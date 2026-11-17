const request = require('supertest');
const app = require('../src/app');
const storage = require('../src/repositories/storage');
const notificador = require('../src/services/notificador');
const { procesarMensajeStockBajo } = require('../src/consumers/stockBajo.consumer');
const { AppError } = require('../src/utils/errors');

describe('MS-Notificaciones | Mocking de Endpoints, Casos Reales, Absurdos y Fuera de Rango', () => {
  const serviceToken = 'token-secreto-gateway-2026';

  function headers(rol = 'compras', userId = '25', extra = {}) {
    const base = {
      Authorization: `Bearer ${serviceToken}`,
    };
    if (userId !== null) base['X-User-Id'] = String(userId);
    if (rol !== null) base['X-User-Role'] = rol;
    return { ...base, ...extra };
  }

  beforeEach(() => {
    storage._resetMemoriaTest();
    process.env.SERVICE_TOKEN = serviceToken;
    process.env.STORAGE_DRIVER = 'local';
    process.env.PUSH_DRIVER = 'console';
    jest.restoreAllMocks();
  });

  describe('1. Mocking explicito de endpoints con entradas esperadas', () => {
    test('POST /dispositivos invoca storage.guardarDispositivo y notificador.suscribirATema con datos normalizados', async () => {
      const spyGuardar = jest.spyOn(storage, 'guardarDispositivo').mockResolvedValueOnce({
        id_dispositivo: 'disp-mock-001',
        id_usuario: '25',
        rol: 'compras',
        token_fcm: 'fcm-token-xyz',
        plataforma: 'web',
        registrado_en: '2026-11-16T21:00:00.000Z',
      });
      const spySuscribir = jest.spyOn(notificador, 'suscribirATema').mockResolvedValueOnce({
        success: true,
        tema: 'rol_compras',
      });

      const res = await request(app)
        .post('/dispositivos')
        .set(headers('Compras', '25'))
        .send({ token_fcm: '  fcm-token-xyz  ', plataforma: '  WEB ' });

      expect(res.status).toBe(201);
      expect(spyGuardar).toHaveBeenCalledWith({
        id_usuario: '25',
        rol: 'compras',
        token_fcm: 'fcm-token-xyz',
        plataforma: 'web',
      });
      expect(spySuscribir).toHaveBeenCalledWith('fcm-token-xyz', 'compras');
      expect(res.body.id_dispositivo).toBe('disp-mock-001');
    });

    test('GET /notificaciones y POST /notificaciones/:id/leida operan con mocks de storage', async () => {
      jest.spyOn(storage, 'listarNotificaciones').mockResolvedValueOnce({
        data: [
          {
            id_notificacion: 'not-mock-1',
            tipo: 'STOCK_BAJO',
            titulo: 'Alerta de Stock Bajo',
            mensaje: 'El producto LAC-0001 quedo con saldo 3',
            rol_destino: 'jefe_bodega',
            datos: { sku: 'LAC-0001', id_bodega: 1, saldo: 3, stock_minimo: 10 },
            leida: false,
            creada_en: '2026-11-16T21:00:00.000Z',
          },
        ],
        meta: { page: 1, per_page: 20, total: 1 },
      });

      const resList = await request(app)
        .get('/notificaciones?leida=false&page=1&per_page=20')
        .set(headers('Jefe de bodega', '12'));

      expect(resList.status).toBe(200);
      expect(storage.listarNotificaciones).toHaveBeenCalledWith({
        rol: 'jefe_bodega',
        leida: false,
        page: 1,
        perPage: 20,
      });
      expect(resList.body.data[0].datos.sku).toBe('LAC-0001');

      jest.spyOn(storage, 'obtenerNotificacionPorId').mockResolvedValueOnce({
        id_notificacion: 'not-mock-1',
        rol_destino: 'jefe_bodega',
        leida: false,
      });
      jest.spyOn(storage, 'marcarNotificacionLeida').mockResolvedValueOnce({
        id_notificacion: 'not-mock-1',
        rol_destino: 'jefe_bodega',
        leida: true,
        leida_en: '2026-11-16T21:05:00.000Z',
      });

      const resLeida = await request(app)
        .post('/notificaciones/not-mock-1/leida')
        .set(headers('jefe_bodega', '12'));

      expect(resLeida.status).toBe(200);
      expect(resLeida.body.leida).toBe(true);
    });
  });

  describe('2. Casos absurdos, ilogicos y fuera de rango', () => {
    test('POST /dispositivos rechaza tipos absurdos (booleanos, numeros, objetos, espacios) y roles invalidos con 422', async () => {
      for (const bodyAbsurdo of [
        { token_fcm: true, plataforma: 'web' },
        { token_fcm: 123456, plataforma: 'android' },
        { token_fcm: '   ', plataforma: '   ' },
        { token_fcm: ['token'], plataforma: { os: 'ios' } },
      ]) {
        const res = await request(app)
          .post('/dispositivos')
          .set(headers('compras', '10'))
          .send(bodyAbsurdo);

        expect(res.status).toBe(422);
        expect(res.body.error.codigo).toBe('VALIDACION_FALLIDA');
      }

      // Rol desconocido en X-User-Role se normaliza a null y es rechazado con 422
      const resRolInvalido = await request(app)
        .post('/dispositivos')
        .set(headers('visitante_externo', '10'))
        .send({ token_fcm: 'tok-1', plataforma: 'web' });

      expect(resRolInvalido.status).toBe(422);
      expect(resRolInvalido.body.error.detalles).toHaveProperty('rol');
    });

    test('GET /notificaciones rechaza paginacion fuera de rango (page=0, per_page=101, negativos, letras) y leida invalida con 422', async () => {
      for (const qs of [
        'page=0',
        'page=-5',
        'page=abc',
        'per_page=0',
        'per_page=101',
        'per_page=mil',
        'leida=1',
        'leida=si',
      ]) {
        const res = await request(app)
          .get(`/notificaciones?${qs}`)
          .set(headers('compras', '10'));

        expect(res.status).toBe(422);
        expect(res.body.error.codigo).toBe('PARAMETROS_INVALIDOS');
      }
    });

    test('POST /notificaciones/:id/leida rechaza con 403 cuando otro rol intenta marcar una alerta ajena y 404 si no existe', async () => {
      await procesarMensajeStockBajo({
        id_evento: 'evt-rol-ajeno-1',
        tipo: 'StockBajoUmbral',
        datos: { sku: 'CAR-0001', id_bodega: 1, saldo: 1, stock_minimo: 5 },
      });

      const listaCompras = await storage.listarNotificaciones({ rol: 'compras' });
      const idNotifCompras = listaCompras.data[0].id_notificacion;

      // Un jefe_bodega o gerente intenta marcar como leida la notificacion de compras -> 403
      const resProhibido = await request(app)
        .post(`/notificaciones/${idNotifCompras}/leida`)
        .set(headers('jefe_bodega', '20'));

      expect(resProhibido.status).toBe(403);
      expect(resProhibido.body.error.codigo).toBe('SIN_PERMISO');

      // ID inexistente -> 404
      const res404 = await request(app)
        .post('/notificaciones/id-no-existe-999/leida')
        .set(headers('admin', '1'));

      expect(res404.status).toBe(404);
      expect(res404.body.error.codigo).toBe('NOTIFICACION_NO_ENCONTRADA');
    });

    test('rechaza JSON mal formado con 400 y maneja excepciones inesperadas con 500 en formato canonico', async () => {
      const resBadJson = await request(app)
        .post('/dispositivos')
        .set({ ...headers('compras', '10'), 'Content-Type': 'application/json' })
        .send('{"token_fcm": "incompleto"');

      expect(resBadJson.status).toBe(400);
      expect(resBadJson.body).toHaveProperty('error');

      jest
        .spyOn(storage, 'listarNotificaciones')
        .mockRejectedValueOnce(new AppError(500, 'FALLO_STORAGE', 'Error simulado de Firestore'));

      const res500 = await request(app).get('/notificaciones').set(headers('admin', '1'));
      expect(res500.status).toBe(500);
      expect(res500.body.error.codigo).toBe('FALLO_STORAGE');
    });

    test('procesarMensajeStockBajo rechaza payloads nulos, tipos no numericos en saldo/stock_minimo y eventos sin id_evento', async () => {
      for (const corrupto of [
        null,
        'texto',
        {},
        { id_evento: '', tipo: 'StockBajoUmbral', datos: {} },
        {
          id_evento: 'evt-bad-1',
          tipo: 'StockBajoUmbral',
          datos: { sku: 'LAC-1', id_bodega: 1, saldo: 'no-numero', stock_minimo: 5 },
        },
        {
          id_evento: 'evt-bad-2',
          tipo: 'StockBajoUmbral',
          datos: { sku: 'LAC-1', id_bodega: 1, saldo: 2, stock_minimo: NaN },
        },
      ]) {
        await expect(procesarMensajeStockBajo(corrupto)).rejects.toThrow();
      }
    });
  });
});
