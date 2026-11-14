const amqplib = require('amqplib');
const storage = require('../repositories/storage');
const notificador = require('../services/notificador');

let conexionActiva = null;
let canalActivo = null;
let reconectando = false;

/**
 * Función pura/asíncrona para procesar la lógica de negocio del evento StockBajoUmbral.
 * @param {object} payload
 * @returns {Promise<{duplicado: boolean, notificacionesCreadas?: Array}>}
 */
async function procesarMensajeStockBajo(payload) {
  // a) Validación estricta del sobre y datos del evento
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  const { id_evento, tipo, datos } = payload;

  if (!id_evento || typeof id_evento !== 'string' || !id_evento.trim()) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  if (tipo !== 'StockBajoUmbral') {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  if (!datos || typeof datos !== 'object' || Array.isArray(datos)) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  const { sku, id_bodega, saldo, stock_minimo } = datos;

  if (!sku || typeof sku !== 'string' || !sku.trim()) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  if (
    id_bodega === undefined ||
    id_bodega === null ||
    typeof id_bodega === 'boolean' ||
    isNaN(Number(id_bodega)) ||
    !Number.isInteger(Number(id_bodega))
  ) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  if (
    saldo === undefined ||
    saldo === null ||
    typeof saldo === 'boolean' ||
    !Number.isFinite(Number(saldo))
  ) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  if (
    stock_minimo === undefined ||
    stock_minimo === null ||
    typeof stock_minimo === 'boolean' ||
    !Number.isFinite(Number(stock_minimo))
  ) {
    throw new Error('Payload de StockBajoUmbral inválido o corrupto');
  }

  // b) Verificación de Idempotencia
  const yaProcesado = await storage.fueEventoProcesado(id_evento.trim());
  if (yaProcesado) {
    console.log(
      `[CONSUMIDOR-STOCK-BAJO] Evento ${id_evento} ya fue procesado previamente. Descartando duplicado.`
    );
    return { duplicado: true };
  }

  const numBodega = Number(id_bodega);
  const numSaldo = Number(saldo);
  const numMinimo = Number(stock_minimo);
  const skuLimpio = sku.trim();

  // c) Registro atómico de la alerta y evento procesado con deduplicación por rol, sku y bodega
  const resultadoRegistro = await storage.registrarAlertaStockBajo({
    idEvento: id_evento.trim(),
    tipoEvento: tipo,
    sku: skuLimpio,
    idBodega: numBodega,
    saldo: numSaldo,
    stockMinimo: numMinimo,
    rolesDestino: ['compras', 'jefe_bodega'],
  });

  if (resultadoRegistro.yaProcesado) {
    return { duplicado: true };
  }

  // d) Envío push a los temas FCM correspondientes
  const titulo = 'Alerta de Stock Bajo';
  const mensaje = `El producto ${skuLimpio} en bodega ${numBodega} tiene un saldo de ${numSaldo}, inferior al mínimo requerido de ${numMinimo}.`;
  const datosPush = {
    sku: skuLimpio,
    id_bodega: numBodega,
    saldo: numSaldo,
    stock_minimo: numMinimo,
  };

  await notificador.enviarPushATema('compras', titulo, mensaje, datosPush);
  await notificador.enviarPushATema('jefe_bodega', titulo, mensaje, datosPush);

  // e) Retorno del resultado con las notificaciones creadas/actualizadas
  return {
    duplicado: false,
    notificacionesCreadas: resultadoRegistro.notificaciones || [],
  };
}

/**
 * Conecta a RabbitMQ, configura canal con prefetch(1) y consume de q.notificaciones.
 * Maneja ack/nack y reintento automático de conexión cada 5 segundos.
 */
async function iniciarConsumidor() {
  const rabbitUrl =
    process.env.RABBITMQ_URL || 'amqp://inventario:inventario_secret@127.0.0.1:5672/%2F';
  const cola = 'q.notificaciones';

  reconectando = false;

  try {
    console.log(`[CONSUMIDOR-AMQP] Conectando a RabbitMQ en ${rabbitUrl.replace(/:[^:@]+@/, ':****@')}...`);
    const conexion = await amqplib.connect(rabbitUrl);
    conexionActiva = conexion;

    conexion.on('error', (err) => {
      console.error('[CONSUMIDOR-AMQP] Error en conexión RabbitMQ:', err.message);
      programarReconexion();
    });

    conexion.on('close', () => {
      console.warn('[CONSUMIDOR-AMQP] Conexión cerrada con RabbitMQ. Intentando reconectar...');
      programarReconexion();
    });

    const canal = await conexion.createChannel();
    canalActivo = canal;

    canal.on('error', (err) => {
      console.error('[CONSUMIDOR-AMQP] Error en canal RabbitMQ:', err.message);
    });

    // Control de flujo: 1 mensaje a la vez por consumidor
    await canal.prefetch(1);

    console.log(`[CONSUMIDOR-AMQP] Escuchando mensajes en cola: ${cola}`);

    await canal.consume(
      cola,
      async (msg) => {
        if (!msg) return;

        let idCorrelacion =
          msg.properties && msg.properties.correlationId ? msg.properties.correlationId : 'N/A';

        try {
          const contenidoRaw = msg.content.toString();
          let payload;

          try {
            payload = JSON.parse(contenidoRaw);
            if (payload && payload.id_correlacion) {
              idCorrelacion = payload.id_correlacion;
            }
          } catch (jsonErr) {
            throw new Error(`JSON malformado en mensaje: ${jsonErr.message}`);
          }

          console.log(
            `[CONSUMIDOR-AMQP] Mensaje recibido de ${cola} (Correlación: ${idCorrelacion})`
          );

          await procesarMensajeStockBajo(payload);

          // Confirmación manual (ack) tras procesamiento exitoso (nuevo o duplicado)
          canal.ack(msg);
        } catch (err) {
          console.error(
            `[CONSUMIDOR-AMQP] Error procesando mensaje (Correlación: ${idCorrelacion}): ${err.message}`
          );
          // Rechazo con requeue = true:
          // RabbitMQ reintenta hasta delivery-limit = 3 y lo enruta al Dead Letter Exchange
          canal.nack(msg, false, true);
        }
      },
      { noAck: false }
    );
  } catch (err) {
    console.error('[CONSUMIDOR-AMQP] No se pudo inicializar el consumidor:', err.message);
    programarReconexion();
  }
}

function programarReconexion() {
  if (reconectando) return;
  reconectando = true;

  if (canalActivo) {
    try {
      canalActivo.removeAllListeners();
    } catch (_) {}
    canalActivo = null;
  }
  if (conexionActiva) {
    try {
      conexionActiva.removeAllListeners();
    } catch (_) {}
    conexionActiva = null;
  }

  console.log('[CONSUMIDOR-AMQP] Reintentando conexión en 5 segundos...');
  setTimeout(() => {
    iniciarConsumidor();
  }, 5000);
}

async function detenerConsumidor() {
  try {
    if (canalActivo) {
      await canalActivo.close();
      canalActivo = null;
    }
    if (conexionActiva) {
      await conexionActiva.close();
      conexionActiva = null;
    }
    reconectando = false;
  } catch (err) {
    console.warn('[CONSUMIDOR-AMQP] Error al cerrar consumidor:', err.message);
  }
}

module.exports = {
  procesarMensajeStockBajo,
  iniciarConsumidor,
  detenerConsumidor,
};
