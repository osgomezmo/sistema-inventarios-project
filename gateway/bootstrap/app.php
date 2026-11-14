<?php

use Illuminate\Auth\AuthenticationException;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        // La API no redirige a una página de login: responde 401 en JSON
        $middleware->redirectGuestsTo(fn (Request $request) => $request->is('api/*') ? null : '/');
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );

        // Mismo formato de error que los microservicios: {"error": {codigo, mensaje, detalles}}
        $exceptions->render(function (AuthenticationException $e, Request $request) {
            if ($request->is('api/*')) {
                return response()->json(['error' => [
                    'codigo' => 'NO_AUTENTICADO',
                    'mensaje' => 'Token ausente, inválido o vencido.',
                    'detalles' => (object) [],
                ]], 401);
            }
        });
    })->create();
