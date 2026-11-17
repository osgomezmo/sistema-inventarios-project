<?php

namespace Tests\Feature;

use App\Console\Commands\DatosIniciales;
use App\Models\Rol;
use App\Models\User;
use Database\Seeders\RolesYPermisosSeeder;
use Database\Seeders\UsuariosInicialesSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Log;
use Tests\TestCase;

class UsuariosInicialesTest extends TestCase
{
    use RefreshDatabase;

    private const PASSWORD = 'clave-inicial-de-prueba';

    private const ADMIN = [
        'email' => 'admin@prueba.local',
        'nombre' => 'Administrador de prueba',
        'password' => 'clave-solo-para-pruebas',
    ];

    protected function setUp(): void
    {
        parent::setUp();
        config(['gateway.usuarios_iniciales_password' => self::PASSWORD, 'gateway.admin_inicial' => self::ADMIN]);
    }

    /** Correo => código del rol de los usuarios creados. */
    private function usuariosConRol(): array
    {
        return User::with('rol')->orderBy('email')->get()
            ->mapWithKeys(fn (User $u) => [$u->email => $u->rol?->codigo])->all();
    }

    public function test_crea_un_usuario_por_rol_con_la_contrasena_comun(): void
    {
        $this->seed(RolesYPermisosSeeder::class);

        $this->seed(UsuariosInicialesSeeder::class);

        $this->assertSame([
            'compras@inventario.local' => 'compras',
            'gerente@inventario.local' => 'gerente',
            'jefe.bodega@inventario.local' => 'jefe_bodega',
        ], $this->usuariosConRol());
        foreach (User::all() as $usuario) {
            $this->assertSame('ACTIVO', $usuario->estado);
            $this->assertTrue(Hash::check(self::PASSWORD, $usuario->password));
            $this->assertNotSame(self::PASSWORD, $usuario->password);
        }
    }

    public function test_los_usuarios_iniciales_pueden_iniciar_sesion(): void
    {
        $this->seed(RolesYPermisosSeeder::class);
        $this->seed(UsuariosInicialesSeeder::class);

        $this->postJson('/api/auth/login', ['email' => 'gerente@inventario.local', 'password' => self::PASSWORD])
            ->assertOk()
            ->assertJsonPath('usuario.rol.codigo', 'gerente');
    }

    public function test_correrlo_dos_veces_no_duplica_ni_cambia_contrasenas(): void
    {
        $this->seed(RolesYPermisosSeeder::class);
        $this->seed(UsuariosInicialesSeeder::class);
        config(['gateway.usuarios_iniciales_password' => 'otra-clave-distinta']);

        $this->seed(UsuariosInicialesSeeder::class);

        $this->assertSame(3, User::count());
        $this->assertTrue(Hash::check(self::PASSWORD, User::where('email', 'compras@inventario.local')->value('password')));
    }

    public function test_sin_contrasena_no_crea_usuarios_y_lo_registra(): void
    {
        $this->seed(RolesYPermisosSeeder::class);
        config(['gateway.usuarios_iniciales_password' => '']);
        Log::spy();

        $this->seed(UsuariosInicialesSeeder::class);

        $this->assertSame(0, User::count());
        Log::shouldHaveReceived('warning')->with(UsuariosInicialesSeeder::AVISO_SIN_PASSWORD)->once();
    }

    public function test_el_comando_siembra_todo_con_la_base_vacia(): void
    {
        $this->artisan('gateway:datos-iniciales')->assertSuccessful();

        $this->assertSame(4, Rol::count());
        $this->assertSame([
            'admin@prueba.local' => 'admin',
            'compras@inventario.local' => 'compras',
            'gerente@inventario.local' => 'gerente',
            'jefe.bodega@inventario.local' => 'jefe_bodega',
        ], $this->usuariosConRol());
    }

    public function test_el_comando_no_hace_nada_si_ya_hay_roles(): void
    {
        $this->seed(RolesYPermisosSeeder::class);

        $this->artisan('gateway:datos-iniciales')
            ->expectsOutputToContain('ya tiene roles')
            ->assertSuccessful();

        $this->assertSame(0, User::count());
    }

    public function test_el_comando_sigue_sin_administrador_si_faltan_sus_variables(): void
    {
        config(['gateway.admin_inicial' => ['email' => 'admin@prueba.local', 'nombre' => '', 'password' => '']]);
        Log::spy();

        $this->artisan('gateway:datos-iniciales')->assertSuccessful();

        $this->assertSame(4, Rol::count());
        $this->assertFalse(User::where('email', 'admin@prueba.local')->exists());
        $this->assertSame(3, User::count());
        Log::shouldHaveReceived('warning')->with(DatosIniciales::AVISO_SIN_ADMIN)->once();
    }

    public function test_el_comando_sigue_sin_usuarios_si_falta_su_contrasena(): void
    {
        config(['gateway.usuarios_iniciales_password' => null]);

        $this->artisan('gateway:datos-iniciales')->assertSuccessful();

        $this->assertSame(['admin@prueba.local' => 'admin'], $this->usuariosConRol());
    }
}
