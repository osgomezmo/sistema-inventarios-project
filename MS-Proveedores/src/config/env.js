const config = {
  port: parseInt(process.env.PORT || '3001', 10),
  serviceToken: process.env.SERVICE_TOKEN || '',
  logLevel: process.env.LOG_LEVEL || 'info',
  db: {
    host: process.env.DB_HOST || '127.0.0.1',
    port: parseInt(process.env.DB_PORT || '3306', 10),
    user: process.env.DB_USER || 'proveedores_user',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'proveedores',
  },
};

module.exports = { config };
