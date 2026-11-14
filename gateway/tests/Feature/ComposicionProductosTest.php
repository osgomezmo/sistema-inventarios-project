<?php

namespace Tests\Feature;

use App\Models\Permiso;
use App\Models\Rol;
use App\Models\User;
use Database\Seeders\RolesYPermisosSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ComposicionProductosTest extends TestCase
{
    use RefreshDatabase;

    private const PROVEEDORES = 'http://proveedores.prueba';

    private const PRODUCTOS = 'http://productos.prueba';

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesYPermisosSeeder::class);
        config([
            'gateway.service_token' => 'token-de-servicio-de-prueba',
            'gateway.servicios.proveedores' => self::PROVEEDORES,
            'gateway.servicios.productos' => self::PRODUCTOS,
        ]);
    }

    private function como(string $rol = 'compras')
    {
        $token = User::factory()->create(['id_rol' => Rol::where('codigo', $rol)->value('id_rol')])
            ->createToken('api')->plainTextToken;
        $this->app['auth']->forgetGuards();

        return $this->withToken($token);
    }

    private function skus(int $cantidad): array
    {
        return array_map(fn ($i) => ['sku' => "SKU-{$i}", 'precio_compra' => 1000, 'dias_entrega' => 2, 'estado' => 'ACTIVO'], range(1, $cantidad));
    }

    private function enviadasA(string $base): array
    {
        return Http::recorded()->filter(fn ($par) => str_starts_with($par[0]->url(), $base))->values()->all();
    }

    public function test_proveedor_con_skus(): void
    {
        $listado = ['data' => [['sku' => 'SKU-1']], 'meta' => ['page' => 2, 'per_page' => 5, 'total' => 1]];
        Http::fake([
            self::PROVEEDORES.'/*' => Http::response([...$this->skus(2), ['sku' => 'SKU-1']]),
            self::PRODUCTOS.'/*' => Http::response($listado),
        ]);

        $respuesta = $this->como()->withHeaders(['X-Correlation-Id' => 'corr-1'])
            ->getJson('/api/productos?id_proveedor=7&q=leche&page=2&per_page=5');

        $respuesta->assertOk()->assertExactJson($listado);
        [[$proveedor]] = $this->enviadasA(self::PROVEEDORES);
        $this->assertSame(self::PROVEEDORES.'/proveedores/7/productos', $proveedor->url());
        [[$productos]] = $this->enviadasA(self::PRODUCTOS);
        $this->assertSame(self::PRODUCTOS.'/productos?q=leche&page=2&per_page=5&skus=SKU-1%2CSKU-2', $productos->url());
        foreach ([$proveedor, $productos] as $peticion) {
            $this->assertSame(['corr-1'], $peticion->header('X-Correlation-Id'));
            $this->assertSame(['compras'], $peticion->header('X-User-Role'));
            $this->assertSame(['Bearer token-de-servicio-de-prueba'], $peticion->header('Authorization'));
        }
    }

    public function test_proveedor_sin_skus_no_llama_a_productos(): void
    {
        Http::fake([self::PROVEEDORES.'/*' => Http::response([])]);

        $this->como()->getJson('/api/productos?id_proveedor=7&per_page=10')
            ->assertOk()
            ->assertExactJson(['data' => [], 'meta' => ['page' => 1, 'per_page' => 10, 'total' => 0]]);
        $this->assertSame([], $this->enviadasA(self::PRODUCTOS));
    }

    public function test_proveedor_inexistente_da_404(): void
    {
        Http::fake([self::PROVEEDORES.'/*' => Http::response(['error' => ['codigo' => 'NO_EXISTE']], 404)]);

        $this->como()->getJson('/api/productos?id_proveedor=99')
            ->assertStatus(404)->assertJsonPath('error.codigo', 'NO_EXISTE');
        $this->assertSame([], $this->enviadasA(self::PRODUCTOS));
    }

    public function test_mas_de_100_skus_da_422(): void
    {
        Http::fake([self::PROVEEDORES.'/*' => Http::response($this->skus(101))]);

        $this->como()->getJson('/api/productos?id_proveedor=7')
            ->assertStatus(422)->assertJsonPath('error.codigo', 'VALIDACION')
            ->assertJsonStructure(['error' => ['detalles' => ['id_proveedor']]]);
        $this->assertSame([], $this->enviadasA(self::PRODUCTOS));
    }

    public function test_id_proveedor_invalido_da_422(): void
    {
        Http::fake();

        foreach (['abc', '0', '-3', '1.5', ''] as $valor) {
            $this->como()->getJson('/api/productos?id_proveedor='.$valor)
                ->assertStatus(422)->assertJsonPath('error.codigo', 'VALIDACION');
        }
        Http::assertNothingSent();
    }

    public function test_sin_proveedores_ver_da_403(): void
    {
        // Todos los roles tienen proveedores.ver según 4.3: se quita solo en esta prueba
        Rol::where('codigo', 'gerente')->first()->permisos()
            ->detach(Permiso::where('codigo', 'proveedores.ver')->value('id_permiso'));
        Http::fake();

        $this->como('gerente')->getJson('/api/productos?id_proveedor=7')
            ->assertStatus(403)->assertJsonPath('error.codigo', 'SIN_PERMISO');
        Http::assertNothingSent();
    }

    public function test_proveedores_caido_da_503(): void
    {
        Http::fake([self::PROVEEDORES.'/*' => fn () => throw new ConnectionException('caído')]);

        $this->como()->getJson('/api/productos?id_proveedor=7')
            ->assertStatus(503)->assertJsonPath('error.codigo', 'SERVICIO_NO_DISPONIBLE');
    }

    public function test_productos_caido_da_503(): void
    {
        Http::fake([
            self::PROVEEDORES.'/*' => Http::response($this->skus(1)),
            self::PRODUCTOS.'/*' => fn () => throw new ConnectionException('caído'),
        ]);

        $this->como()->getJson('/api/productos?id_proveedor=7')
            ->assertStatus(503)->assertJsonPath('error.codigo', 'SERVICIO_NO_DISPONIBLE');
    }

    public function test_sin_id_proveedor_sigue_el_reenvio_normal(): void
    {
        Http::fake(['*' => Http::response(['data' => [], 'meta' => ['page' => 1, 'per_page' => 20, 'total' => 0]])]);

        $this->como()->getJson('/api/productos?q=leche')->assertOk();

        $enviadas = Http::recorded();
        $this->assertCount(1, $enviadas);
        $this->assertSame(self::PRODUCTOS.'/productos?q=leche', $enviadas[0][0]->url());
    }
}
