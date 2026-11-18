<?php

namespace Tests\Feature;

use App\Models\Rol;
use App\Models\User;
use Database\Seeders\RolesYPermisosSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Request as PeticionServicio;
use Illuminate\Support\Facades\Http;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class ProxyTest extends TestCase
{
    use RefreshDatabase;

    private const TOKEN_SERVICIO = 'token-de-servicio-de-prueba';

    private const URLS = [
        'productos' => 'http://productos.prueba',
        'inventario' => 'http://inventario.prueba',
        'compras' => 'http://compras.prueba',
        'proveedores' => 'http://proveedores.prueba',
        'notificaciones' => 'http://notificaciones.prueba',
        'reportes' => 'http://reportes.prueba',
    ];

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesYPermisosSeeder::class);
        config(['gateway.service_token' => self::TOKEN_SERVICIO, 'gateway.servicios' => self::URLS, 'gateway.timeout' => 1]);
    }

    private function token(string $rol = 'admin', string $estado = 'ACTIVO'): string
    {
        $usuario = User::factory()->create([
            'id_rol' => Rol::where('codigo', $rol)->value('id_rol'),
            'estado' => $estado,
        ]);

        return $usuario->createToken('api')->plainTextToken;
    }

    private function como(string $token)
    {
        $this->app['auth']->forgetGuards();

        return $this->withToken($token);
    }

    private function respuestaOk(): void
    {
        Http::fake(['*' => Http::response(['ok' => true], 200)]);
    }

    /** Única petición que recibió algún servicio. */
    private function peticionEnviada(): PeticionServicio
    {
        $enviadas = Http::recorded();
        $this->assertCount(1, $enviadas);

        return $enviadas[0][0];
    }

    private function assertError($respuesta, int $status, string $codigo): void
    {
        $respuesta->assertStatus($status)->assertJsonPath('error.codigo', $codigo);
    }

    // --- Enrutamiento ---------------------------------------------------------------

    public static function prefijos(): array
    {
        return [
            ['categorias', 'productos'], ['productos/sku/LAC-1', 'productos'],
            ['bodegas/3', 'inventario'], ['stock', 'inventario'], ['movimientos', 'inventario'],
            ['kardex', 'inventario'], ['traslados', 'inventario'], ['devoluciones-cliente', 'inventario'],
            ['proveedores/7/productos', 'proveedores'],
            ['ordenes-compra/5/recepciones', 'compras'], ['devoluciones-proveedor', 'compras'],
            ['reportes/valorizacion', 'reportes'], ['dashboard', 'reportes'],
            ['notificaciones', 'notificaciones'], ['dispositivos', 'notificaciones'],
        ];
    }

    #[DataProvider('prefijos')]
    public function test_cada_prefijo_va_a_su_servicio_sin_api_y_con_la_consulta_intacta(string $ruta, string $servicio): void
    {
        $this->respuestaOk();

        $this->como($this->token())->getJson("/api/{$ruta}?page=2&q=leche%20entera")->assertOk();

        $this->assertSame(self::URLS[$servicio]."/{$ruta}?page=2&q=leche%20entera", $this->peticionEnviada()->url());
    }

    public function test_el_servicio_recibe_la_identidad_del_gateway_y_no_la_del_cliente(): void
    {
        $this->respuestaOk();
        $tokenCliente = $this->token('gerente');
        $usuario = User::latest('id')->first();

        $this->como($tokenCliente)->withHeaders([
            'X-User-Role' => 'admin', 'X-User-Id' => '1', 'Cookie' => 'sesion=abc',
        ])->getJson('/api/stock')->assertOk();

        $peticion = $this->peticionEnviada();
        $this->assertSame(['Bearer '.self::TOKEN_SERVICIO], $peticion->header('Authorization'));
        $this->assertSame([(string) $usuario->id], $peticion->header('X-User-Id'));
        $this->assertSame(['gerente'], $peticion->header('X-User-Role'));
        $this->assertNotEmpty($peticion->header('X-Correlation-Id')[0]);
        $this->assertSame([], $peticion->header('Cookie'));
        $this->assertStringNotContainsString(explode('|', $tokenCliente)[1], json_encode($peticion->headers()));
    }

    public function test_el_cuerpo_crudo_y_su_tipo_llegan_al_servicio(): void
    {
        $this->respuestaOk();
        $cuerpo = '{"sku":"LAC-1","id_bodega":2,"tipo":"SALIDA","cantidad":3}';

        // call() no aplica las cabeceras de withToken(): van como variables de servidor
        $this->app['auth']->forgetGuards();
        $this->call('POST', '/api/movimientos', [], [], [], [
            'CONTENT_TYPE' => 'application/json', 'HTTP_ACCEPT' => 'application/json',
            'HTTP_AUTHORIZATION' => 'Bearer '.$this->token(),
        ], $cuerpo)->assertOk();

        $peticion = $this->peticionEnviada();
        $this->assertSame('POST', $peticion->method());
        $this->assertSame($cuerpo, $peticion->body());
        $this->assertSame(['application/json'], $peticion->header('Content-Type'));
    }

    public static function respuestasDelServicio(): array
    {
        return [
            [404, ['error' => ['codigo' => 'NO_EXISTE', 'mensaje' => 'x', 'detalles' => []]]],
            [409, ['error' => ['codigo' => 'STOCK_INSUFICIENTE', 'mensaje' => 'x', 'detalles' => []]]],
            [422, ['error' => ['codigo' => 'VALIDACION', 'mensaje' => 'x', 'detalles' => ['cantidad' => ['Mal.']]]]],
            [201, ['id_movimiento' => 9]],
        ];
    }

    #[DataProvider('respuestasDelServicio')]
    public function test_el_codigo_y_el_cuerpo_del_servicio_llegan_al_cliente(int $status, array $cuerpo): void
    {
        Http::fake(['*' => Http::response($cuerpo, $status, ['X-Interno' => 'secreto'])]);

        $respuesta = $this->como($this->token())->postJson('/api/movimientos', ['sku' => 'X']);

        $respuesta->assertStatus($status)->assertExactJson($cuerpo)->assertHeader('Content-Type', 'application/json');
        $respuesta->assertHeaderMissing('X-Interno');
    }

    public function test_un_csv_conserva_content_type_y_content_disposition(): void
    {
        Http::fake(['*' => Http::response("sku,valor\nLAC-1,100\n", 200, [
            'Content-Type' => 'text/csv; charset=utf-8',
            'Content-Disposition' => 'attachment; filename="rotacion.csv"',
        ])]);

        $respuesta = $this->como($this->token())->get('/api/reportes/rotacion?formato=csv');

        $respuesta->assertOk()
            ->assertHeader('Content-Type', 'text/csv; charset=utf-8')
            ->assertHeader('Content-Disposition', 'attachment; filename="rotacion.csv"');
        $this->assertSame("sku,valor\nLAC-1,100\n", $respuesta->getContent());
    }

    public function test_un_pdf_conserva_content_type_y_content_disposition_y_cuerpo_binario(): void
    {
        $binarioPdf = "%PDF-1.4\n1 0 obj<</Type/Catalog>>\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF\x00\xFF\xFE";
        Http::fake(['*' => Http::response($binarioPdf, 200, [
            'Content-Type' => 'application/pdf',
            'Content-Disposition' => 'attachment; filename="reporte_valorizacion.pdf"',
        ])]);

        $respuesta = $this->como($this->token())->get('/api/reportes/valorizacion?formato=pdf');

        $respuesta->assertOk()
            ->assertHeader('Content-Type', 'application/pdf')
            ->assertHeader('Content-Disposition', 'attachment; filename="reporte_valorizacion.pdf"');
        $this->assertSame($binarioPdf, $respuesta->getContent());
    }

    public function test_correlation_id_del_cliente_se_reenvia_y_se_devuelve(): void
    {
        $this->respuestaOk();

        $respuesta = $this->como($this->token())->withHeaders(['X-Correlation-Id' => 'abc-123'])->getJson('/api/stock');

        $respuesta->assertHeader('X-Correlation-Id', 'abc-123');
        $this->assertSame(['abc-123'], $this->peticionEnviada()->header('X-Correlation-Id'));
    }

    public function test_correlation_id_invalido_se_reemplaza(): void
    {
        $this->respuestaOk();

        $respuesta = $this->como($this->token())->withHeaders(['X-Correlation-Id' => 'mal id; <script>'])->getJson('/api/stock');

        $nuevo = $respuesta->headers->get('X-Correlation-Id');
        $this->assertMatchesRegularExpression('/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/', $nuevo);
        $this->assertSame([$nuevo], $this->peticionEnviada()->header('X-Correlation-Id'));
    }

    public function test_los_errores_tambien_llevan_correlation_id(): void
    {
        $this->getJson('/api/stock')->assertStatus(401)->assertHeader('X-Correlation-Id');
    }

    // --- Permisos (matriz 4.3) ------------------------------------------------------------

    public static function matriz(): array
    {
        return [
            // rol, método, ruta, ¿permitido?
            ['gerente', 'POST', 'ordenes-compra/5/aprobar', true],
            ['jefe_bodega', 'POST', 'ordenes-compra/5/aprobar', false],
            ['jefe_bodega', 'POST', 'ordenes-compra/5/recepciones', true],
            ['compras', 'POST', 'ordenes-compra/5/recepciones', false],
            ['compras', 'POST', 'movimientos', false],
            ['jefe_bodega', 'POST', 'movimientos', true],
            ['compras', 'GET', 'movimientos', false],
            ['gerente', 'GET', 'movimientos', true],
            ['compras', 'GET', 'stock', true],
            ['gerente', 'POST', 'productos', false],
            ['admin', 'POST', 'productos', true],
            ['jefe_bodega', 'GET', 'productos', true],
            ['compras', 'POST', 'proveedores', true],
            ['jefe_bodega', 'POST', 'proveedores', false],
            ['compras', 'POST', 'ordenes-compra', true],
            ['gerente', 'PUT', 'ordenes-compra/5', false],
            ['gerente', 'GET', 'devoluciones-proveedor', false],
            ['compras', 'GET', 'devoluciones-proveedor', true],
            ['compras', 'POST', 'bodegas', false],
            ['jefe_bodega', 'POST', 'bodegas', true],
            ['compras', 'POST', 'devoluciones-cliente', false],
            ['jefe_bodega', 'POST', 'devoluciones-cliente', true],
            ['gerente', 'GET', 'reportes/rotacion', true],
            ['compras', 'GET', 'notificaciones', true],
            ['gerente', 'POST', 'dispositivos', true],
        ];
    }

    #[DataProvider('matriz')]
    public function test_matriz_de_permisos(string $rol, string $metodo, string $ruta, bool $permitido): void
    {
        $this->respuestaOk();

        $respuesta = $this->como($this->token($rol))->json($metodo, "/api/{$ruta}", ['x' => 1]);

        if ($permitido) {
            $respuesta->assertOk();
            $this->assertSame($metodo, $this->peticionEnviada()->method());
        } else {
            $this->assertError($respuesta, 403, 'SIN_PERMISO');
            Http::assertNothingSent();
        }
    }

    // --- Rechazos antes de llamar al servicio ------------------------------------------------

    public function test_sin_token_da_401_sin_llamar_al_servicio(): void
    {
        $this->respuestaOk();

        $this->assertError($this->getJson('/api/stock'), 401, 'NO_AUTENTICADO');
        Http::assertNothingSent();
    }

    public function test_usuario_inactivo_da_403(): void
    {
        $this->respuestaOk();

        $this->assertError($this->como($this->token('admin', 'INACTIVO'))->getJson('/api/stock'), 403, 'USUARIO_INACTIVO');
        Http::assertNothingSent();
    }

    public static function rutasInvalidas(): array
    {
        return [
            ['/api/xyz'], ['/api/productos/../usuarios'], ['/api/productos/%2e%2e/usuarios'],
            ['/api/productos/%252e%252e/x'], ['/api/productos//x'], ['/api/productos/%5cx'],
            ['/api/productos/a%00b'], ['/api/productos/a%0Ab'],
        ];
    }

    #[DataProvider('rutasInvalidas')]
    public function test_prefijo_desconocido_o_ruta_peligrosa_da_404(string $ruta): void
    {
        $this->respuestaOk();

        $this->assertError($this->como($this->token())->getJson($ruta), 404, 'NO_EXISTE');
        Http::assertNothingSent();
    }

    public function test_metodo_que_no_existe_en_el_recurso_da_405(): void
    {
        $this->respuestaOk();

        $respuesta = $this->como($this->token())->postJson('/api/stock');

        $this->assertError($respuesta, 405, 'METODO_NO_PERMITIDO');
        $respuesta->assertHeader('Allow', 'GET');
        Http::assertNothingSent();
    }

    public function test_conexion_fallida_o_timeout_da_503_sin_reintento(): void
    {
        $llamadas = 0;
        Http::fake(function () use (&$llamadas) {
            $llamadas++;
            throw new ConnectionException('cURL error 28: Operation timed out');
        });

        $respuesta = $this->como($this->token())->getJson('/api/stock');

        $this->assertError($respuesta, 503, 'SERVICIO_NO_DISPONIBLE');
        $respuesta->assertJsonPath('error.mensaje', 'El servicio no responde.');
        $this->assertSame(1, $llamadas);
    }

    public function test_conexion_rechazada_de_verdad_da_503(): void
    {
        // Puerto cerrado en la máquina local: la conexión se rechaza sin esperar
        config(['gateway.servicios.inventario' => 'http://127.0.0.1:1']);

        $this->assertError($this->como($this->token())->getJson('/api/stock'), 503, 'SERVICIO_NO_DISPONIBLE');
    }

    #[DataProvider('tokensDeEjemplo')]
    public function test_token_de_servicio_vacio_o_de_ejemplo_da_503(?string $token): void
    {
        $this->respuestaOk();
        config(['gateway.service_token' => $token]);

        $this->assertError($this->como($this->token())->getJson('/api/stock'), 503, 'SERVICIO_NO_DISPONIBLE');
        Http::assertNothingSent();
    }

    public static function tokensDeEjemplo(): array
    {
        return [[null], [''], ['cambia-este-token']];
    }
}
