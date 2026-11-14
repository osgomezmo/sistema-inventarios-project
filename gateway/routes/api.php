<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\RolController;
use App\Http\Controllers\UsuarioController;
use Illuminate\Support\Facades\Route;

// Rutas de la API pública. El reenvío a los microservicios se agrega más adelante.

Route::post('/auth/login', [AuthController::class, 'login'])->middleware('throttle:login');

Route::middleware(['auth:sanctum', 'activo'])->group(function () {
    Route::post('/auth/logout', [AuthController::class, 'logout']);
    Route::get('/auth/me', [AuthController::class, 'me']);
    Route::put('/auth/password', [AuthController::class, 'cambiarPassword']);
});

// Administración de usuarios y roles (G9)
Route::middleware(['auth:sanctum', 'activo', 'permiso:usuarios.gestionar'])->group(function () {
    Route::get('/usuarios', [UsuarioController::class, 'listar']);
    Route::post('/usuarios', [UsuarioController::class, 'crear']);
    Route::get('/usuarios/{id}', [UsuarioController::class, 'ver'])->whereNumber('id');
    Route::put('/usuarios/{id}', [UsuarioController::class, 'editar'])->whereNumber('id');
    Route::post('/usuarios/{id}/inactivar', [UsuarioController::class, 'inactivar'])->whereNumber('id');
    Route::post('/usuarios/{id}/activar', [UsuarioController::class, 'activar'])->whereNumber('id');
    Route::get('/roles', [RolController::class, 'listar']);
});
