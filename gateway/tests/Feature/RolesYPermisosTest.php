<?php

namespace Tests\Feature;

use App\Models\Rol;
use App\Models\User;
use Database\Seeders\AdminInicialSeeder;
use Database\Seeders\RolesYPermisosSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use PHPUnit\Framework\Attributes\DataProvider;
use RuntimeException;
use Tests\TestCase;

class RolesYPermisosTest extends TestCase
{
    use RefreshDatabase;

    private const ADMIN = [
        'email' => 'admin@prueba.local',
        'nombre' => 'Administrador de prueba',
        'password' => 'clave-solo-para-pruebas',
    ];

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesYPermisosSeeder::class);
        config(['gateway.admin_inicial' => self::ADMIN]);
    }

    public function test_existen_los_cuatro_roles(): void
    {
        $roles = Rol::orderBy('codigo')->pluck('nombre', 'codigo')->all();

        $this->assertSame([
            'admin' => 'Administrador',
            'compras' => 'Compras',
            'gerente' => 'Gerente',
            'jefe_bodega' => 'Jefe de bodega',
        ], $roles);
    }

    /** Matriz 4.3 escrita a mano, independiente del seeder. */
    public static function permisosPorRol(): array
    {
        $ver = ['productos.ver', 'bodegas.ver', 'stock.ver', 'proveedores.ver', 'ordenes.ver', 'reportes.ver'];

        return [
            'admin' => ['admin', array_merge($ver, [
                'usuarios.gestionar', 'productos.gestionar', 'bodegas.gestionar',
                'movimientos.ver', 'movimientos.gestionar',
                'devoluciones_cliente.ver', 'devoluciones_cliente.gestionar',
                'proveedores.gestionar', 'ordenes.gestionar', 'ordenes.aprobar',
                'recepciones.registrar', 'devoluciones_proveedor.registrar',
            ])],
            'jefe_bodega' => ['jefe_bodega', array_merge($ver, [
                'bodegas.gestionar', 'movimientos.ver', 'movimientos.gestionar',
                'devoluciones_cliente.ver', 'devoluciones_cliente.gestionar',
                'recepciones.registrar', 'devoluciones_proveedor.registrar',
            ])],
            'compras' => ['compras', array_merge($ver, [
                'proveedores.gestionar', 'ordenes.gestionar', 'devoluciones_proveedor.registrar',
            ])],
            'gerente' => ['gerente', array_merge($ver, [
                'movimientos.ver', 'devoluciones_cliente.ver', 'ordenes.aprobar',
            ])],
        ];
    }

    #[DataProvider('permisosPorRol')]
    public function test_permisos_de_cada_rol_coinciden_con_la_matriz(string $codigo, array $esperados): void
    {
        $permisos = Rol::where('codigo', $codigo)->firstOrFail()->permisos()->pluck('codigo')->sort()->values()->all();

        sort($esperados);
        $this->assertSame($esperados, $permisos);
    }

    public function test_el_seeder_de_roles_es_idempotente(): void
    {
        $this->seed(RolesYPermisosSeeder::class);

        $this->assertSame(4, Rol::count());
        $this->assertSame(18, Rol::where('codigo', 'admin')->first()->permisos()->count());
    }

    public function test_el_seeder_crea_el_admin_con_contrasena_hasheada(): void
    {
        $this->seed(AdminInicialSeeder::class);

        $admin = User::where('email', self::ADMIN['email'])->firstOrFail();
        $this->assertSame('admin', $admin->rol->codigo);
        $this->assertSame(self::ADMIN['nombre'], $admin->name);
        $this->assertNotSame(self::ADMIN['password'], $admin->getRawOriginal('password'));
        $this->assertTrue(Hash::check(self::ADMIN['password'], $admin->password));
        $this->assertSame('ACTIVO', $admin->fresh()->estado);
    }

    public function test_el_seeder_del_admin_no_duplica(): void
    {
        $this->seed(AdminInicialSeeder::class);
        $this->seed(AdminInicialSeeder::class);

        $this->assertSame(1, User::where('email', self::ADMIN['email'])->count());
    }

    public function test_el_seeder_del_admin_falla_sin_contrasena(): void
    {
        config(['gateway.admin_inicial.password' => null]);

        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('ADMIN_PASSWORD');
        $this->seed(AdminInicialSeeder::class);
    }

    public function test_un_usuario_nuevo_queda_activo(): void
    {
        $usuario = User::factory()->create(['id_rol' => Rol::where('codigo', 'gerente')->value('id_rol')]);

        $this->assertSame('ACTIVO', $usuario->estado);
        $this->assertSame('ACTIVO', $usuario->fresh()->estado);
        $this->assertSame('gerente', $usuario->rol->codigo);
    }
}
