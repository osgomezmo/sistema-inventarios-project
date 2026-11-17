const { Router } = require('express');
const ctrl = require('../controllers/proveedores.controller');
const { requerirRoles } = require('../utils/roles');

const router = Router();

const ROLES_LECTURA = ['admin', 'jefe_bodega', 'compras', 'gerente'];
const ROLES_ESCRITURA = ['admin', 'compras'];

// Consulta general y detalle de proveedores
router.get('/', requerirRoles(ROLES_LECTURA, { permitirInterno: true }), ctrl.listarProveedores);
router.get('/:id', requerirRoles(ROLES_LECTURA, { permitirInterno: true }), ctrl.obtenerProveedor);

// Alta, actualización e inactivación/activación de proveedores
router.post('/', requerirRoles(ROLES_ESCRITURA), ctrl.crearProveedor);
router.put('/:id', requerirRoles(ROLES_ESCRITURA), ctrl.actualizarProveedor);
router.post('/:id/inactivar', requerirRoles(ROLES_ESCRITURA), ctrl.inactivarProveedor);
router.post('/:id/activar', requerirRoles(ROLES_ESCRITURA), ctrl.activarProveedor);

// Contactos de un proveedor
router.post('/:id/contactos', requerirRoles(ROLES_ESCRITURA), ctrl.crearContacto);
router.put('/:id/contactos/:id_contacto', requerirRoles(ROLES_ESCRITURA), ctrl.actualizarContacto);
router.delete('/:id/contactos/:id_contacto', requerirRoles(ROLES_ESCRITURA), ctrl.eliminarContacto);

// Productos suministrados por el proveedor (entidad débil ProductoSuministrado)
router.get('/:id/productos', requerirRoles(ROLES_LECTURA, { permitirInterno: true }), ctrl.listarProductosProveedor);
router.put('/:id/productos/:sku', requerirRoles(ROLES_ESCRITURA), ctrl.upsertProductoProveedor);
router.delete('/:id/productos/:sku', requerirRoles(ROLES_ESCRITURA), ctrl.eliminarProductoProveedor);

module.exports = router;
