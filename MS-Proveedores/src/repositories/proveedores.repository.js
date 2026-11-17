const { ejecutarConsulta, conTransaccion } = require('../config/db');
const { AppError } = require('../utils/errors');

function formatearContacto(row) {
  return {
    id_contacto: Number(row.id_contacto),
    nombre: row.nombre,
    cargo: row.cargo,
    telefono: row.telefono,
    email: row.email,
  };
}

function formatearProveedor(row, contactos = []) {
  return {
    id_proveedor: Number(row.id_proveedor),
    nit: row.nit,
    razon_social: row.razon_social,
    telefono: row.telefono,
    email: row.email,
    direccion: row.direccion,
    estado: row.estado,
    contactos,
  };
}

function formatearProductoSuministrado(row) {
  return {
    sku: row.sku,
    precio_compra: Number(Number(row.precio_compra).toFixed(2)),
    dias_entrega: Number(row.dias_entrega),
    estado: row.estado,
  };
}

async function verificarProveedorExiste(idProveedor) {
  const rows = await ejecutarConsulta(
    'SELECT id_proveedor FROM proveedores WHERE id_proveedor = ?',
    [idProveedor]
  );
  if (rows.length === 0) {
    throw new AppError(404, 'NO_EXISTE', 'El proveedor solicitado no existe.');
  }
}

async function obtenerContactosPorProveedores(ids) {
  if (ids.length === 0) return new Map();

  const rows = await ejecutarConsulta(
    `SELECT id_contacto, id_proveedor, nombre, cargo, telefono, email
     FROM contactos
     WHERE id_proveedor IN (?)
     ORDER BY id_contacto ASC`,
    [ids]
  );

  const mapa = new Map();
  for (const row of rows) {
    const lista = mapa.get(row.id_proveedor) || [];
    lista.push(formatearContacto(row));
    mapa.set(row.id_proveedor, lista);
  }
  return mapa;
}

async function listarProveedores({ q, estado, sku, page, perPage }) {
  const condiciones = [];
  const params = [];

  if (q) {
    const patron = `%${q}%`;
    condiciones.push('(p.nit LIKE ? OR p.razon_social LIKE ?)');
    params.push(patron, patron);
  }

  if (estado) {
    condiciones.push('p.estado = ?');
    params.push(estado);
  }

  if (sku) {
    condiciones.push(
      "EXISTS (SELECT 1 FROM productos_suministrados ps WHERE ps.id_proveedor = p.id_proveedor AND ps.sku = ? AND ps.estado = 'ACTIVO')"
    );
    params.push(sku);
  }

  const whereSql = condiciones.length > 0 ? `WHERE ${condiciones.join(' AND ')}` : '';
  const offset = (page - 1) * perPage;

  const totalRows = await ejecutarConsulta(
    `SELECT COUNT(*) AS total FROM proveedores p ${whereSql}`,
    params
  );
  const total = Number(totalRows[0].total || 0);

  const filas = await ejecutarConsulta(
    `SELECT p.id_proveedor, p.nit, p.razon_social, p.telefono, p.email, p.direccion, p.estado
     FROM proveedores p
     ${whereSql}
     ORDER BY p.id_proveedor ASC
     LIMIT ? OFFSET ?`,
    [...params, perPage, offset]
  );

  const ids = filas.map((f) => f.id_proveedor);
  const contactosMapa = await obtenerContactosPorProveedores(ids);

  const data = filas.map((fila) =>
    formatearProveedor(fila, contactosMapa.get(fila.id_proveedor) || [])
  );

  return { data, total };
}

async function obtenerProveedorPorId(idProveedor) {
  const rows = await ejecutarConsulta(
    `SELECT id_proveedor, nit, razon_social, telefono, email, direccion, estado
     FROM proveedores
     WHERE id_proveedor = ?`,
    [idProveedor]
  );

  if (rows.length === 0) {
    return null;
  }

  const contactosRows = await ejecutarConsulta(
    `SELECT id_contacto, id_proveedor, nombre, cargo, telefono, email
     FROM contactos
     WHERE id_proveedor = ?
     ORDER BY id_contacto ASC`,
    [idProveedor]
  );

  return formatearProveedor(rows[0], contactosRows.map(formatearContacto));
}

async function crearProveedor({ nit, razon_social, telefono, email, direccion, contactos = [], productos = [] }) {
  try {
    if (contactos.length === 0 && productos.length === 0) {
      const resultado = await ejecutarConsulta(
        `INSERT INTO proveedores (nit, razon_social, telefono, email, direccion, estado)
         VALUES (?, ?, ?, ?, ?, 'ACTIVO')`,
        [nit, razon_social, telefono, email, direccion]
      );
      return await obtenerProveedorPorId(resultado.insertId);
    }

    const idProveedor = await conTransaccion(async (conexion) => {
      const [resProv] = await conexion.query(
        `INSERT INTO proveedores (nit, razon_social, telefono, email, direccion, estado)
         VALUES (?, ?, ?, ?, ?, 'ACTIVO')`,
        [nit, razon_social, telefono, email, direccion]
      );
      const nuevoId = resProv.insertId;

      for (const ct of contactos) {
        await conexion.query(
          `INSERT INTO contactos (id_proveedor, nombre, cargo, telefono, email)
           VALUES (?, ?, ?, ?, ?)`,
          [nuevoId, ct.nombre, ct.cargo, ct.telefono, ct.email]
        );
      }

      for (const pr of productos) {
        await conexion.query(
          `INSERT INTO productos_suministrados (id_proveedor, sku, precio_compra, dias_entrega, estado, actualizado_en)
           VALUES (?, ?, ?, ?, ?, UTC_TIMESTAMP())
           ON DUPLICATE KEY UPDATE
             precio_compra = VALUES(precio_compra),
             dias_entrega = VALUES(dias_entrega),
             estado = VALUES(estado),
             actualizado_en = UTC_TIMESTAMP()`,
          [nuevoId, pr.sku, pr.precio_compra, pr.dias_entrega, pr.estado || 'ACTIVO']
        );
      }

      return nuevoId;
    });

    return await obtenerProveedorPorId(idProveedor);
  } catch (err) {
    if (err && err.code === 'ER_DUP_ENTRY') {
      throw new AppError(409, 'NIT_DUPLICADO', 'Ya existe un proveedor con ese NIT.', {
        nit: ['El NIT ya está registrado.'],
      });
    }
    throw err;
  }
}

