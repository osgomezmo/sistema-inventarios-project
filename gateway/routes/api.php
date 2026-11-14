<?php

use App\Http\Controllers\AuthController;
use Illuminate\Support\Facades\Route;

// Rutas de la API pública. El reenvío a los microservicios se agrega más adelante.

Route::post('/auth/login', [AuthController::class, 'login'])->middleware('throttle:login');

Route::middleware(['auth:sanctum', 'activo'])->group(function () {
    Route::post('/auth/logout', [AuthController::class, 'logout']);
    Route::get('/auth/me', [AuthController::class, 'me']);
    Route::put('/auth/password', [AuthController::class, 'cambiarPassword']);
});
