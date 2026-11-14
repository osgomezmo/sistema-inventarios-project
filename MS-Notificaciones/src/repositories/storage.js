const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { db, estaConfigurado } = require('../config/firebase');
const { normalizarRol } = require('../utils/roles');
const { AppError } = require('../utils/errors');

const DATA_DIR = path.join(__dirname, '../../.data');
const DB_FILE = path.join(DATA_DIR, 'db.json');

// Base de datos en memoria para entornos de testing
let memoriaTest = {
  notificaciones: [],
  dispositivos: [],
  eventos_procesados: [],
};

class StorageRepository {
  constructor() {
    this.driver = (process.env.STORAGE_DRIVER || 'local').toLowerCase();
    this.isTestEnv = process.env.NODE_ENV === 'test';

    if (this.driver === 'local' && !this.isTestEnv) {
      this._inicializarArchivoLocal();
    }
  }

  // ==========================================
  // HELPERS MODO LOCAL / MEMORIA
  // ==========================================

  _inicializarArchivoLocal() {
    if (!fs.existsSync(DATA_DIR)) {
      fs.mkdirSync(DATA_DIR, { recursive: true });
    }
    if (!fs.existsSync(DB_FILE)) {
      const initData = {
        notificaciones: [],
        dispositivos: [],
        eventos_procesados: [],
      };
      fs.writeFileSync(DB_FILE, JSON.stringify(initData, null, 2), 'utf-8');
    }
  }

  _leerLocal() {
    if (this.isTestEnv) {
      return memoriaTest;
    }
    try {
      this._inicializarArchivoLocal();
      const content = fs.readFileSync(DB_FILE, 'utf-8');
      return JSON.parse(content);
    } catch (err) {
      console.error('[STORAGE-LOCAL] Error leyendo db.json:', err.message);
      return { notificaciones: [], dispositivos: [], eventos_procesados: [] };
    }
  }

  _escribirLocal(data) {
    if (this.isTestEnv) {
      memoriaTest = data;
      return;
    }
    try {
      this._inicializarArchivoLocal();
      fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf-8');
    } catch (err) {
      console.error('[STORAGE-LOCAL] Error escribiendo db.json:', err.message);
      throw new AppError(500, 'ERROR_INTERNO', 'No se pudo persistir la información local');
    }
  }

  _resetMemoriaTest() {
    memoriaTest = {
      notificaciones: [],
      dispositivos: [],
      eventos_procesados: [],
    };
  }

  // ==========================================
  // DISPOSITIVOS
  // ==========================================

