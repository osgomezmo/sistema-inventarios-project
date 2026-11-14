const request = require('supertest');
const app = require('../src/app');
const storage = require('../src/repositories/storage');

describe('Paso 1.2 — Controladores y Rutas de MS-Notificaciones', () => {
  const serviceToken = 'token-secreto-gateway-2026';

  beforeEach(() => {
    storage._resetMemoriaTest();
    process.env.SERVICE_TOKEN = serviceToken;
    process.env.STORAGE_DRIVER = 'local';
    process.env.PUSH_DRIVER = 'console';
  });

  // =========================================================================
  // ENDPOINT: POST /dispositivos
  // =========================================================================
  describe('POST /dispositivos', () => {
    it('debe responder 422 si faltan datos en el body o encabezados de usuario', async () => {
      // Falta X-User-Id y X-User-Role
      const res1 = await request(app)
        .post('/dispositivos')
        .set('Authorization', `Bearer ${serviceToken}`)
        .send({ token_fcm: 'token-123', plataforma: 'android' });

      expect(res1.status).toBe(422);
      expect(res1.body.error.codigo).toBe('VALIDACION_FALLIDA');
      expect(res1.body.error.detalles).toHaveProperty('id_usuario');
      expect(res1.body.error.detalles).toHaveProperty('rol');

      // Faltan campos en el body
      const res2 = await request(app)
        .post('/dispositivos')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Id', '10')
        .set('X-User-Role', 'Compras')
        .send({});

      expect(res2.status).toBe(422);
      expect(res2.body.error.codigo).toBe('VALIDACION_FALLIDA');
      expect(res2.body.error.detalles).toHaveProperty('token_fcm');
      expect(res2.body.error.detalles).toHaveProperty('plataforma');
    });

    it('debe registrar el dispositivo y retornar 201 con el recurso creado', async () => {
      const res = await request(app)
        .post('/dispositivos')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Id', '15')
        .set('X-User-Role', 'Jefe de bodega')
        .send({
          token_fcm: 'fcm-token-valido-12345',
          plataforma: 'android',
        });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty('id_dispositivo');
      expect(res.body.id_usuario).toBe('15');
      expect(res.body.rol).toBe('jefe_bodega');
      expect(res.body.token_fcm).toBe('fcm-token-valido-12345');
      expect(res.body.plataforma).toBe('android');
      expect(res.body).toHaveProperty('registrado_en');

      // Verificar que quedó persistido en el storage
      const guardado = await storage.obtenerDispositivoPorId(res.body.id_dispositivo);
      expect(guardado).toBeDefined();
      expect(guardado.id_usuario).toBe('15');
    });
  });

  // =========================================================================
  // ENDPOINT: DELETE /dispositivos/:id
  // =========================================================================
  describe('DELETE /dispositivos/:id', () => {
    it('debe responder 404 si el dispositivo no existe', async () => {
      const res = await request(app)
        .delete('/dispositivos/id-inexistente')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Id', '15')
        .set('X-User-Role', 'Compras');

      expect(res.status).toBe(404);
      expect(res.body.error.codigo).toBe('DISPOSITIVO_NO_ENCONTRADO');
    });

    it('debe responder 403 si el usuario no es el dueño ni administrador', async () => {
      // Creamos un dispositivo para el usuario 10
      const disp = await storage.guardarDispositivo({
        idUsuario: '10',
        rol: 'compras',
        tokenFcm: 'token-usuario-10',
        plataforma: 'web',
      });

      // El usuario 99 (no admin) intenta eliminarlo
      const res = await request(app)
        .delete(`/dispositivos/${disp.id_dispositivo}`)
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Id', '99')
        .set('X-User-Role', 'compras');

      expect(res.status).toBe(403);
      expect(res.body.error.codigo).toBe('SIN_PERMISO');
      expect(res.body.error.mensaje).toBe('No tienes permiso para eliminar este dispositivo');

      // Verificar que el dispositivo NO se eliminó
      const sigueExistiendo = await storage.obtenerDispositivoPorId(disp.id_dispositivo);
      expect(sigueExistiendo).not.toBeNull();
    });

    it('debe permitir la eliminación si el usuario es el dueño (responde 204)', async () => {
      const disp = await storage.guardarDispositivo({
        idUsuario: '10',
        rol: 'compras',
        tokenFcm: 'token-usuario-10',
        plataforma: 'web',
      });

      const res = await request(app)
        .delete(`/dispositivos/${disp.id_dispositivo}`)
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Id', '10')
        .set('X-User-Role', 'compras');

      expect(res.status).toBe(204);
      expect(res.body).toEqual({});

      const eliminado = await storage.obtenerDispositivoPorId(disp.id_dispositivo);
      expect(eliminado).toBeNull();
    });

    it('debe permitir la eliminación si el usuario tiene rol admin aunque no sea el dueño (responde 204)', async () => {
      const disp = await storage.guardarDispositivo({
        idUsuario: '10',
        rol: 'compras',
        tokenFcm: 'token-usuario-10',
        plataforma: 'web',
      });

      const res = await request(app)
        .delete(`/dispositivos/${disp.id_dispositivo}`)
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Id', '1') // Admin con id diferente
        .set('X-User-Role', 'Administrador');

      expect(res.status).toBe(204);

      const eliminado = await storage.obtenerDispositivoPorId(disp.id_dispositivo);
      expect(eliminado).toBeNull();
    });
  });

  // =========================================================================
  // ENDPOINT: GET /notificaciones
  // =========================================================================
  describe('GET /notificaciones', () => {
    beforeEach(async () => {
      // Sembrar alertas para pruebas de filtrado y paginación
      await storage.registrarAlertaStockBajo({
        idEvento: 'evt-001',
        sku: 'SKU-AAA',
        idBodega: 1,
        saldo: 3,
        stockMinimo: 10,
        rolesDestino: ['compras', 'jefe_bodega'],
      });

      await storage.registrarAlertaStockBajo({
        idEvento: 'evt-002',
        sku: 'SKU-BBB',
        idBodega: 2,
        saldo: 1,
        stockMinimo: 5,
        rolesDestino: ['compras'],
      });
    });

    it('debe validar parámetros de consulta y responder 422 si son inválidos', async () => {
      const res1 = await request(app)
        .get('/notificaciones?page=0')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'compras');

      expect(res1.status).toBe(422);
      expect(res1.body.error.codigo).toBe('PARAMETROS_INVALIDOS');
      expect(res1.body.error.detalles).toHaveProperty('page');

      const res2 = await request(app)
        .get('/notificaciones?per_page=150')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'compras');

      expect(res2.status).toBe(422);
      expect(res2.body.error.detalles).toHaveProperty('per_page');

      const res3 = await request(app)
        .get('/notificaciones?leida=si')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'compras');

      expect(res3.status).toBe(422);
      expect(res3.body.error.detalles).toHaveProperty('leida');
    });

    it('debe filtrar notificaciones automáticamente por el rol del usuario no-admin', async () => {
      // Usuario con rol 'compras' debe ver 2 alertas (SKU-AAA y SKU-BBB)
      const resCompras = await request(app)
        .get('/notificaciones')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Compras');

      expect(resCompras.status).toBe(200);
      expect(resCompras.body.meta.total).toBe(2);
      expect(resCompras.body.data.every((n) => n.rol_destino === 'compras')).toBe(true);

      // Usuario con rol 'jefe_bodega' debe ver solo 1 alerta (SKU-AAA)
      const resJefe = await request(app)
        .get('/notificaciones')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Jefe de bodega');

      expect(resJefe.status).toBe(200);
      expect(resJefe.body.meta.total).toBe(1);
      expect(resJefe.body.data[0].rol_destino).toBe('jefe_bodega');
    });

    it('debe permitir a un admin ver todas las notificaciones o filtrar por ?rol=', async () => {
      // Admin sin filtro ?rol=: ve las 3 notificaciones
      const resAdminTodas = await request(app)
        .get('/notificaciones')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Admin');

      expect(resAdminTodas.status).toBe(200);
      expect(resAdminTodas.body.meta.total).toBe(3);

      // Admin filtrando con ?rol=jefe_bodega
      const resAdminJefe = await request(app)
        .get('/notificaciones?rol=jefe_bodega')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Admin');

      expect(resAdminJefe.status).toBe(200);
      expect(resAdminJefe.body.meta.total).toBe(1);
      expect(resAdminJefe.body.data[0].rol_destino).toBe('jefe_bodega');
    });

    it('debe aplicar paginación correctamente (page y per_page)', async () => {
      const res = await request(app)
        .get('/notificaciones?page=1&per_page=1')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Compras');

      expect(res.status).toBe(200);
      expect(res.body.meta.page).toBe(1);
      expect(res.body.meta.per_page).toBe(1);
      expect(res.body.meta.total).toBe(2);
      expect(res.body.data).toHaveLength(1);
    });

    it('debe filtrar correctamente por estado de lectura (?leida=true|false)', async () => {
      const listado = await storage.listarNotificaciones({ rol: 'compras' });
      const primerId = listado.data[0].id_notificacion;
      await storage.marcarNotificacionLeida(primerId);

      const resLeidas = await request(app)
        .get('/notificaciones?leida=true')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Compras');

      expect(resLeidas.status).toBe(200);
      expect(resLeidas.body.meta.total).toBe(1);
      expect(resLeidas.body.data[0].id_notificacion).toBe(primerId);

      const resNoLeidas = await request(app)
        .get('/notificaciones?leida=false')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Compras');

      expect(resNoLeidas.status).toBe(200);
      expect(resNoLeidas.body.meta.total).toBe(1);
      expect(resNoLeidas.body.data[0].leida).toBe(false);
    });
  });

  // =========================================================================
  // ENDPOINT: POST /notificaciones/:id/leida
  // =========================================================================
  describe('POST /notificaciones/:id/leida', () => {
    let notifCompras;
    let notifJefe;

    beforeEach(async () => {
      const res = await storage.registrarAlertaStockBajo({
        idEvento: 'evt-test-leida',
        sku: 'SKU-LEIDA',
        idBodega: 1,
        saldo: 2,
        stockMinimo: 8,
        rolesDestino: ['compras', 'jefe_bodega'],
      });

      notifCompras = res.notificaciones.find((n) => n.rol_destino === 'compras');
      notifJefe = res.notificaciones.find((n) => n.rol_destino === 'jefe_bodega');
    });

    it('debe responder 404 si la notificación no existe', async () => {
      const res = await request(app)
        .post('/notificaciones/id-inexistente/leida')
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'compras');

      expect(res.status).toBe(404);
      expect(res.body.error.codigo).toBe('NOTIFICACION_NO_ENCONTRADA');
    });

    it('debe responder 403 si el usuario intenta marcar una notificación de otro rol', async () => {
      // Usuario con rol 'compras' intenta marcar la notificación de 'jefe_bodega'
      const res = await request(app)
        .post(`/notificaciones/${notifJefe.id_notificacion}/leida`)
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Compras');

      expect(res.status).toBe(403);
      expect(res.body.error.codigo).toBe('SIN_PERMISO');
      expect(res.body.error.mensaje).toBe('Esta notificación pertenece a otro rol');
    });

    it('debe marcar la notificación como leída si el rol coincide (responde 200)', async () => {
      const res = await request(app)
        .post(`/notificaciones/${notifCompras.id_notificacion}/leida`)
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Compras');

      expect(res.status).toBe(200);
      expect(res.body.id_notificacion).toBe(notifCompras.id_notificacion);
      expect(res.body.leida).toBe(true);
      expect(res.body.leida_en).toBeDefined();

      // Verificar en storage
      const actualizada = await storage.obtenerNotificacionPorId(notifCompras.id_notificacion);
      expect(actualizada.leida).toBe(true);
    });

    it('debe permitir a un admin marcar como leída cualquier notificación (responde 200)', async () => {
      const res = await request(app)
        .post(`/notificaciones/${notifJefe.id_notificacion}/leida`)
        .set('Authorization', `Bearer ${serviceToken}`)
        .set('X-User-Role', 'Administrador');

      expect(res.status).toBe(200);
      expect(res.body.leida).toBe(true);
    });
  });
});
