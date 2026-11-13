require('dotenv').config();

const app = require('./app');

const PORT = process.env.PORT || 5006;

const server = app.listen(PORT, () => {
  console.log(`[MS-Notificaciones] Servidor iniciado y escuchando en el puerto ${PORT}`);
  console.log(`[MS-Notificaciones] Modo almacenamiento (STORAGE_DRIVER): ${process.env.STORAGE_DRIVER || 'local'}`);
  console.log(`[MS-Notificaciones] Modo notificador push (PUSH_DRIVER): ${process.env.PUSH_DRIVER || 'console'}`);
});

// Manejo elegante de señales de terminación
function shutdown(signal) {
  console.log(`\n[MS-Notificaciones] Recibida señal ${signal}. Cerrando servidor...`);
  server.close(() => {
    console.log('[MS-Notificaciones] Servidor HTTP cerrado correctamente.');
    process.exit(0);
  });
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

module.exports = server;
