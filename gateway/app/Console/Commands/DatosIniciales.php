<?php

namespace App\Console\Commands;

use App\Models\Rol;
use Database\Seeders\AdminInicialSeeder;
use Database\Seeders\RolesYPermisosSeeder;
use Database\Seeders\UsuariosInicialesSeeder;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Siembra los datos iniciales solo si la base no tiene roles (D51); lo usa
 * entrypoint.sh al arrancar. El administrador se crea solo si ADMIN_EMAIL,
 * ADMIN_NOMBRE y ADMIN_PASSWORD existen; si faltan, sigue y lo registra.
 */
class DatosIniciales extends Command
{
    protected $signature = 'gateway:datos-iniciales';

    protected $description = 'Siembra roles, administrador y usuarios iniciales si la base no tiene roles';

    public const AVISO_SIN_ADMIN = 'Faltan ADMIN_EMAIL, ADMIN_NOMBRE o ADMIN_PASSWORD: no se crea el administrador inicial.';

    public function handle(): int
    {
        if (Rol::query()->exists()) {
            $this->info('La base ya tiene roles: no se siembran datos iniciales.');

            return self::SUCCESS;
        }

        DB::transaction(function () {
            $this->callSilent('db:seed', ['--class' => RolesYPermisosSeeder::class, '--force' => true]);

            $admin = config('gateway.admin_inicial');
            if (collect($admin)->contains(fn ($valor) => blank($valor))) {
                Log::warning(self::AVISO_SIN_ADMIN);
                $this->warn(self::AVISO_SIN_ADMIN);
            } else {
                $this->callSilent('db:seed', ['--class' => AdminInicialSeeder::class, '--force' => true]);
            }

            $this->call('db:seed', ['--class' => UsuariosInicialesSeeder::class, '--force' => true]);
        });

        $this->info('Datos iniciales sembrados.');

        return self::SUCCESS;
    }
}
