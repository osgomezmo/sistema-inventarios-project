const request = require('supertest');
const app = require('../src/app');
const { normalizarRol } = require('../src/utils/roles');
const { AppError } = require('../src/utils/errors');
const notificador = require('../src/services/notificador');
const storage = require('../src/repositories/storage');

describe('Paso 1.1 — MS-Notificaciones Base Architecture', () => {
  beforeEach(() => {
    storage._resetMemoriaTest();
    process.env.SERVICE_TOKEN = 'token-secreto-gateway-2026';
    process.env.STORAGE_DRIVER = 'local';
    process.env.PUSH_DRIVER = 'console';
  });

  describe('1. Endpoint de Salud (GET /health)', () => {
    it('debe responder 200 con status ok y el nombre del microservicio sin exigir token', async () => {
      const res = await request(app).get('/health');
      expect(res.status).toBe(200);
      expect(res.body).toEqual({
        status: 'ok',
        service: 'ms-notificaciones',
      });
      expect(res.headers['x-correlation-id']).toBeDefined();
    });

    it('debe propagar el X-Correlation-Id enviado por el cliente', async () => {
      const cid = 'test-correlation-uuid-1234';
      const res = await request(app).get('/health').set('X-Correlation-Id', cid);
      expect(res.status).toBe(200);
      expect(res.headers['x-correlation-id']).toBe(cid);
    });
  });

  describe('2. Autenticación de Servicio (authMiddleware)', () => {
    it('debe rechazar con 401 si falta el encabezado Authorization', async () => {
      const res = await request(app).get('/alguna-ruta');
      expect(res.status).toBe(401);
      expect(res.body).toEqual({
        error: {
          codigo: 'NO_AUTORIZADO',
          mensaje: 'Token de servicio inválido o ausente',
          detalles: null,
        },
      });
    });

    it('debe rechazar con 401 si el token no coincide con SERVICE_TOKEN', async () => {
      const res = await request(app)
        .get('/alguna-ruta')
        .set('Authorization', 'Bearer token-equivocado');
      expect(res.status).toBe(401);
      expect(res.body.error.codigo).toBe('NO_AUTORIZADO');
    });

    it('debe permitir la petición y devolver 404 canónico si el token es válido pero la ruta no existe', async () => {
      const res = await request(app)
        .get('/ruta-inexistente')
        .set('Authorization', 'Bearer token-secreto-gateway-2026')
        .set('X-User-Id', '42')
        .set('X-User-Role', 'Jefe de bodega');

      expect(res.status).toBe(404);
      expect(res.body).toEqual({
        error: {
          codigo: 'RUTA_NO_ENCONTRADA',
          mensaje: 'Ruta no encontrada',
          detalles: null,
        },
      });
    });
  });

  describe('3. Normalización de Roles', () => {
    it('debe normalizar roles de acuerdo a las reglas del sistema', () => {
      expect(normalizarRol('Administrador')).toBe('admin');
      expect(normalizarRol('Admin')).toBe('admin');
      expect(normalizarRol('Jefe de bodega')).toBe('jefe_bodega');
      expect(normalizarRol('Jefe')).toBe('jefe_bodega');
      expect(normalizarRol('Compras')).toBe('compras');
      expect(normalizarRol('Gerente')).toBe('gerente');
      expect(normalizarRol('')).toBeNull();
      expect(normalizarRol(null)).toBeNull();
    });
  });

  describe('4. Servicio Notificador (Modo Consola)', () => {
    it('debe simular suscripción al tema correspondiente', async () => {
      const res = await notificador.suscribirATema('token-fcm-demo', 'compras');
      expect(res.success).toBe(true);
      expect(res.simulado).toBe(true);
      expect(res.tema).toBe('rol_compras');
    });

    it('debe simular desuscripción del tema correspondiente', async () => {
      const res = await notificador.desuscribirDeTema('token-fcm-demo', 'Jefe de bodega');
      expect(res.success).toBe(true);
      expect(res.simulado).toBe(true);
      expect(res.tema).toBe('rol_jefe_de_bodega');
    });

    it('debe simular envío push al tema correspondiente', async () => {
      const res = await notificador.enviarPushATema(
        'compras',
        'Alerta de Stock',
        'Stock bajo en SKU LAC-0001',
        { sku: 'LAC-0001', saldo: 4 }
      );
      expect(res.success).toBe(true);
      expect(res.simulado).toBe(true);
      expect(res.tema).toBe('rol_compras');
      expect(res.messageId).toBeDefined();
    });
  });

  describe('5. Repositorio Storage (Memoria / Local)', () => {
    it('debe guardar, consultar y eliminar dispositivos correctamente', async () => {
      const nuevo = await storage.guardarDispositivo({
        idUsuario: 10,
        rol: 'Jefe de bodega',
        tokenFcm: 'token-device-xyz',
        plataforma: 'android',
      });

      expect(nuevo.id_dispositivo).toBeDefined();
      expect(nuevo.rol).toBe('jefe_bodega');
      expect(nuevo.token_fcm).toBe('token-device-xyz');

      const obtenido = await storage.obtenerDispositivoPorId(nuevo.id_dispositivo);
      expect(obtenido).toEqual(nuevo);

      const eliminado = await storage.eliminarDispositivo(nuevo.id_dispositivo);
      expect(eliminado).toBe(true);

      const postEliminado = await storage.obtenerDispositivoPorId(nuevo.id_dispositivo);
      expect(postEliminado).toBeNull();
    });

    it('debe registrar alertas de stock bajo y verificar idempotencia', async () => {
      const idEvento = 'evento-uuid-1111';

      // 1. Primer registro del evento
      const res1 = await storage.registrarAlertaStockBajo({
        idEvento,
        tipoEvento: 'StockBajoUmbral',
        sku: 'LAC-0001',
        idBodega: 1,
        saldo: 4.0,
        stockMinimo: 10.0,
        rolesDestino: ['compras', 'jefe_bodega'],
      });

      expect(res1.yaProcesado).toBe(false);
      expect(res1.notificaciones).toHaveLength(2);

      // Verificar que el evento ahora figura como procesado
      const yaProc = await storage.fueEventoProcesado(idEvento);
      expect(yaProc).toBe(true);

      // 2. Intento de reprocesar el mismo idEvento (Idempotencia)
      const res2 = await storage.registrarAlertaStockBajo({
        idEvento,
        tipoEvento: 'StockBajoUmbral',
        sku: 'LAC-0001',
        idBodega: 1,
        saldo: 4.0,
        stockMinimo: 10.0,
      });

      expect(res2.yaProcesado).toBe(true);
      expect(res2.notificaciones).toHaveLength(0);

      // 3. Nuevo evento para el mismo SKU y bodega -> Deduplicación de notificación no leída
      const idEvento2 = 'evento-uuid-2222';
      const res3 = await storage.registrarAlertaStockBajo({
        idEvento: idEvento2,
        tipoEvento: 'StockBajoUmbral',
        sku: 'LAC-0001',
        idBodega: 1,
        saldo: 2.0,
        stockMinimo: 10.0,
        rolesDestino: ['compras'],
      });

      expect(res3.yaProcesado).toBe(false);
      expect(res3.notificaciones).toHaveLength(1);
      expect(res3.notificaciones[0].datos.saldo).toBe(2);

      // Listar notificaciones para 'compras': solo debe haber 1 alerta (actualizada, no duplicada)
      const listado = await storage.listarNotificaciones({ rol: 'compras', leida: false });
      expect(listado.meta.total).toBe(1);
      expect(listado.data[0].datos.saldo).toBe(2);

      // 4. Marcar como leída
      const notifId = listado.data[0].id_notificacion;
      const marcada = await storage.marcarNotificacionLeida(notifId);
      expect(marcada.leida).toBe(true);
      expect(marcada.leida_en).toBeDefined();

      const listadoNoLeidas = await storage.listarNotificaciones({ rol: 'compras', leida: false });
      expect(listadoNoLeidas.meta.total).toBe(0);
    });
  });
});
