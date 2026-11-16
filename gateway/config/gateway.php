<?php

// Configuración propia del gateway. Los valores llegan por variables de entorno;
// ninguna contraseña ni token real vive en el repositorio (G5).

// Métodos de escritura que se agrupan como "otros métodos" en la matriz 4.3
$escritura = ['POST', 'PUT', 'PATCH', 'DELETE'];

return [

    // Administrador inicial que crea AdminInicialSeeder
    'admin_inicial' => [
        'email' => env('ADMIN_EMAIL'),
        'nombre' => env('ADMIN_NOMBRE'),
        'password' => env('ADMIN_PASSWORD'),
    ],

    // Contraseña común de los usuarios iniciales por rol (UsuariosInicialesSeeder)
    'usuarios_iniciales_password' => env('USUARIOS_INICIALES_PASSWORD'),

    // Token compartido con todos los microservicios (G2)
    'service_token' => env('SERVICE_TOKEN'),

    // Segundos máximos de espera por servicio; sin reintentos (G10)
    'timeout' => (float) env('SERVICIOS_TIMEOUT', 5),

    // URL base de cada microservicio en la red redapi (G3)
    'servicios' => [
        'productos' => env('PRODUCTOS_URL', 'http://ms-productos:5000'),
        'inventario' => env('INVENTARIO_URL', 'http://ms-inventario:5000'),
        'compras' => env('COMPRAS_URL', 'http://ms-compras:5000'),
        'proveedores' => env('PROVEEDORES_URL', 'http://ms-proveedores:3001'),
        'notificaciones' => env('NOTIFICACIONES_URL', 'http://ms-notificaciones:5006'),
        'reportes' => env('REPORTES_URL', 'http://ms-reportes:5000'),
    ],

    // Primer segmento de /api/{ruta} => servicio (4.2)
    'prefijos' => [
        'categorias' => 'productos',
        'productos' => 'productos',
        'bodegas' => 'inventario',
        'stock' => 'inventario',
        'movimientos' => 'inventario',
        'kardex' => 'inventario',
        'traslados' => 'inventario',
        'devoluciones-cliente' => 'inventario',
        'proveedores' => 'proveedores',
        'ordenes-compra' => 'compras',
        'devoluciones-proveedor' => 'compras',
        'reportes' => 'reportes',
        'dashboard' => 'reportes',
        'notificaciones' => 'notificaciones',
        'dispositivos' => 'notificaciones',
    ],

    /*
     * Matriz 4.3 aplicada a las rutas internas (sin /api): [métodos, patrón, permiso].
     * La primera regla que coincide decide. Permiso null = cualquier usuario autenticado.
     * Una ruta que solo coincide con otros métodos responde 405.
     */
    'permisos' => [
        [['GET'], '#^(categorias|productos)(/.*)?$#', 'productos.ver'],
        [$escritura, '#^(categorias|productos)(/.*)?$#', 'productos.gestionar'],

        [['GET'], '#^bodegas(/.*)?$#', 'bodegas.ver'],
        [$escritura, '#^bodegas(/.*)?$#', 'bodegas.gestionar'],
        [['GET'], '#^stock(/.*)?$#', 'stock.ver'],
        [['GET'], '#^(movimientos|kardex|traslados)(/.*)?$#', 'movimientos.ver'],
        [['POST'], '#^(movimientos|traslados)$#', 'movimientos.gestionar'],
        [['GET'], '#^devoluciones-cliente(/.*)?$#', 'devoluciones_cliente.ver'],
        [['POST'], '#^devoluciones-cliente$#', 'devoluciones_cliente.gestionar'],

        [['GET'], '#^proveedores(/.*)?$#', 'proveedores.ver'],
        [$escritura, '#^proveedores(/.*)?$#', 'proveedores.gestionar'],

        [['GET'], '#^ordenes-compra(/.*)?$#', 'ordenes.ver'],
        [['POST'], '#^ordenes-compra$#', 'ordenes.gestionar'],
        [['PUT'], '#^ordenes-compra/[^/]+$#', 'ordenes.gestionar'],
        [['POST'], '#^ordenes-compra/[^/]+/(aprobar|anular)$#', 'ordenes.aprobar'],
        [['POST'], '#^ordenes-compra/[^/]+/recepciones$#', 'recepciones.registrar'],
        [['POST'], '#^ordenes-compra/[^/]+/devoluciones$#', 'devoluciones_proveedor.registrar'],
        [['GET'], '#^devoluciones-proveedor(/.*)?$#', 'devoluciones_proveedor.registrar'],

        [['GET'], '#^(reportes|dashboard)(/.*)?$#', 'reportes.ver'],

        [['GET', ...$escritura], '#^(notificaciones|dispositivos)(/.*)?$#', null],
    ],

];
