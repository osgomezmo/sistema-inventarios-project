<?php

namespace App\Support;

use App\Models\User;

/** Formas públicas de los recursos del gateway (G7). */
class Serializador
{
    /** {id, nombre, email, estado, rol: {codigo, nombre}}; nunca la contraseña ni tokens. */
    public static function usuario(User $usuario): array
    {
        $rol = $usuario->rol;

        return [
            'id' => $usuario->id,
            'nombre' => $usuario->name,
            'email' => $usuario->email,
            'estado' => $usuario->estado,
            'rol' => $rol ? ['codigo' => $rol->codigo, 'nombre' => $rol->nombre] : null,
        ];
    }
}
