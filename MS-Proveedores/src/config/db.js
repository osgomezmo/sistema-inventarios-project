const mysql = require('mysql2/promise');
const { config } = require('./env');
const { AppError } = require('../utils/errors');

const CODIGOS_CONEXION_BD = new Set([
  'ECONNREFUSED',
  'ETIMEDOUT',
  'ENOTFOUND',
  'ECONNRESET',
  'EHOSTUNREACH',
  'PROTOCOL_CONNECTION_LOST',
  'PROTOCOL_ENQUEUE_AFTER_FATAL_ERROR',
  'ER_ACCESS_DENIED_ERROR',
  'ER_BAD_DB_ERROR',
]);

let pool = null;

function obtenerPool() {
  if (!pool) {
    pool = mysql.createPool({
      host: config.db.host,
      port: config.db.port,
      user: config.db.user,
      password: config.db.password,
      database: config.db.database,
      waitForConnections: true,
      connectionLimit: 10,
      queueLimit: 0,
      connectTimeout: 5000,
      timezone: 'Z',
      charset: 'utf8mb4',
      decimalNumbers: false,
    });
  }
  return pool;
}

function traducirErrorDb(err) {
  if (err instanceof AppError) {
    return err;
  }
  if (err && (CODIGOS_CONEXION_BD.has(err.code) || err.fatal)) {
    return new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'La base de datos no está disponible.');
  }
  return err;
}

async function ejecutarConsulta(sql, params = []) {
  try {
    const [rows] = await obtenerPool().query(sql, params);
    return rows;
  } catch (err) {
    throw traducirErrorDb(err);
  }
}

async function conTransaccion(fn) {
  let conexion;
  try {
    conexion = await obtenerPool().getConnection();
    await conexion.beginTransaction();
    const resultado = await fn(conexion);
    await conexion.commit();
    return resultado;
  } catch (err) {
    if (conexion) {
      try {
        await conexion.rollback();
      } catch (_) {
        // Ignora fallo secundario al revertir transacción
      }
    }
    throw traducirErrorDb(err);
  } finally {
    if (conexion) {
      conexion.release();
    }
  }
}

async function verificarConexionDb() {
  try {
    await obtenerPool().query('SELECT 1 AS ok');
    return true;
  } catch (err) {
    throw traducirErrorDb(err);
  }
}

async function cerrarPool() {
  if (pool) {
    const actual = pool;
    pool = null;
    await actual.end();
  }
}

module.exports = {
  ejecutarConsulta,
  conTransaccion,
  verificarConexionDb,
  cerrarPool,
  traducirErrorDb,
};
