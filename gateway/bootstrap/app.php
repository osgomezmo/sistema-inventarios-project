<?php

use App\Exceptions\ManejadorErroresApi;
use App\Http\Middleware\UsuarioActivo;
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

        // Un usuario INACTIVO no puede seguir usando sus tokens (G8)
        $middleware->alias(['activo' => UsuarioActivo::class]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );

        // Todos los errores de /api/* con el formato {"error": {codigo, mensaje, detalles}} (G7)
        $exceptions->render(function (Throwable $e, Request $request) {
            if ($request->is('api/*')) {
                return ManejadorErroresApi::responder($e);
            }
        });
    })->create();
