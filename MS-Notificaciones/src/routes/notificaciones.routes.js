const { Router } = require('express');
const {
  listarNotificaciones,
  marcarComoLeida,
} = require('../controllers/notificaciones.controller');

const router = Router();

// GET /notificaciones - Consulta paginada y filtrada por rol / estado de lectura
router.get('/', listarNotificaciones);

// POST /notificaciones/:id/leida - Marca una notificación como leída
router.post('/:id/leida', marcarComoLeida);

module.exports = router;
