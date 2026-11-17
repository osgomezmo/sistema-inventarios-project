<?php

namespace App\Http\Middleware;

use App\Exceptions\ErrorApi;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/** permiso:<codigo>: 403 SIN_PERMISO si el rol del usuario no lo tiene (G9). */
class TienePermiso
{
    public function handle(Request $request, Closure $next, string $codigo): Response
    {
        if (! $request->user()?->tienePermiso($codigo)) {
            throw new ErrorApi('SIN_PERMISO', 'No tienes permiso para esta operación.', 403);
        }

        return $next($request);
    }
}
