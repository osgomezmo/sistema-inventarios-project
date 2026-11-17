<?php

namespace App\Http\Controllers;

use App\Exceptions\ErrorApi;
use App\Http\Middleware\IdCorrelacion;
use App\Services\ProxyServicios;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response as RespuestaHttp;

/**
 * GET /api/productos?id_proveedor={id}: única composición del gateway (4.2, G11).
 * Pide los SKU a ms-proveedores y luego consulta ms-productos con ?skus.
 */
class ComposicionProductosController extends Controller
{
    /** ms-productos acepta como máximo 100 SKU en ?skus. */
    private const MAX_SKUS = 100;

    public function __construct(private readonly ProxyServicios $proxy) {}

    public function __invoke(Request $request): RespuestaHttp
    {
        $idProveedor = (string) $request->query('id_proveedor');
        if (! preg_match('/^[1-9][0-9]{0,9}$/', $idProveedor)) {
            throw new ErrorApi('VALIDACION', 'Revisa los campos enviados.', 422,
                ['id_proveedor' => ['Debe ser un número entero positivo.']]);
        }

        $usuario = $request->user();
        if (! $usuario->tienePermiso('productos.ver') || ! $usuario->tienePermiso('proveedores.ver')) {
            throw new ErrorApi('SIN_PERMISO', 'No tienes permiso para esta operación.', 403);
        }

        $correlacion = $request->attributes->get(IdCorrelacion::ATRIBUTO);
        $proveedor = $this->proxy->enviar(
            'proveedores', 'GET', "proveedores/{$idProveedor}/productos", null, $usuario, $correlacion);

        if ($proveedor->status() === 404) {
            throw new ErrorApi('NO_EXISTE', 'El proveedor no existe.', 404);
        }
        if (! $proveedor->successful()) {
            return ProxyController::devolver($proveedor);
        }

        // ms-proveedores responde un arreglo; se acepta también {data: [...]}
        $filas = $proveedor->json('data') ?? $proveedor->json() ?? [];
        $skus = array_values(array_unique(array_filter(array_map(
            fn ($fila) => is_array($fila) ? ($fila['sku'] ?? null) : null, (array) $filas,
        ), 'is_string')));

        $parametros = $request->query();
        unset($parametros['id_proveedor']);

        if ($skus === []) {
            return response()->json(['data' => [], 'meta' => [
                'page' => $this->entero($parametros['page'] ?? null, 1),
                'per_page' => $this->entero($parametros['per_page'] ?? null, 20),
                'total' => 0,
            ]]);
        }
        if (count($skus) > self::MAX_SKUS) {
            throw new ErrorApi('VALIDACION', 'Revisa los campos enviados.', 422, ['id_proveedor' => [
                'El proveedor tiene más de '.self::MAX_SKUS.' productos; la consulta por proveedor no los admite.',
            ]]);
        }

        $parametros['skus'] = implode(',', $skus);
        $productos = $this->proxy->enviar(
            'productos', 'GET', 'productos', http_build_query($parametros, '', '&', PHP_QUERY_RFC3986),
            $usuario, $correlacion);

        return ProxyController::devolver($productos);
    }

    private function entero(mixed $valor, int $porDefecto): int
    {
        return is_string($valor) && preg_match('/^[1-9][0-9]{0,5}$/', $valor) ? (int) $valor : $porDefecto;
    }
}
