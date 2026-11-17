const express = require('express');
const cors = require('cors');

const correlationMiddleware = require('./middlewares/correlation');
const authMiddleware = require('./middlewares/auth');
const { notFoundHandler, errorHandler } = require('./middlewares/errorHandler');

const healthRoutes = require('./routes/health.routes');
const proveedoresRoutes = require('./routes/proveedores.routes');

const app = express();

app.use(cors());
app.use(express.json());
app.use(correlationMiddleware);

// Rutas públicas de salud (sin token de servicio)
app.use('/', healthRoutes);

// Todas las rutas de negocio exigen Authorization: Bearer <SERVICE_TOKEN>
app.use(authMiddleware);

app.use('/proveedores', proveedoresRoutes);

app.use(notFoundHandler);
app.use(errorHandler);

module.exports = app;
