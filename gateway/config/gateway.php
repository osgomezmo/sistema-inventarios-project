<?php

// Configuración propia del gateway. Los valores llegan por variables de entorno;
// ninguna contraseña real vive en el repositorio (G5).
return [

    // Administrador inicial que crea AdminInicialSeeder
    'admin_inicial' => [
        'email' => env('ADMIN_EMAIL'),
        'nombre' => env('ADMIN_NOMBRE'),
        'password' => env('ADMIN_PASSWORD'),
    ],

];
