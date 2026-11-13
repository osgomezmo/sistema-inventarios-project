const { messaging, estaConfigurado } = require('../config/firebase');
const { normalizarRol } = require('../utils/roles');
const { AppError } = require('../utils/errors');

/**
 * Convierte un rol normalizado en el nombre del tema (topic) de Firebase.
 * Ej: 'compras' -> 'rol_compras', 'jefe_bodega' -> 'rol_jefe_de_bodega'
 */
function obtenerNombreTema(rol) {
  const norm = normalizarRol(rol);
  if (norm === 'jefe_bodega') {
    return 'rol_jefe_de_bodega';
  }
  if (norm) {
    return `rol_${norm}`;
  }
  return 'rol_general';
}

/**
 * Interfaz / Servicio de Notificaciones Push.
 * Soporta modo 'console' (para desarrollo local sin Firebase)
 * y modo 'fcm' (con Firebase Cloud Messaging).
 */
class NotificadorService {
  constructor() {
    this.driver = (process.env.PUSH_DRIVER || 'console').toLowerCase();
  }

  /**
   * Suscribe uno o varios tokens FCM a un tema correspondiente al rol.
   * @param {string|string[]} tokenFcm
   * @param {string} rol
   */
  async suscribirATema(tokenFcm, rol) {
    const tema = obtenerNombreTema(rol);
    const tokens = Array.isArray(tokenFcm) ? tokenFcm : [tokenFcm];

    if (this.driver === 'fcm' && estaConfigurado && messaging) {
      try {
        const respuesta = await messaging.subscribeToTopic(tokens, tema);
        return {
          success: true,
          tema,
          successCount: respuesta.successCount,
          failureCount: respuesta.failureCount,
          errores: respuesta.errors || [],
        };
      } catch (err) {
        console.error(`[FCM] Error suscribiendo a tema ${tema}:`, err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error al suscribir dispositivo en FCM', {
          original: err.message,
        });
      }
    }

    // Modo consola (local / mock)
    console.log(
      `[FCM-CONSOLE] Suscripción a tema: "${tema}" | Rol: "${rol}" | Tokens: ${JSON.stringify(tokens)}`
    );
    return {
      success: true,
      simulado: true,
      tema,
      successCount: tokens.length,
      failureCount: 0,
    };
  }

  /**
   * Desuscribe uno o varios tokens FCM del tema correspondiente al rol.
   * @param {string|string[]} tokenFcm
   * @param {string} rol
   */
  async desuscribirDeTema(tokenFcm, rol) {
    const tema = obtenerNombreTema(rol);
    const tokens = Array.isArray(tokenFcm) ? tokenFcm : [tokenFcm];

    if (this.driver === 'fcm' && estaConfigurado && messaging) {
      try {
        const respuesta = await messaging.unsubscribeFromTopic(tokens, tema);
        return {
          success: true,
          tema,
          successCount: respuesta.successCount,
          failureCount: respuesta.failureCount,
          errores: respuesta.errors || [],
        };
      } catch (err) {
        console.error(`[FCM] Error desuscribiendo de tema ${tema}:`, err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error al desuscribir dispositivo en FCM', {
          original: err.message,
        });
      }
    }

    // Modo consola (local / mock)
    console.log(
      `[FCM-CONSOLE] Desuscripción de tema: "${tema}" | Rol: "${rol}" | Tokens: ${JSON.stringify(tokens)}`
    );
    return {
      success: true,
      simulado: true,
      tema,
      successCount: tokens.length,
      failureCount: 0,
    };
  }

  /**
   * Envía un mensaje push al tema asociado a un rol.
   * @param {string} rol
   * @param {string} titulo
   * @param {string} mensaje
   * @param {object} datos
   */
  async enviarPushATema(rol, titulo, mensaje, datos = {}) {
    const tema = obtenerNombreTema(rol);

    if (this.driver === 'fcm' && estaConfigurado && messaging) {
      try {
        // FCM exige que todos los valores del objeto 'data' sean strings
        const stringifiedData = {};
        if (datos && typeof datos === 'object') {
          for (const [clave, valor] of Object.entries(datos)) {
            stringifiedData[clave] = typeof valor === 'object' ? JSON.stringify(valor) : String(valor);
          }
        }

        const payload = {
          topic: tema,
          notification: {
            title: titulo,
            body: mensaje,
          },
          data: stringifiedData,
        };

        const messageId = await messaging.send(payload);
        return {
          success: true,
          tema,
          messageId,
        };
      } catch (err) {
        console.error(`[FCM] Error enviando push a tema ${tema}:`, err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error al enviar notificación push en FCM', {
          original: err.message,
        });
      }
    }

    // Modo consola (local / mock)
    console.log(
      `[FCM-CONSOLE] Envío push al tema "${tema}":\n` +
      `  - Título: ${titulo}\n` +
      `  - Mensaje: ${mensaje}\n` +
      `  - Datos: ${JSON.stringify(datos)}`
    );

    return {
      success: true,
      simulado: true,
      tema,
      messageId: `mock-fcm-${Date.now()}`,
    };
  }
}

const notificador = new NotificadorService();

module.exports = notificador;
module.exports.NotificadorService = NotificadorService;
module.exports.obtenerNombreTema = obtenerNombreTema;
