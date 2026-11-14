const storage = require('../repositories/storage');
const notificador = require('../services/notificador');
const { AppError } = require('../utils/errors');

/**
 * Registra el token FCM de un dispositivo y lo suscribe al tema de su rol.
 * POST /dispositivos
 */
async function registrarDispositivo(req, res, next) {
  try {
    const { token_fcm, plataforma } = req.body || {};
    const usuario = req.usuario;
    const detalles = {};

    if (!usuario || !usuario.id) {
      detalles.id_usuario = ['El encabezado de usuario (X-User-Id) es requerido'];
    }

    if (!usuario || !usuario.rol) {
      detalles.rol = ['El encabezado de rol de usuario (X-User-Role) es requerido'];
    }

    if (!token_fcm || typeof token_fcm !== 'string' || !token_fcm.trim()) {
      detalles.token_fcm = ['El campo token_fcm es requerido y debe ser un texto no vacío'];
    }

    if (!plataforma || typeof plataforma !== 'string' || !plataforma.trim()) {
      detalles.plataforma = ['El campo plataforma es requerido y debe ser un texto no vacío'];
    }

    if (Object.keys(detalles).length > 0) {
      throw new AppError(
        422,
        'VALIDACION_FALLIDA',
        'Datos de dispositivo inválidos o encabezados de usuario ausentes',
        detalles
      );
    }

    const dispositivoGuardado = await storage.guardarDispositivo({
      id_usuario: usuario.id,
      rol: usuario.rol,
      token_fcm: token_fcm.trim(),
      plataforma: plataforma.trim().toLowerCase(),
    });

    // Suscribir el dispositivo al tema de FCM correspondiente a su rol
    await notificador.suscribirATema(dispositivoGuardado.token_fcm, usuario.rol);

    return res.status(201).json(dispositivoGuardado);
  } catch (error) {
    next(error);
  }
}

/**
 * Elimina el registro de un dispositivo y cancela su suscripción al tema.
 * DELETE /dispositivos/:id
 */
async function eliminarDispositivo(req, res, next) {
  try {
    const { id } = req.params;
    const usuario = req.usuario;

    const dispositivo = await storage.obtenerDispositivoPorId(id);
    if (!dispositivo) {
      throw new AppError(404, 'DISPOSITIVO_NO_ENCONTRADO', 'El dispositivo no existe');
    }

    // Control de autorización: Dueño del dispositivo o Administrador
    const esDuenio = usuario && String(dispositivo.id_usuario) === String(usuario.id);
    const esAdmin = usuario && usuario.rol === 'admin';

    if (!esDuenio && !esAdmin) {
      throw new AppError(403, 'SIN_PERMISO', 'No tienes permiso para eliminar este dispositivo');
    }

    // Cancelar la suscripción en FCM
    await notificador.desuscribirDeTema(dispositivo.token_fcm, dispositivo.rol);

    // Eliminar del almacenamiento
    await storage.eliminarDispositivo(id);

    return res.status(204).send();
  } catch (error) {
    next(error);
  }
}

module.exports = {
  registrarDispositivo,
  eliminarDispositivo,
};
