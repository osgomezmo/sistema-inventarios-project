<?php

namespace Tests\Feature;

use App\Models\Permiso;
use App\Models\Rol;
use App\Models\User;
use Database\Seeders\RolesYPermisosSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class UsuariosTest extends TestCase
{
    use RefreshDatabase;

    private User $admin;

    private string $tokenAdmin;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesYPermisosSeeder::class);
        $this->admin = $this->crearUsuario('admin', 'Admin Uno', 'admin1@prueba.local');
        $this->tokenAdmin = $this->admin->createToken('api')->plainTextToken;
    }

    private function idRol(string $codigo): int
    {
        return Rol::where('codigo', $codigo)->value('id_rol');
    }

    private function crearUsuario(string $rol, string $nombre, string $email, string $estado = 'ACTIVO'): User
    {
        return User::factory()->create([
            'name' => $nombre, 'email' => $email, 'password' => 'clave-de-prueba-1',
            'id_rol' => $this->idRol($rol), 'estado' => $estado,
        ]);
    }

    /** Cada petición con un token distinto debe autenticarse de nuevo. */
    private function como(?string $token = null)
    {
        $this->app['auth']->forgetGuards();

        return $this->withToken($token ?? $this->tokenAdmin);
    }

    private function assertError($respuesta, int $status, string $codigo): void
    {
        $respuesta->assertStatus($status)
            ->assertJsonStructure(['error' => ['codigo', 'mensaje', 'detalles']])
            ->assertJsonPath('error.codigo', $codigo);
    }

    public static function rutas(): array
    {
        return [
            ['GET', '/api/usuarios'], ['POST', '/api/usuarios'], ['GET', '/api/usuarios/1'],
            ['PUT', '/api/usuarios/1'], ['POST', '/api/usuarios/1/inactivar'],
            ['POST', '/api/usuarios/1/activar'], ['GET', '/api/roles'],
        ];
    }

    #[DataProvider('rutas')]
    public function test_sin_usuarios_gestionar_recibe_403(string $metodo, string $ruta): void
    {
        $token = $this->crearUsuario('gerente', 'Gerente', 'gerente@prueba.local')->createToken('api')->plainTextToken;

        $this->assertError($this->como($token)->json($metodo, $ruta, []), 403, 'SIN_PERMISO');
    }

    public function test_listado_paginado_con_filtros(): void
    {
        $this->crearUsuario('compras', 'Carla', 'carla@prueba.local');
        $this->crearUsuario('compras', 'Andrés', 'andres@prueba.local', 'INACTIVO');
        $this->crearUsuario('gerente', 'Beatriz', 'beatriz@prueba.local');

        $todos = $this->como()->getJson('/api/usuarios?per_page=2')->assertOk();
        $todos->assertJsonPath('meta', ['page' => 1, 'per_page' => 2, 'total' => 4]);
        $this->assertSame(['Admin Uno', 'Andrés'], array_column($todos->json('data'), 'nombre'));

        $compras = $this->como()->getJson('/api/usuarios?rol=compras&estado=ACTIVO')->assertOk();
        $this->assertSame(['Carla'], array_column($compras->json('data'), 'nombre'));
        $this->assertSame(['id', 'nombre', 'email', 'estado', 'rol'], array_keys($compras->json('data.0')));
    }

    public function test_filtros_invalidos_dan_422(): void
    {
        $respuesta = $this->como()->getJson('/api/usuarios?rol=jefe&estado=x&per_page=101&page=0');

        $this->assertError($respuesta, 422, 'VALIDACION');
        $this->assertEqualsCanonicalizing(['rol', 'estado', 'per_page', 'page'], array_keys($respuesta->json('error.detalles')));
    }

    public function test_crear_usuario(): void
    {
        $respuesta = $this->como()->postJson('/api/usuarios', [
            'nombre' => 'Laura Gómez', 'email' => '  Laura.Gomez@Prueba.LOCAL ',
            'password' => 'clave-segura-1', 'id_rol' => $this->idRol('jefe_bodega'),
        ]);

        $respuesta->assertCreated()
            ->assertJsonPath('email', 'laura.gomez@prueba.local')
            ->assertJsonPath('estado', 'ACTIVO')
            ->assertJsonPath('rol.codigo', 'jefe_bodega')
            ->assertJsonMissingPath('password');
        $creado = User::where('email', 'laura.gomez@prueba.local')->firstOrFail();
        $this->assertNotSame('clave-segura-1', $creado->getRawOriginal('password'));
        $this->assertTrue(Hash::check('clave-segura-1', $creado->password));
    }

    public function test_correo_duplicado_con_otra_capitalizacion_da_409(): void
    {
        $respuesta = $this->como()->postJson('/api/usuarios', [
            'nombre' => 'Otro', 'email' => 'ADMIN1@prueba.local',
            'password' => 'clave-segura-1', 'id_rol' => $this->idRol('compras'),
        ]);

        $this->assertError($respuesta, 409, 'EMAIL_DUPLICADO');
    }

    public function test_crear_con_id_rol_inexistente_y_datos_invalidos_da_422(): void
    {
        $respuesta = $this->como()->postJson('/api/usuarios', [
            'nombre' => '', 'email' => 'no-es-correo', 'password' => 'corta', 'id_rol' => 999,
        ]);

        $this->assertError($respuesta, 422, 'VALIDACION');
        $this->assertEqualsCanonicalizing(['nombre', 'email', 'password', 'id_rol'], array_keys($respuesta->json('error.detalles')));
    }

    public function test_ver_usuario(): void
    {
        $usuario = $this->crearUsuario('compras', 'Carla', 'carla@prueba.local');

        $this->como()->getJson("/api/usuarios/{$usuario->id}")->assertOk()->assertJsonPath('nombre', 'Carla');
        $this->assertError($this->como()->getJson('/api/usuarios/999999'), 404, 'NO_EXISTE');
    }

    public function test_editar_usuario_no_toca_contrasena_ni_estado(): void
    {
        $usuario = $this->crearUsuario('compras', 'Carla', 'carla@prueba.local');

        $this->como()->putJson("/api/usuarios/{$usuario->id}", [
            'nombre' => 'Carla Ruiz', 'email' => 'carla.ruiz@prueba.local', 'id_rol' => $this->idRol('gerente'),
            'password' => 'no-debe-cambiar', 'estado' => 'INACTIVO',
        ])->assertOk()->assertJsonPath('nombre', 'Carla Ruiz')->assertJsonPath('rol.codigo', 'gerente');

        $usuario->refresh();
        $this->assertTrue(Hash::check('clave-de-prueba-1', $usuario->password));
        $this->assertSame('ACTIVO', $usuario->estado);
    }

    public function test_inactivar_revoca_los_tokens_y_es_idempotente(): void
    {
        $usuario = $this->crearUsuario('compras', 'Carla', 'carla@prueba.local');
        $token = $usuario->createToken('api')->plainTextToken;

        $this->como()->postJson("/api/usuarios/{$usuario->id}/inactivar")->assertOk()->assertJsonPath('estado', 'INACTIVO');
        $this->como()->postJson("/api/usuarios/{$usuario->id}/inactivar")->assertOk()->assertJsonPath('estado', 'INACTIVO');

        $this->assertSame(0, $usuario->tokens()->count());
        $this->assertError($this->como($token)->getJson('/api/auth/me'), 401, 'NO_AUTENTICADO');
    }

    public function test_activar(): void
    {
        $usuario = $this->crearUsuario('compras', 'Carla', 'carla@prueba.local', 'INACTIVO');

        $this->como()->postJson("/api/usuarios/{$usuario->id}/activar")->assertOk()->assertJsonPath('estado', 'ACTIVO');
        $this->como()->postJson("/api/usuarios/{$usuario->id}/activar")->assertOk()->assertJsonPath('estado', 'ACTIVO');
    }

    public function test_el_admin_no_puede_inactivarse_ni_quitarse_el_rol(): void
    {
        $this->crearUsuario('admin', 'Admin Dos', 'admin2@prueba.local');

        $this->assertError($this->como()->postJson("/api/usuarios/{$this->admin->id}/inactivar"), 409, 'CONFLICTO');
        $this->assertError($this->como()->putJson("/api/usuarios/{$this->admin->id}", [
            'nombre' => 'Admin Uno', 'email' => 'admin1@prueba.local', 'id_rol' => $this->idRol('gerente'),
        ]), 409, 'CONFLICTO');
        $this->assertSame('admin', $this->admin->fresh()->rol->codigo);
    }

    public function test_no_se_puede_quedar_sin_administradores_activos(): void
    {
        // Un gerente con usuarios.gestionar (solo en esta prueba) intenta dejar
        // sin efecto al único administrador activo.
        $gerente = Rol::where('codigo', 'gerente')->first();
        $gerente->permisos()->attach(Permiso::where('codigo', 'usuarios.gestionar')->value('id_permiso'));
        $token = $this->crearUsuario('gerente', 'Gerente', 'gerente@prueba.local')->createToken('api')->plainTextToken;
        $this->crearUsuario('admin', 'Admin Inactivo', 'admin2@prueba.local', 'INACTIVO');

        $this->assertError($this->como($token)->postJson("/api/usuarios/{$this->admin->id}/inactivar"), 409, 'CONFLICTO');
        $this->assertError($this->como($token)->putJson("/api/usuarios/{$this->admin->id}", [
            'nombre' => 'Admin Uno', 'email' => 'admin1@prueba.local', 'id_rol' => $this->idRol('compras'),
        ]), 409, 'CONFLICTO');
        $this->assertSame('ACTIVO', $this->admin->fresh()->estado);
        $this->assertSame('admin', $this->admin->fresh()->rol->codigo);

        // Con otro administrador activo, sí se permite
        $this->crearUsuario('admin', 'Admin Tres', 'admin3@prueba.local');
        $this->como($token)->postJson("/api/usuarios/{$this->admin->id}/inactivar")->assertOk();
    }

    public function test_roles_con_sus_permisos(): void
    {
        $roles = $this->como()->getJson('/api/roles')->assertOk()->json();

        $this->assertSame(['admin', 'jefe_bodega', 'compras', 'gerente'], array_column($roles, 'codigo'));
        $this->assertSame(['id_rol', 'codigo', 'nombre', 'permisos'], array_keys($roles[0]));
        $this->assertCount(18, $roles[0]['permisos']);
        $this->assertSame(['ordenes.aprobar'], array_values(array_intersect(['ordenes.aprobar'], $roles[3]['permisos'])));
        $this->assertNotContains('usuarios.gestionar', $roles[3]['permisos']);
    }
}