  /**
   * Guarda o actualiza el registro de un dispositivo móvil/web.
   */
  async guardarDispositivo({ id, id_dispositivo, idUsuario, id_usuario, rol, tokenFcm, token_fcm, plataforma }) {
    const dispositivoId = id || id_dispositivo || uuidv4();
    const token = tokenFcm || token_fcm;
    const usuarioId = idUsuario !== undefined ? idUsuario : id_usuario;
    const rolNorm = normalizarRol(rol);
    const plat = plataforma || 'android';
    const ahora = new Date().toISOString();

    const dispositivoData = {
      id_dispositivo: dispositivoId,
      id_usuario: usuarioId || null,
      rol: rolNorm,
      token_fcm: token,
      plataforma: plat,
      registrado_en: ahora,
    };

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        await db.collection('dispositivos').doc(dispositivoId).set(dispositivoData, { merge: true });
        return dispositivoData;
      } catch (err) {
        console.error('[FIRESTORE] Error guardando dispositivo:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error persistiendo dispositivo en Firestore');
      }
    }

    // Modo local
    const data = this._leerLocal();
    const index = data.dispositivos.findIndex(
      (d) => d.id_dispositivo === dispositivoId || (token && d.token_fcm === token)
    );

    if (index >= 0) {
      data.dispositivos[index] = { ...data.dispositivos[index], ...dispositivoData };
    } else {
      data.dispositivos.push(dispositivoData);
    }

    this._escribirLocal(data);
    return dispositivoData;
  }

  /**
   * Obtiene un dispositivo por su ID.
   */
  async obtenerDispositivoPorId(id) {
    if (!id) return null;

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        const doc = await db.collection('dispositivos').doc(id).get();
        if (!doc.exists) return null;
        return { id_dispositivo: doc.id, ...doc.data() };
      } catch (err) {
        console.error('[FIRESTORE] Error obteniendo dispositivo:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error consultando dispositivo en Firestore');
      }
    }

    const data = this._leerLocal();
    return data.dispositivos.find((d) => d.id_dispositivo === id) || null;
  }

  /**
   * Elimina un dispositivo por su ID.
   * Retorna true si existía y fue eliminado, false si no existía.
   */
  async eliminarDispositivo(id) {
    if (!id) return false;

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        const docRef = db.collection('dispositivos').doc(id);
        const doc = await docRef.get();
        if (!doc.exists) return false;
        await docRef.delete();
        return true;
      } catch (err) {
        console.error('[FIRESTORE] Error eliminando dispositivo:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error eliminando dispositivo en Firestore');
      }
    }

    const data = this._leerLocal();
    const index = data.dispositivos.findIndex((d) => d.id_dispositivo === id);
    if (index === -1) return false;

    data.dispositivos.splice(index, 1);
    this._escribirLocal(data);
    return true;
  }

  // ==========================================
  // NOTIFICACIONES
  // ==========================================

  /**
   * Lista notificaciones con filtros opcionales (rol, leida) y paginación estándar.
   */
  async listarNotificaciones({ rol, leida, page = 1, perPage = 20 } = {}) {
    const numPage = Math.max(1, parseInt(page, 10) || 1);
    const numPerPage = Math.min(100, Math.max(1, parseInt(perPage, 10) || 20));
    const rolNorm = rol ? normalizarRol(rol) : null;

    let items = [];

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        let query = db.collection('notificaciones');

        if (rolNorm && rolNorm !== 'admin') {
          query = query.where('rol_destino', '==', rolNorm);
        }

        if (leida !== undefined && leida !== null) {
          const esLeida = leida === true || leida === 'true';
          query = query.where('leida', '==', esLeida);
        }

        const snapshot = await query.get();
        snapshot.forEach((doc) => {
          items.push({ id_notificacion: doc.id, ...doc.data() });
        });

        // Orden descendente por creada_en / actualizada_en
        items.sort((a, b) => {
          const fechaA = new Date(a.actualizada_en || a.creada_en || 0).getTime();
          const fechaB = new Date(b.actualizada_en || b.creada_en || 0).getTime();
          return fechaB - fechaA;
        });
      } catch (err) {
        console.error('[FIRESTORE] Error listando notificaciones:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error consultando notificaciones en Firestore');
      }
    } else {
      const data = this._leerLocal();
      items = [...data.notificaciones];

      if (rolNorm && rolNorm !== 'admin') {
        items = items.filter((n) => n.rol_destino === rolNorm);
      }

      if (leida !== undefined && leida !== null) {
        const esLeida = leida === true || leida === 'true';
        items = items.filter((n) => n.leida === esLeida);
      }

      items.sort((a, b) => {
        const fechaA = new Date(a.actualizada_en || a.creada_en || 0).getTime();
        const fechaB = new Date(b.actualizada_en || b.creada_en || 0).getTime();
        return fechaB - fechaA;
      });
    }

    const total = items.length;
    const skip = (numPage - 1) * numPerPage;
    const paginados = items.slice(skip, skip + numPerPage);

    return {
      data: paginados,
      meta: {
        page: numPage,
        per_page: numPerPage,
        total,
      },
    };
  }

  /**
   * Obtiene una notificación por su ID.
   */
  async obtenerNotificacionPorId(id) {
    if (!id) return null;

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        const doc = await db.collection('notificaciones').doc(id).get();
        if (!doc.exists) return null;
        return { id_notificacion: doc.id, ...doc.data() };
      } catch (err) {
        console.error('[FIRESTORE] Error obteniendo notificación:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error consultando notificación en Firestore');
      }
    }

    const data = this._leerLocal();
    return data.notificaciones.find((n) => n.id_notificacion === id) || null;
  }

  /**
   * Marca una notificación como leída.
   */
  async marcarNotificacionLeida(id) {
    if (!id) return null;
    const ahora = new Date().toISOString();

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        const docRef = db.collection('notificaciones').doc(id);
        const doc = await docRef.get();
        if (!doc.exists) return null;

        await docRef.update({
          leida: true,
          leida_en: ahora,
        });

        const actualizado = await docRef.get();
        return { id_notificacion: actualizado.id, ...actualizado.data() };
      } catch (err) {
        console.error('[FIRESTORE] Error marcando notificación leída:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error actualizando notificación en Firestore');
      }
    }

    const data = this._leerLocal();
    const notificacion = data.notificaciones.find((n) => n.id_notificacion === id);
    if (!notificacion) return null;

    notificacion.leida = true;
    notificacion.leida_en = ahora;

    this._escribirLocal(data);
    return notificacion;
  }

  // ==========================================
  // IDEMPOTENCIA Y ALERTAS DE STOCK BAJO
  // ==========================================

  /**
   * Verifica si un evento ya fue procesado previamente.
   */
  async fueEventoProcesado(idEvento) {
    if (!idEvento) return false;

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        const doc = await db.collection('eventos_procesados').doc(idEvento).get();
        return doc.exists;
      } catch (err) {
        console.error('[FIRESTORE] Error verificando idempotencia de evento:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error verificando evento en Firestore');
      }
    }

    const data = this._leerLocal();
    return data.eventos_procesados.some((e) => e.id_evento === idEvento);
  }

  /**
   * Registra atómicamente la alerta de stock bajo y el evento procesado.
   * Deduplica alertas activas (leida: false) para la misma tupla (rol, sku, bodega).
   */
  async registrarAlertaStockBajo({
    idEvento,
    tipoEvento = 'StockBajoUmbral',
    sku,
    idBodega,
    saldo,
    stockMinimo,
    rolesDestino = ['compras', 'jefe_bodega'],
  }) {
    const ahora = new Date().toISOString();

    if (this.driver === 'firestore' && estaConfigurado && db) {
      try {
        return await db.runTransaction(async (transaction) => {
          const eventoRef = db.collection('eventos_procesados').doc(idEvento);
          const eventoDoc = await transaction.get(eventoRef);

          if (eventoDoc.exists) {
            return { yaProcesado: true, notificaciones: [] };
          }

          transaction.set(eventoRef, {
            id_evento: idEvento,
            tipo: tipoEvento,
            procesado_en: ahora,
          });

          const notificacionesGuardadas = [];

          for (const rawRol of rolesDestino) {
            const rolNorm = normalizarRol(rawRol);

            // Búsqueda de alerta activa para deduplicar
            const queryActiva = await db
              .collection('notificaciones')
              .where('rol_destino', '==', rolNorm)
              .where('leida', '==', false)
              .where('datos.sku', '==', sku)
              .where('datos.id_bodega', '==', idBodega)
              .limit(1)
              .get();

            if (!queryActiva.empty) {
              const docExistente = queryActiva.docs[0];
              const docRef = docExistente.ref;
              const updateData = {
                mensaje: `Stock bajo el umbral mínimo para SKU ${sku} en Bodega ${idBodega}. Saldo actual: ${saldo}, Mínimo: ${stockMinimo}`,
                'datos.saldo': Number(saldo),
                'datos.stock_minimo': Number(stockMinimo),
                actualizada_en: ahora,
              };
              transaction.update(docRef, updateData);
              notificacionesGuardadas.push({
                id_notificacion: docExistente.id,
                ...docExistente.data(),
                ...updateData,
              });
            } else {
              const nuevoId = uuidv4();
              const nuevoRef = db.collection('notificaciones').doc(nuevoId);
              const nuevaNotificacion = {
                id_notificacion: nuevoId,
                tipo: 'STOCK_BAJO',
                titulo: 'Alerta de Stock Bajo',
                mensaje: `El producto ${sku} en bodega ${idBodega} tiene un saldo de ${saldo}, inferior al mínimo requerido de ${stockMinimo}.`,
                rol_destino: rolNorm,
                datos: {
                  sku,
                  id_bodega: idBodega,
                  saldo: Number(saldo),
                  stock_minimo: Number(stockMinimo),
                },
                leida: false,
                creada_en: ahora,
                actualizada_en: ahora,
              };
              transaction.set(nuevoRef, nuevaNotificacion);
              notificacionesGuardadas.push(nuevaNotificacion);
            }
          }

          return {
            yaProcesado: false,
            idEvento,
            notificaciones: notificacionesGuardadas,
          };
        });
      } catch (err) {
        console.error('[FIRESTORE] Error en transacción de alerta stock bajo:', err.message);
        throw new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Error registrando alerta en Firestore');
      }
    }

    // Modo local / memoria
    const data = this._leerLocal();

    const yaExiste = data.eventos_procesados.some((e) => e.id_evento === idEvento);
    if (yaExiste) {
      return { yaProcesado: true, notificaciones: [] };
    }

    data.eventos_procesados.push({
      id_evento: idEvento,
      tipo: tipoEvento,
      procesado_en: ahora,
    });

    const notificacionesGuardadas = [];

    for (const rawRol of rolesDestino) {
      const rolNorm = normalizarRol(rawRol);

      const notifExistente = data.notificaciones.find(
        (n) =>
          n.rol_destino === rolNorm &&
          n.leida === false &&
          n.datos &&
          n.datos.sku === sku &&
          String(n.datos.id_bodega) === String(idBodega)
      );

      if (notifExistente) {
        notifExistente.mensaje = `Stock bajo el umbral mínimo para SKU ${sku} en Bodega ${idBodega}. Saldo actual: ${saldo}, Mínimo: ${stockMinimo}`;
        notifExistente.datos.saldo = Number(saldo);
        notifExistente.datos.stock_minimo = Number(stockMinimo);
        notifExistente.actualizada_en = ahora;
        notificacionesGuardadas.push(notifExistente);
      } else {
        const nuevaNotificacion = {
          id_notificacion: uuidv4(),
          tipo: 'STOCK_BAJO',
          titulo: 'Alerta de Stock Bajo',
          mensaje: `El producto ${sku} en bodega ${idBodega} tiene un saldo de ${saldo}, inferior al mínimo requerido de ${stockMinimo}.`,
          rol_destino: rolNorm,
          datos: {
            sku,
            id_bodega: idBodega,
            saldo: Number(saldo),
            stock_minimo: Number(stockMinimo),
          },
          leida: false,
          creada_en: ahora,
          actualizada_en: ahora,
        };
        data.notificaciones.push(nuevaNotificacion);
        notificacionesGuardadas.push(nuevaNotificacion);
      }
    }

    this._escribirLocal(data);

    return {
      yaProcesado: false,
      idEvento,
      notificaciones: notificacionesGuardadas,
    };
  }
}

const storage = new StorageRepository();

module.exports = storage;
module.exports.StorageRepository = StorageRepository;
