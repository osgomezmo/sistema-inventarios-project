<?php

namespace App\Http\Middleware;

use App\Exceptions\ErrorApi;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Revisa el estado del usuario en cada petición autenticada: un usuario
 * INACTIVO no puede seguir usando tokens que aún no han vencido (G8).
 */
class UsuarioActivo
{
    public function handle(Request $request, Closure $next): Response
    {
        $usuario = $request->user();
        if ($usuario !== null && $usuario->estado !== 'ACTIVO') {
            throw new ErrorApi('USUARIO_INACTIVO', 'El usuario está inactivo.', 403);
        }

        return $next($request);
    }
}