async function actualizarProveedor(idProveedor, { razon_social, telefono, email, direccion }) {
  const resultado = await ejecutarConsulta(
    `UPDATE proveedores
     SET razon_social = ?, telefono = ?, email = ?, direccion = ?, actualizado_en = UTC_TIMESTAMP()
     WHERE id_proveedor = ?`,
    [razon_social, telefono, email, direccion, idProveedor]
  );

  if (resultado.affectedRows === 0) {
    return null;
  }

  return await obtenerProveedorPorId(idProveedor);
}

async function cambiarEstadoProveedor(idProveedor, nuevoEstado) {
  await verificarProveedorExiste(idProveedor);
  await ejecutarConsulta(
    `UPDATE proveedores
     SET estado = ?, actualizado_en = UTC_TIMESTAMP()
     WHERE id_proveedor = ?`,
    [nuevoEstado, idProveedor]
  );
  return await obtenerProveedorPorId(idProveedor);
}

async function crearContacto(idProveedor, { nombre, cargo, telefono, email }) {
  await verificarProveedorExiste(idProveedor);

  const resultado = await ejecutarConsulta(
    `INSERT INTO contactos (id_proveedor, nombre, cargo, telefono, email)
     VALUES (?, ?, ?, ?, ?)`,
    [idProveedor, nombre, cargo, telefono, email]
  );

  const rows = await ejecutarConsulta(
    `SELECT id_contacto, nombre, cargo, telefono, email
     FROM contactos
     WHERE id_contacto = ?`,
    [resultado.insertId]
  );

  return formatearContacto(rows[0]);
}

async function actualizarContacto(idProveedor, idContacto, { nombre, cargo, telefono, email }) {
  await verificarProveedorExiste(idProveedor);

  const resultado = await ejecutarConsulta(
    `UPDATE contactos
     SET nombre = ?, cargo = ?, telefono = ?, email = ?
     WHERE id_contacto = ? AND id_proveedor = ?`,
    [nombre, cargo, telefono, email, idContacto, idProveedor]
  );

  if (resultado.affectedRows === 0) {
    return null;
  }

  const rows = await ejecutarConsulta(
    `SELECT id_contacto, nombre, cargo, telefono, email
     FROM contactos
     WHERE id_contacto = ? AND id_proveedor = ?`,
    [idContacto, idProveedor]
  );

  return formatearContacto(rows[0]);
}

async function eliminarContacto(idProveedor, idContacto) {
  await verificarProveedorExiste(idProveedor);

  const resultado = await ejecutarConsulta(
    'DELETE FROM contactos WHERE id_contacto = ? AND id_proveedor = ?',
    [idContacto, idProveedor]
  );

  return resultado.affectedRows > 0;
}

async function listarProductosProveedor(idProveedor) {
  await verificarProveedorExiste(idProveedor);

  const rows = await ejecutarConsulta(
    `SELECT sku, precio_compra, dias_entrega, estado
     FROM productos_suministrados
     WHERE id_proveedor = ?
     ORDER BY sku ASC`,
    [idProveedor]
  );

  return rows.map(formatearProductoSuministrado);
}

async function upsertProductoProveedor(idProveedor, sku, { precio_compra, dias_entrega, estado }) {
  return await conTransaccion(async (conexion) => {
    const [provRows] = await conexion.query(
      'SELECT id_proveedor FROM proveedores WHERE id_proveedor = ?',
      [idProveedor]
    );
    if (provRows.length === 0) {
      throw new AppError(404, 'NO_EXISTE', 'El proveedor solicitado no existe.');
    }

    await conexion.query(
      `INSERT INTO productos_suministrados (id_proveedor, sku, precio_compra, dias_entrega, estado, actualizado_en)
       VALUES (?, ?, ?, ?, ?, UTC_TIMESTAMP())
       ON DUPLICATE KEY UPDATE
         precio_compra = VALUES(precio_compra),
         dias_entrega = VALUES(dias_entrega),
         estado = VALUES(estado),
         actualizado_en = UTC_TIMESTAMP()`,
      [idProveedor, sku, precio_compra, dias_entrega, estado]
    );

    const [rows] = await conexion.query(
      `SELECT sku, precio_compra, dias_entrega, estado
       FROM productos_suministrados
       WHERE id_proveedor = ? AND sku = ?`,
      [idProveedor, sku]
    );

    return formatearProductoSuministrado(rows[0]);
  });
}

async function eliminarProductoProveedor(idProveedor, sku) {
  await verificarProveedorExiste(idProveedor);

  const resultado = await ejecutarConsulta(
    'DELETE FROM productos_suministrados WHERE id_proveedor = ? AND sku = ?',
    [idProveedor, sku]
  );

  return resultado.affectedRows > 0;
}

module.exports = {
  listarProveedores,
  obtenerProveedorPorId,
  crearProveedor,
  actualizarProveedor,
  cambiarEstadoProveedor,
  crearContacto,
  actualizarContacto,
  eliminarContacto,
  listarProductosProveedor,
  upsertProductoProveedor,
  eliminarProductoProveedor,
};
