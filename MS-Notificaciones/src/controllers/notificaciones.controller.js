const storage = require('../repositories/storage');
const { normalizarRol } = require('../utils/roles');
const { AppError } = require('../utils/errors');

/**
 * Consulta el historial de notificaciones con soporte para paginación y filtros.
 * GET /notificaciones
 */
async function listarNotificaciones(req, res, next) {
  try {
    const { page, per_page, leida, rol: queryRol } = req.query;
    const detalles = {};

    let numPage = 1;
    if (page !== undefined) {
      if (!/^\d+$/.test(page) || parseInt(page, 10) < 1) {
        detalles.page = ['El parámetro page debe ser un número entero mayor o igual a 1'];
      } else {
        numPage = parseInt(page, 10);
      }
    }

    let numPerPage = 20;
    if (per_page !== undefined) {
      if (
        !/^\d+$/.test(per_page) ||
        parseInt(per_page, 10) < 1 ||
        parseInt(per_page, 10) > 100
      ) {
        detalles.per_page = ['El parámetro per_page debe ser un número entero entre 1 y 100'];
      } else {
        numPerPage = parseInt(per_page, 10);
      }
    }

    let leidaFiltro = undefined;
    if (leida !== undefined) {
      if (leida !== 'true' && leida !== 'false') {
        detalles.leida = ['El parámetro leida solo puede ser "true" o "false"'];
      } else {
        leidaFiltro = leida === 'true';
      }
    }

    if (Object.keys(detalles).length > 0) {
      throw new AppError(
        422,
        'PARAMETROS_INVALIDOS',
        'Parámetros de consulta o paginación inválidos',
        detalles
      );
    }

    // Regla de roles:
    // Si el usuario es 'admin', puede filtrar opcionalmente por cualquier rol (?rol=) o ver todas si no se envía.
    // Si el usuario tiene otro rol (ej. 'compras', 'jefe_bodega'), solo puede ver las dirigidas a su rol.
    const rolUsuario = req.usuario ? req.usuario.rol : null;
    let rolParaFiltrar = rolUsuario;

    if (rolUsuario === 'admin') {
      rolParaFiltrar = queryRol ? normalizarRol(queryRol) : null;
    }

    const resultado = await storage.listarNotificaciones({
      rol: rolParaFiltrar,
      leida: leidaFiltro,
      page: numPage,
      perPage: numPerPage,
    });

    return res.status(200).json(resultado);
  } catch (error) {
    next(error);
  }
}

/**
 * Marca una notificación específica como leída.
 * POST /notificaciones/:id/leida
 */
async function marcarComoLeida(req, res, next) {
  try {
    const { id } = req.params;
    const usuario = req.usuario;

    const notificacion = await storage.obtenerNotificacionPorId(id);
    if (!notificacion) {
      throw new AppError(404, 'NOTIFICACION_NO_ENCONTRADA', 'La notificación no existe');
    }

    // Autorización: Administrador o usuario cuyo rol coincida con el rol_destino de la alerta
    const esAdmin = usuario && usuario.rol === 'admin';
    const coincideRol = usuario && usuario.rol === notificacion.rol_destino;

    if (!esAdmin && !coincideRol) {
      throw new AppError(403, 'SIN_PERMISO', 'Esta notificación pertenece a otro rol');
    }

    const actualizada = await storage.marcarNotificacionLeida(id);

    return res.status(200).json(actualizada);
  } catch (error) {
    next(error);
  }
}

module.exports = {
  listarNotificaciones,
  marcarComoLeida,
};
