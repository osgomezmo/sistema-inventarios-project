<?php

namespace Database\Seeders;

use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    use WithoutModelEvents;

    /**
     * Roles, permisos, administrador inicial y usuarios iniciales del gateway.
     */
    public function run(): void
    {
        $this->call([
            RolesYPermisosSeeder::class,
            AdminInicialSeeder::class,
            UsuariosInicialesSeeder::class,
        ]);
    }
}
