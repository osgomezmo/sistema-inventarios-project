<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table) {
            // Anulable para poder agregar la columna a una tabla existente; la app
            // siempre asigna un rol al crear un usuario.
            $table->foreignId('id_rol')->nullable()->after('password')
                ->constrained('roles', 'id_rol')->restrictOnDelete();
            $table->enum('estado', ['ACTIVO', 'INACTIVO'])->default('ACTIVO')->after('id_rol');
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->dropConstrainedForeignId('id_rol');
            $table->dropColumn('estado');
        });
    }
};
