<?php

namespace Database\Seeders;

use App\Models\Permiso;
use App\Models\Rol;
use Illuminate\Database\Seeder;

/**
 * Roles (G1) y permisos según la matriz 4.3 del contrato. Es idempotente:
 * actualiza por código y deja los permisos de cada rol exactamente como aquí.
 */
class RolesYPermisosSeeder extends Seeder
{
    public const ROLES = [
        'admin' => 'Administrador',
        'jefe_bodega' => 'Jefe de bodega',
        'compras' => 'Compras',
        'gerente' => 'Gerente',
    ];

    /** Permiso => [descripción, roles que lo tienen]. */
    public const PERMISOS = [
        'usuarios.gestionar' => ['Administrar usuarios y roles', ['admin']],
        'productos.ver' => ['Consultar productos y categorías', ['admin', 'jefe_bodega', 'compras', 'gerente']],
        'productos.gestionar' => ['Crear y editar productos y categorías', ['admin']],
        'bodegas.ver' => ['Consultar bodegas', ['admin', 'jefe_bodega', 'compras', 'gerente']],
        'bodegas.gestionar' => ['Crear y editar bodegas', ['admin', 'jefe_bodega']],
        'stock.ver' => ['Consultar saldos', ['admin', 'jefe_bodega', 'compras', 'gerente']],
        'movimientos.ver' => ['Consultar movimientos, kardex y traslados', ['admin', 'jefe_bodega', 'gerente']],
        'movimientos.gestionar' => ['Registrar movimientos, ajustes y traslados', ['admin', 'jefe_bodega']],
        'devoluciones_cliente.ver' => ['Consultar devoluciones de cliente', ['admin', 'jefe_bodega', 'gerente']],
        'devoluciones_cliente.gestionar' => ['Registrar devoluciones de cliente', ['admin', 'jefe_bodega']],
        'proveedores.ver' => ['Consultar proveedores y sus productos', ['admin', 'jefe_bodega', 'compras', 'gerente']],
        'proveedores.gestionar' => ['Crear y editar proveedores y sus productos', ['admin', 'compras']],
        'ordenes.ver' => ['Consultar órdenes de compra', ['admin', 'jefe_bodega', 'compras', 'gerente']],
        'ordenes.gestionar' => ['Crear y editar órdenes de compra', ['admin', 'compras']],
        'ordenes.aprobar' => ['Aprobar y anular órdenes de compra', ['admin', 'gerente']],
        'recepciones.registrar' => ['Recibir mercancía', ['admin', 'jefe_bodega']],
        'devoluciones_proveedor.registrar' => ['Registrar devoluciones a proveedor', ['admin', 'jefe_bodega', 'compras']],
        'reportes.ver' => ['Consultar reportes y dashboard', ['admin', 'jefe_bodega', 'compras', 'gerente']],
    ];

    public function run(): void
    {
        $roles = [];
        foreach (self::ROLES as $codigo => $nombre) {
            $roles[$codigo] = Rol::updateOrCreate(['codigo' => $codigo], ['nombre' => $nombre]);
        }

        $porRol = array_fill_keys(array_keys(self::ROLES), []);
        foreach (self::PERMISOS as $codigo => [$descripcion, $codigosRol]) {
            $permiso = Permiso::updateOrCreate(['codigo' => $codigo], ['descripcion' => $descripcion]);
            foreach ($codigosRol as $codigoRol) {
                $porRol[$codigoRol][] = $permiso->id_permiso;
            }
        }

        foreach ($roles as $codigo => $rol) {
            $rol->permisos()->sync($porRol[$codigo]);
        }
    }
}
