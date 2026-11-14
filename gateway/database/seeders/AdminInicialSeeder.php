<?php

namespace Database\Seeders;

use App\Models\Rol;
use App\Models\User;
use Illuminate\Database\Seeder;
use RuntimeException;

/**
 * Crea el administrador inicial con ADMIN_EMAIL, ADMIN_NOMBRE y ADMIN_PASSWORD
 * del entorno (G5). Si el correo ya existe, no hace nada.
 */
class AdminInicialSeeder extends Seeder
{
    public function run(): void
    {
        $datos = config('gateway.admin_inicial');
        $faltan = array_keys(array_filter($datos, fn ($valor) => blank($valor)));
        if ($faltan) {
            $variables = implode(', ', array_map(fn ($c) => 'ADMIN_'.strtoupper($c), $faltan));
            throw new RuntimeException("No se puede crear el administrador inicial: faltan {$variables} en .env.");
        }

        // El login compara el correo en minúsculas y sin espacios
        $datos['email'] = strtolower(trim($datos['email']));

        if (User::where('email', $datos['email'])->exists()) {
            return;
        }

        $rol = Rol::where('codigo', 'admin')->first()
            ?? throw new RuntimeException('Falta el rol admin: corre primero RolesYPermisosSeeder.');

        User::create([
            'name' => $datos['nombre'],
            'email' => $datos['email'],
            'password' => $datos['password'],  // el modelo la guarda hasheada
            'id_rol' => $rol->id_rol,
        ]);
    }
}
