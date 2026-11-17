const repo = require('../repositories/proveedores.repository');
const { AppError } = require('../utils/errors');
const { leerPaginacion, respuestaPaginada } = require('../utils/paginacion');
const {
  validarIdEntero,
  validarSkuParam,
  validarProveedorCrear,
  validarProveedorActualizar,
  validarContacto,
  validarProductoSuministrado,
} = require('../utils/validadores');

async function listarProveedores(req, res, next) {
  try {
    const { page, perPage } = leerPaginacion(req.query);
    const q = typeof req.query.q === 'string' && req.query.q.trim() ? req.query.q.trim() : null;
    const sku =
      typeof req.query.sku === 'string' && req.query.sku.trim()
        ? req.query.sku.trim().toUpperCase()
        : null;

    let estado = null;
    if (req.query.estado !== undefined && String(req.query.estado).trim() !== '') {
      const est = String(req.query.estado).trim().toUpperCase();
      if (est !== 'ACTIVO' && est !== 'INACTIVO') {
        throw new AppError(422, 'VALIDACION', 'Filtro estado inválido.', {
          estado: ['El parámetro estado debe ser ACTIVO o INACTIVO.'],
        });
      }
      estado = est;
    }

    const { data, total } = await repo.listarProveedores({ q, estado, sku, page, perPage });
    return res.status(200).json(respuestaPaginada(data, page, perPage, total));
  } catch (err) {
    return next(err);
  }
}

async function obtenerProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const proveedor = await repo.obtenerProveedorPorId(idProveedor);
    if (!proveedor) {
      throw new AppError(404, 'NO_EXISTE', 'El proveedor solicitado no existe.');
    }
    return res.status(200).json(proveedor);
  } catch (err) {
    return next(err);
  }
}

async function crearProveedor(req, res, next) {
  try {
    const datos = validarProveedorCrear(req.body);
    const creado = await repo.crearProveedor(datos);
    return res.status(201).json(creado);
  } catch (err) {
    return next(err);
  }
}

async function actualizarProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const datos = validarProveedorActualizar(req.body);
    const actualizado = await repo.actualizarProveedor(idProveedor, datos);
    if (!actualizado) {
      throw new AppError(404, 'NO_EXISTE', 'El proveedor solicitado no existe.');
    }
    return res.status(200).json(actualizado);
  } catch (err) {
    return next(err);
  }
}

async function inactivarProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const actualizado = await repo.cambiarEstadoProveedor(idProveedor, 'INACTIVO');
    return res.status(200).json(actualizado);
  } catch (err) {
    return next(err);
  }
}

async function activarProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const actualizado = await repo.cambiarEstadoProveedor(idProveedor, 'ACTIVO');
    return res.status(200).json(actualizado);
  } catch (err) {
    return next(err);
  }
}

async function crearContacto(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const datos = validarContacto(req.body);
    const creado = await repo.crearContacto(idProveedor, datos);
    return res.status(201).json(creado);
  } catch (err) {
    return next(err);
  }
}

async function actualizarContacto(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const idContacto = validarIdEntero(req.params.id_contacto, 'id_contacto');
    const datos = validarContacto(req.body);
    const actualizado = await repo.actualizarContacto(idProveedor, idContacto, datos);
    if (!actualizado) {
      throw new AppError(404, 'NO_EXISTE', 'El contacto solicitado no existe.');
    }
    return res.status(200).json(actualizado);
  } catch (err) {
    return next(err);
  }
}

async function eliminarContacto(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const idContacto = validarIdEntero(req.params.id_contacto, 'id_contacto');
    const eliminado = await repo.eliminarContacto(idProveedor, idContacto);
    if (!eliminado) {
      throw new AppError(404, 'NO_EXISTE', 'El contacto solicitado no existe.');
    }
    return res.status(204).send();
  } catch (err) {
    return next(err);
  }
}

async function listarProductosProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const productos = await repo.listarProductosProveedor(idProveedor);
    return res.status(200).json(productos);
  } catch (err) {
    return next(err);
  }
}

async function upsertProductoProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const sku = validarSkuParam(req.params.sku);
    const datos = validarProductoSuministrado(req.body);
    const producto = await repo.upsertProductoProveedor(idProveedor, sku, datos);
    return res.status(200).json(producto);
  } catch (err) {
    return next(err);
  }
}

async function eliminarProductoProveedor(req, res, next) {
  try {
    const idProveedor = validarIdEntero(req.params.id, 'id');
    const sku = validarSkuParam(req.params.sku);
    const eliminado = await repo.eliminarProductoProveedor(idProveedor, sku);
    if (!eliminado) {
      throw new AppError(404, 'NO_EXISTE', 'El producto suministrado no existe para este proveedor.');
    }
    return res.status(204).send();
  } catch (err) {
    return next(err);
  }
}

module.exports = {
  listarProveedores,
  obtenerProveedor,
  crearProveedor,
  actualizarProveedor,
  inactivarProveedor,
  activarProveedor,
  crearContacto,
  actualizarContacto,
  eliminarContacto,
  listarProductosProveedor,
  upsertProductoProveedor,
  eliminarProductoProveedor,
};
