const { Router } = require('express');
const { verificarConexionDb } = require('../config/db');

const router = Router();

router.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'ms-proveedores',
  });
});

router.get('/health/ready', async (req, res, next) => {
  try {
    await verificarConexionDb();
    res.status(200).json({
      status: 'ok',
      service: 'ms-proveedores',
      db: 'connected',
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
