<?php

namespace Database\Seeders;

use App\Models\Rol;
use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Log;
use RuntimeException;

/**
 * Crea un usuario inicial por rol (jefe_bodega, compras y gerente), todos con la
 * contraseña de USUARIOS_INICIALES_PASSWORD (D51). Si la variable está vacía, no
 * crea ninguno y lo registra, sin fallar. Los correos que ya existen se respetan.
 */
class UsuariosInicialesSeeder extends Seeder
{
    /** Correo => [nombre, código del rol] */
    public const USUARIOS = [
        'jefe.bodega@inventario.local' => ['Jefe de bodega', 'jefe_bodega'],
        'compras@inventario.local' => ['Analista de compras', 'compras'],
        'gerente@inventario.local' => ['Gerente', 'gerente'],
    ];

    public const AVISO_SIN_PASSWORD = 'USUARIOS_INICIALES_PASSWORD está vacía: no se crean los usuarios iniciales.';

    public function run(): void
    {
        $password = config('gateway.usuarios_iniciales_password');
        if (blank($password)) {
            Log::warning(self::AVISO_SIN_PASSWORD);
            $this->command?->warn(self::AVISO_SIN_PASSWORD);

            return;
        }

        foreach (self::USUARIOS as $email => [$nombre, $codigoRol]) {
            if (User::where('email', $email)->exists()) {
                continue;
            }
            $rol = Rol::where('codigo', $codigoRol)->first()
                ?? throw new RuntimeException("Falta el rol {$codigoRol}: corre primero RolesYPermisosSeeder.");

            User::create([
                'name' => $nombre,
                'email' => $email,
                'password' => $password,  // el modelo la guarda hasheada
                'id_rol' => $rol->id_rol,
            ]);
        }
    }
}
