const { Router } = require('express');
const {
  registrarDispositivo,
  eliminarDispositivo,
} = require('../controllers/dispositivos.controller');

const router = Router();

// POST /dispositivos - Registra token FCM y suscribe a tema de rol
router.post('/', registrarDispositivo);

// DELETE /dispositivos/:id - Desuscribe token FCM y elimina registro (Dueño o Admin)
router.delete('/:id', eliminarDispositivo);

module.exports = router;
