<?php

namespace Tests\Feature;

use App\Models\Rol;
use App\Models\User;
use Database\Seeders\RolesYPermisosSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use RuntimeException;
use Tests\TestCase;

class AuthTest extends TestCase
{
    use RefreshDatabase;

    private const CLAVE = 'clave-de-prueba-1';

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesYPermisosSeeder::class);
    }

    private function usuario(string $rol = 'jefe_bodega', string $estado = 'ACTIVO'): User
    {
        return User::factory()->create([
            'email' => "{$rol}@prueba.local",
            'password' => self::CLAVE,
            'id_rol' => Rol::where('codigo', $rol)->value('id_rol'),
            'estado' => $estado,
        ]);
    }

    private function login(string $email, string $password = self::CLAVE)
    {
        return $this->postJson('/api/auth/login', ['email' => $email, 'password' => $password]);
    }

    /** Cada petición con un token distinto debe autenticarse de nuevo. */
    private function conToken(string $token)
    {
        $this->app['auth']->forgetGuards();

        return $this->withToken($token);
    }

    private function assertError($respuesta, int $status, string $codigo): void
    {
        $respuesta->assertStatus($status)
            ->assertJsonStructure(['error' => ['codigo', 'mensaje', 'detalles']])
            ->assertJsonPath('error.codigo', $codigo);
    }

    public function test_login_correcto(): void
    {
        $usuario = $this->usuario();

        $respuesta = $this->login('  JEFE_BODEGA@prueba.local ')->assertOk();

        $respuesta->assertJsonStructure(['token', 'usuario' => ['id', 'nombre', 'email', 'estado', 'rol']])
            ->assertJsonPath('usuario.id', $usuario->id)
            ->assertJsonPath('usuario.rol', ['codigo' => 'jefe_bodega', 'nombre' => 'Jefe de bodega'])
            ->assertJsonMissingPath('usuario.password');
        $this->assertSame(['id', 'nombre', 'email', 'estado', 'rol'], array_keys($respuesta->json('usuario')));
        $this->assertSame('api', $usuario->tokens()->first()->name);
    }

    public function test_correo_inexistente_y_clave_errada_dan_el_mismo_401(): void
    {
        $this->usuario();

        $inexistente = $this->login('nadie@prueba.local');
        $errada = $this->login('jefe_bodega@prueba.local', 'otra-clave');

        $this->assertError($inexistente, 401, 'CREDENCIALES_INVALIDAS');
        $this->assertError($errada, 401, 'CREDENCIALES_INVALIDAS');
        $this->assertSame($inexistente->json(), $errada->json());
    }

    public function test_usuario_inactivo_no_puede_entrar(): void
    {
        $this->usuario(estado: 'INACTIVO');

        $this->assertError($this->login('jefe_bodega@prueba.local'), 403, 'USUARIO_INACTIVO');
    }

    public function test_validacion_del_login(): void
    {
        $respuesta = $this->postJson('/api/auth/login', ['email' => 'no-es-correo']);

        $this->assertError($respuesta, 422, 'VALIDACION');
        $this->assertSame(['email', 'password'], array_keys($respuesta->json('error.detalles')));
    }

    public function test_el_sexto_intento_en_un_minuto_da_429(): void
    {
        $this->usuario();
        for ($i = 0; $i < 5; $i++) {
            $this->login('jefe_bodega@prueba.local', 'errada')->assertStatus(401);
        }

        $this->assertError($this->login('jefe_bodega@prueba.local'), 429, 'DEMASIADAS_PETICIONES');
    }

    public function test_logout_revoca_solo_el_token_actual(): void
    {
        $usuario = $this->usuario();
        $primero = $usuario->createToken('api')->plainTextToken;
        $segundo = $usuario->createToken('api')->plainTextToken;

        $this->conToken($primero)->postJson('/api/auth/logout')->assertNoContent();

        $this->assertError($this->conToken($primero)->getJson('/api/auth/me'), 401, 'NO_AUTENTICADO');
        $this->conToken($segundo)->getJson('/api/auth/me')->assertOk();
    }

    public function test_me_devuelve_los_permisos_del_rol(): void
    {
        $token = $this->usuario('compras')->createToken('api')->plainTextToken;

        $this->conToken($token)->getJson('/api/auth/me')
            ->assertOk()
            ->assertJsonPath('rol.codigo', 'compras')
            ->assertJsonPath('permisos', [
                'bodegas.ver', 'devoluciones_proveedor.registrar', 'ordenes.gestionar', 'ordenes.ver',
                'productos.ver', 'proveedores.gestionar', 'proveedores.ver', 'reportes.ver', 'stock.ver',
            ]);
    }

    public function test_cambio_de_contrasena(): void
    {
        $usuario = $this->usuario();
        $actual = $usuario->createToken('api')->plainTextToken;
        $otro = $usuario->createToken('api')->plainTextToken;

        $this->conToken($actual)->putJson('/api/auth/password', [
            'password_actual' => self::CLAVE,
            'password_nueva' => 'otra-clave-nueva',
        ])->assertNoContent();

        $this->conToken($actual)->getJson('/api/auth/me')->assertOk();
        $this->assertError($this->conToken($otro)->getJson('/api/auth/me'), 401, 'NO_AUTENTICADO');
        $this->assertError($this->login('jefe_bodega@prueba.local'), 401, 'CREDENCIALES_INVALIDAS');
        $this->login('jefe_bodega@prueba.local', 'otra-clave-nueva')->assertOk();
    }

    public function test_cambio_de_contrasena_con_la_actual_errada(): void
    {
        $token = $this->usuario()->createToken('api')->plainTextToken;

        $respuesta = $this->conToken($token)->putJson('/api/auth/password', [
            'password_actual' => 'no-es-la-clave',
            'password_nueva' => 'otra-clave-nueva',
        ]);

        $this->assertError($respuesta, 422, 'VALIDACION');
        $this->assertSame(['password_actual'], array_keys($respuesta->json('error.detalles')));
    }

    public function test_la_nueva_debe_tener_8_caracteres_y_ser_distinta(): void
    {
        $token = $this->usuario()->createToken('api')->plainTextToken;

        $corta = $this->conToken($token)->putJson('/api/auth/password', [
            'password_actual' => self::CLAVE, 'password_nueva' => 'corta',
        ]);
        $igual = $this->conToken($token)->putJson('/api/auth/password', [
            'password_actual' => self::CLAVE, 'password_nueva' => self::CLAVE,
        ]);

        $this->assertError($corta, 422, 'VALIDACION');
        $this->assertError($igual, 422, 'VALIDACION');
        $this->assertArrayHasKey('password_nueva', $igual->json('error.detalles'));
    }

    public function test_usuario_inactivado_con_token_vigente_recibe_403(): void
    {
        $usuario = $this->usuario();
        $token = $usuario->createToken('api')->plainTextToken;
        $usuario->update(['estado' => 'INACTIVO']);

        $this->assertError($this->conToken($token)->getJson('/api/auth/me'), 403, 'USUARIO_INACTIVO');
    }

    public function test_404_y_500_salen_con_el_formato_del_contrato_y_sin_traza(): void
    {
        config(['app.debug' => true, 'gateway.service_token' => 'token-de-servicio-de-prueba']);
        // Una falla no prevista al llamar a un servicio debe salir como 500 genérico
        Http::fake(fn () => throw new RuntimeException('detalle interno'));
        $token = $this->usuario()->createToken('api')->plainTextToken;

        $noExiste = $this->conToken($token)->getJson('/api/ruta-que-no-existe');
        $interno = $this->conToken($token)->getJson('/api/stock');

        $this->assertError($noExiste, 404, 'NO_EXISTE');
        $this->assertError($interno, 500, 'ERROR_INTERNO');
        $this->assertSame(['error'], array_keys($interno->json()));
        $this->assertStringNotContainsString('detalle interno', $interno->getContent());
        $this->assertStringNotContainsString('trace', $interno->getContent());
    }

    public function test_metodo_no_permitido_da_405(): void
    {
        $this->assertError($this->getJson('/api/auth/login'), 405, 'METODO_NO_PERMITIDO');
    }
}
