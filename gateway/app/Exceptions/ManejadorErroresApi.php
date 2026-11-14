<?php

namespace App\Exceptions;

use Illuminate\Auth\AuthenticationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;
use Throwable;

/**
 * Convierte cualquier excepción de /api/* al formato de error del contrato (G7).
 * Un 500 nunca revela detalles, aunque APP_DEBUG esté activo.
 */
class ManejadorErroresApi
{
    /** Código y mensaje por estado HTTP. */
    private const POR_ESTADO = [
        400 => ['PETICION_INVALIDA', 'La petición está mal formada.'],
        401 => ['NO_AUTENTICADO', 'Token ausente, inválido o vencido.'],
        403 => ['SIN_PERMISO', 'No tienes permiso para esta operación.'],
        404 => ['NO_EXISTE', 'El recurso no existe.'],
        405 => ['METODO_NO_PERMITIDO', 'El método no está permitido en esta ruta.'],
        409 => ['CONFLICTO', 'La operación entra en conflicto con el estado actual.'],
        422 => ['VALIDACION', 'Revisa los campos enviados.'],
        429 => ['DEMASIADAS_PETICIONES', 'Demasiadas peticiones; espera un momento.'],
        503 => ['SERVICIO_NO_DISPONIBLE', 'Un servicio del que depende no responde.'],
    ];

    public static function responder(Throwable $e): JsonResponse
    {
        if ($e instanceof ErrorApi) {
            return self::json($e->codigo, $e->getMessage(), $e->status, $e->detalles);
        }
        if ($e instanceof AuthenticationException) {
            return self::estandar(401);
        }
        if ($e instanceof ValidationException) {
            return self::estandar(422, $e->errors());
        }
        if ($e instanceof HttpExceptionInterface) {
            $status = $e->getStatusCode();
            $respuesta = isset(self::POR_ESTADO[$status])
                ? self::estandar($status)
                : self::json('ERROR_HTTP', 'La petición no se pudo procesar.', $status);

            // Conserva cabeceras útiles como Allow o Retry-After
            return $respuesta->withHeaders($e->getHeaders());
        }

        return self::json('ERROR_INTERNO', 'Ocurrió un error interno.', 500);
    }

    public static function estandar(int $status, array $detalles = []): JsonResponse
    {
        [$codigo, $mensaje] = self::POR_ESTADO[$status];

        return self::json($codigo, $mensaje, $status, $detalles);
    }

    public static function json(string $codigo, string $mensaje, int $status, array $detalles = []): JsonResponse
    {
        return response()->json(['error' => [
            'codigo' => $codigo,
            'mensaje' => $mensaje,
            // {} y no [] cuando no hay detalles
            'detalles' => $detalles ?: (object) [],
        ]], $status);
    }
}
