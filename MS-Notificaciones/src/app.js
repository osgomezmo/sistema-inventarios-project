const express = require('express');
const cors = require('cors');

const correlationMiddleware = require('./middlewares/correlation');
const authMiddleware = require('./middlewares/auth');
const { notFoundHandler, errorHandler } = require('./middlewares/errorHandler');

const dispositivosRoutes = require('./routes/dispositivos.routes');
const notificacionesRoutes = require('./routes/notificaciones.routes');

const app = express();

// Middlewares globales de parsing y CORS
app.use(cors());
app.use(express.json());

// Trazabilidad distribuida con X-Correlation-Id
app.use(correlationMiddleware);

// Endpoint público de salud (sin autenticación de servicio)
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'ms-notificaciones',
  });
});

// A partir de aquí, todas las rutas exigen autenticación interna por SERVICE_TOKEN
app.use(authMiddleware);

// Rutas del microservicio
app.use('/dispositivos', dispositivosRoutes);
app.use('/notificaciones', notificacionesRoutes);

// Manejo de recursos inexistentes (404) y errores globales
app.use(notFoundHandler);
app.use(errorHandler);

module.exports = app;
