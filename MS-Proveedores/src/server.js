require('dotenv').config();

const app = require('./app');
const { config } = require('./config/env');
const { cerrarPool } = require('./config/db');

const server = app.listen(config.port, () => {
  console.log(
    JSON.stringify({
      fecha: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
      servicio: 'ms-proveedores',
      nivel: 'info',
      mensaje: `Servidor HTTP escuchando en el puerto ${config.port}`,
    })
  );
});

async function shutdown(signal) {
  console.log(`[MS-Proveedores] Señal ${signal} recibida. Cerrando servidor y pool MySQL...`);
  server.close(async () => {
    try {
      await cerrarPool();
    } catch (_) {
      // Ignora error de cierre en apagado
    }
    process.exit(0);
  });
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

module.exports = server;
