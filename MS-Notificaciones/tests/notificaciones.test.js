const request = require('supertest');
const app = require('../src/app');
const storage = require('../src/repositories/storage');
const notificador = require('../src/services/notificador');
const { procesarMensajeStockBajo } = require('../src/consumers/stockBajo.consumer');

describe('Batería de Pruebas Automatizadas — MS-Notificaciones (10 Casos)', () => {
  const serviceToken = 'token-secreto-gateway-2026';

  beforeEach(() => {
    storage._resetMemoriaTest();
    process.env.SERVICE_TOKEN = serviceToken;
    process.env.STORAGE_DRIVER = 'local';
    process.env.PUSH_DRIVER = 'console';
    jest.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Caso 1: GET /health responde 200 sin autenticación.
  // -------------------------------------------------------------------------
  test('Caso 1: GET /health responde 200 sin autenticación', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      status: 'ok',
      service: 'ms-notificaciones',
    });
    expect(res.headers['x-correlation-id']).toBeDefined();
  });

  // -------------------------------------------------------------------------
  // Caso 2: Petición sin Authorization: Bearer <SERVICE_TOKEN> responde 401
  // con formato {"error": {"codigo", "mensaje", "detalles"}}.
  // -------------------------------------------------------------------------
  test('Caso 2: Petición sin Authorization responde 401 con formato canónico de error', async () => {
    const res = await request(app).get('/notificaciones');
    expect(res.status).toBe(401);
    expect(res.body).toEqual({
      error: {
        codigo: 'NO_AUTORIZADO',
        mensaje: 'Token de servicio inválido o ausente',
        detalles: null,
      },
    });
  });

  // -------------------------------------------------------------------------
  // Caso 3: POST /dispositivos crea dispositivo (201) y suscribe al tema
  // del rol normalizado (Jefe de bodega -> jefe_bodega).
  // -------------------------------------------------------------------------
  test('Caso 3: POST /dispositivos crea dispositivo (201) y suscribe al tema del rol normalizado', async () => {
    const spySuscribir = jest.spyOn(notificador, 'suscribirATema');

    const res = await request(app)
      .post('/dispositivos')
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Id', '101')
      .set('X-User-Role', 'Jefe de bodega')
      .send({
        token_fcm: 'token-fcm-jefe-bodega-123',
        plataforma: 'android',
      });

    expect(res.status).toBe(201);
    expect(res.body.id_usuario).toBe('101');
    expect(res.body.rol).toBe('jefe_bodega');
    expect(res.body.token_fcm).toBe('token-fcm-jefe-bodega-123');
    expect(res.body.plataforma).toBe('android');

    expect(spySuscribir).toHaveBeenCalledWith('token-fcm-jefe-bodega-123', 'jefe_bodega');
    spySuscribir.mockRestore();
  });

  // -------------------------------------------------------------------------
  // Caso 4: POST /dispositivos sin token_fcm responde 422.
  // -------------------------------------------------------------------------
  test('Caso 4: POST /dispositivos sin token_fcm responde 422 con detalles de validación', async () => {
    const res = await request(app)
      .post('/dispositivos')
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Id', '101')
      .set('X-User-Role', 'compras')
      .send({
        plataforma: 'web',
      });

    expect(res.status).toBe(422);
    expect(res.body.error.codigo).toBe('VALIDACION_FALLIDA');
    expect(res.body.error.detalles).toHaveProperty('token_fcm');
  });

  // -------------------------------------------------------------------------
  // Caso 5: DELETE /dispositivos/:id responde 403 si otro usuario que no es
  // dueño ni admin intenta borrarlo, 204 si lo borra el dueño o un admin, y 404 si ya no existe.
  // -------------------------------------------------------------------------
  test('Caso 5: DELETE /dispositivos/:id valida permisos (403 ajeno, 204 dueño/admin, 404 no existe)', async () => {
    // Crear dispositivo para usuario 50
    const disp = await storage.guardarDispositivo({
      idUsuario: '50',
      rol: 'compras',
      tokenFcm: 'token-50',
      plataforma: 'android',
    });

    // 5.a Usuario ajeno (id: 99, rol: compras) intenta borrarlo -> 403
    const resAjeno = await request(app)
      .delete(`/dispositivos/${disp.id_dispositivo}`)
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Id', '99')
      .set('X-User-Role', 'compras');

    expect(resAjeno.status).toBe(403);
    expect(resAjeno.body.error.codigo).toBe('SIN_PERMISO');

    // 5.b Dueño (id: 50) lo borra -> 204
    const resDuenio = await request(app)
      .delete(`/dispositivos/${disp.id_dispositivo}`)
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Id', '50')
      .set('X-User-Role', 'compras');

    expect(resDuenio.status).toBe(204);

    // 5.c Intentar borrarlo de nuevo (ya no existe) -> 404
    const resNoExiste = await request(app)
      .delete(`/dispositivos/${disp.id_dispositivo}`)
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Id', '50')
      .set('X-User-Role', 'compras');

    expect(resNoExiste.status).toBe(404);
    expect(resNoExiste.body.error.codigo).toBe('DISPOSITIVO_NO_ENCONTRADO');

    // 5.d Crear otro dispositivo y verificar que un admin sí puede borrarlo -> 204
    const disp2 = await storage.guardarDispositivo({
      idUsuario: '60',
      rol: 'compras',
      tokenFcm: 'token-60',
      plataforma: 'android',
    });

    const resAdmin = await request(app)
      .delete(`/dispositivos/${disp2.id_dispositivo}`)
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Id', '1')
      .set('X-User-Role', 'admin');

    expect(resAdmin.status).toBe(204);
  });

  // -------------------------------------------------------------------------
  // Caso 6: procesarMensajeStockBajo crea notificaciones para compras y
  // jefe_bodega al recibir StockBajoUmbral.
  // -------------------------------------------------------------------------
  test('Caso 6: procesarMensajeStockBajo crea notificaciones para compras y jefe_bodega', async () => {
    const spyPush = jest.spyOn(notificador, 'enviarPushATema');

    const payload = {
      id_evento: 'evt-stock-6666',
      tipo: 'StockBajoUmbral',
      fecha: '2026-11-13T19:00:00Z',
      productor: 'ms-inventario',
      id_correlacion: 'corr-6666',
      datos: {
        sku: 'LAC-0001',
        id_bodega: 1,
        saldo: 4.0,
        stock_minimo: 10.0,
      },
    };

    const resultado = await procesarMensajeStockBajo(payload);

    expect(resultado.duplicado).toBe(false);
    expect(resultado.notificacionesCreadas).toHaveLength(2);

    const rolesDestino = resultado.notificacionesCreadas.map((n) => n.rol_destino);
    expect(rolesDestino).toContain('compras');
    expect(rolesDestino).toContain('jefe_bodega');

    // Verifica que se enviaron los push a ambos temas
    expect(spyPush).toHaveBeenCalledWith('compras', expect.any(String), expect.any(String), expect.any(Object));
    expect(spyPush).toHaveBeenCalledWith('jefe_bodega', expect.any(String), expect.any(String), expect.any(Object));

    spyPush.mockRestore();
  });

  // -------------------------------------------------------------------------
  // Caso 7: Idempotencia: llamar 2 veces a procesarMensajeStockBajo con el
  // mismo id_evento ignora el segundo envío y no duplica notificaciones.
  // -------------------------------------------------------------------------
  test('Caso 7: Idempotencia: reenvío con mismo id_evento es ignorado sin duplicar notificaciones', async () => {
    const payload = {
      id_evento: 'evt-idempotente-7777',
      tipo: 'StockBajoUmbral',
      datos: {
        sku: 'BEB-0002',
        id_bodega: 2,
        saldo: 1.0,
        stock_minimo: 8.0,
      },
    };

    // Primer procesamiento
    const res1 = await procesarMensajeStockBajo(payload);
    expect(res1.duplicado).toBe(false);

    // Segundo procesamiento del mismo id_evento
    const res2 = await procesarMensajeStockBajo(payload);
    expect(res2.duplicado).toBe(true);

    // Verificar en el storage que solo existen 2 notificaciones en total (1 para compras, 1 para jefe_bodega)
    const listado = await storage.listarNotificaciones({ rol: null });
    expect(listado.meta.total).toBe(2);
  });

  // -------------------------------------------------------------------------
  // Caso 8: Deduplicación: un segundo evento con distinto id_evento pero mismo
  // sku y id_bodega actualiza el saldo de la notificación no leída en vez de crear otra repetida.
  // -------------------------------------------------------------------------
  test('Caso 8: Deduplicación: nuevo id_evento con mismo SKU y bodega actualiza la alerta no leída', async () => {
    const payloadInicial = {
      id_evento: 'evt-dedup-8888-A',
      tipo: 'StockBajoUmbral',
      datos: {
        sku: 'PAN-0003',
        id_bodega: 1,
        saldo: 5.0,
        stock_minimo: 12.0,
      },
    };

    await procesarMensajeStockBajo(payloadInicial);

    // Segundo evento con DIFERENTE id_evento pero MISMO SKU y bodega y nuevo saldo
    const payloadActualizado = {
      id_evento: 'evt-dedup-8888-B',
      tipo: 'StockBajoUmbral',
      datos: {
        sku: 'PAN-0003',
        id_bodega: 1,
        saldo: 3.0,
        stock_minimo: 12.0,
      },
    };

    const res2 = await procesarMensajeStockBajo(payloadActualizado);
    expect(res2.duplicado).toBe(false);

    // Debe seguir habiendo solo 2 notificaciones activas no leídas en total (1 compras, 1 jefe_bodega)
    const listadoCompras = await storage.listarNotificaciones({ rol: 'compras', leida: false });
    expect(listadoCompras.meta.total).toBe(1);
    expect(listadoCompras.data[0].datos.saldo).toBe(3);
  });

  // -------------------------------------------------------------------------
  // Caso 9: Evento corrupto (sin sku o sin saldo) lanza excepción en procesarMensajeStockBajo.
  // -------------------------------------------------------------------------
  test('Caso 9: Evento corrupto lanza excepción en procesarMensajeStockBajo', async () => {
    // 9.a Sin sku
    const corruptoSinSku = {
      id_evento: 'evt-corrupto-1',
      tipo: 'StockBajoUmbral',
      datos: {
        id_bodega: 1,
        saldo: 4.0,
        stock_minimo: 10.0,
      },
    };
    await expect(procesarMensajeStockBajo(corruptoSinSku)).rejects.toThrow(
      'Payload de StockBajoUmbral inválido o corrupto'
    );

    // 9.b Sin saldo
    const corruptoSinSaldo = {
      id_evento: 'evt-corrupto-2',
      tipo: 'StockBajoUmbral',
      datos: {
        sku: 'LAC-0001',
        id_bodega: 1,
        stock_minimo: 10.0,
      },
    };
    await expect(procesarMensajeStockBajo(corruptoSinSaldo)).rejects.toThrow(
      'Payload de StockBajoUmbral inválido o corrupto'
    );

    // 9.c Tipo de evento incorrecto
    const corruptoTipoErroneo = {
      id_evento: 'evt-corrupto-3',
      tipo: 'OtroEvento',
      datos: {
        sku: 'LAC-0001',
        id_bodega: 1,
        saldo: 2.0,
        stock_minimo: 10.0,
      },
    };
    await expect(procesarMensajeStockBajo(corruptoTipoErroneo)).rejects.toThrow(
      'Payload de StockBajoUmbral inválido o corrupto'
    );
  });

  // -------------------------------------------------------------------------
  // Caso 10: GET /notificaciones filtra correctamente por el rol del usuario
  // (compras vs jefe_bodega), soporta ?leida=false y paginación, y POST /notificaciones/:id/leida marca leida: true.
  // -------------------------------------------------------------------------
  test('Caso 10: GET /notificaciones filtra por rol, soporta ?leida y paginación, y POST /:id/leida marca lectura', async () => {
    // Sembrar dos alertas distintas
    await procesarMensajeStockBajo({
      id_evento: 'evt-10-A',
      tipo: 'StockBajoUmbral',
      datos: { sku: 'PROD-10-A', id_bodega: 1, saldo: 2, stock_minimo: 10 },
    });
    await procesarMensajeStockBajo({
      id_evento: 'evt-10-B',
      tipo: 'StockBajoUmbral',
      datos: { sku: 'PROD-10-B', id_bodega: 2, saldo: 1, stock_minimo: 5 },
    });

    // 10.a Filtro por rol del usuario (compras ve 2 alertas correspondientes a su rol)
    const resCompras = await request(app)
      .get('/notificaciones?leida=false&page=1&per_page=10')
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Role', 'Compras');

    expect(resCompras.status).toBe(200);
    expect(resCompras.body.meta.total).toBe(2);
    expect(resCompras.body.meta.page).toBe(1);
    expect(resCompras.body.data.every((n) => n.rol_destino === 'compras')).toBe(true);

    // 10.b Paginación: page=1&per_page=1 devuelve 1 elemento pero total=2
    const resPaginada = await request(app)
      .get('/notificaciones?page=1&per_page=1')
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Role', 'Compras');

    expect(resPaginada.status).toBe(200);
    expect(resPaginada.body.data).toHaveLength(1);
    expect(resPaginada.body.meta.total).toBe(2);

    // 10.c POST /notificaciones/:id/leida marca como leída
    const notifId = resCompras.body.data[0].id_notificacion;
    const resLeida = await request(app)
      .post(`/notificaciones/${notifId}/leida`)
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Role', 'Compras');

    expect(resLeida.status).toBe(200);
    expect(resLeida.body.leida).toBe(true);
    expect(resLeida.body.leida_en).toBeDefined();

    // 10.d Al consultar con ?leida=false solo debe quedar 1 alerta pendiente para compras
    const resPendientes = await request(app)
      .get('/notificaciones?leida=false')
      .set('Authorization', `Bearer ${serviceToken}`)
      .set('X-User-Role', 'Compras');

    expect(resPendientes.status).toBe(200);
    expect(resPendientes.body.meta.total).toBe(1);
    expect(resPendientes.body.data[0].id_notificacion).not.toBe(notifId);
  });
});
