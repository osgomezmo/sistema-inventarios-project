<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

/**
 * X-Correlation-Id de /api/*: se conserva el del cliente si es seguro (hasta 64
 * caracteres [A-Za-z0-9-]); si no, se genera un UUID v4. Se devuelve en toda
 * respuesta, incluidos los errores (G10).
 */
class IdCorrelacion
{
    public const ATRIBUTO = 'id_correlacion';

    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->is('api/*')) {
            return $next($request);
        }

        $recibido = (string) $request->headers->get('X-Correlation-Id', '');
        $id = preg_match('/^[A-Za-z0-9-]{1,64}$/', $recibido) ? $recibido : (string) Str::uuid();
        $request->attributes->set(self::ATRIBUTO, $id);

        $respuesta = $next($request);
        $respuesta->headers->set('X-Correlation-Id', $id);

        return $respuesta;
    }
}
