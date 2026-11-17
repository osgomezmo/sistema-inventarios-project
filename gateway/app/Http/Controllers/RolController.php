<?php

namespace App\Http\Controllers;

use App\Models\Rol;
use Illuminate\Http\JsonResponse;

/** GET /api/roles: cada rol con los códigos de sus permisos (G9). */
class RolController extends Controller
{
    public function listar(): JsonResponse
    {
        $roles = Rol::with(['permisos' => fn ($q) => $q->orderBy('codigo')])->orderBy('id_rol')->get();

        return response()->json($roles->map(fn (Rol $rol) => [
            'id_rol' => $rol->id_rol,
            'codigo' => $rol->codigo,
            'nombre' => $rol->nombre,
            'permisos' => $rol->permisos->pluck('codigo')->all(),
        ])->all());
    }
}
