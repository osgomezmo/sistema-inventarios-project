<?php

namespace Database\Seeders;

use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    use WithoutModelEvents;

    /**
     * Roles, permisos y administrador inicial del gateway.
     */
    public function run(): void
    {
        $this->call([
            RolesYPermisosSeeder::class,
            AdminInicialSeeder::class,
        ]);
    }
}
