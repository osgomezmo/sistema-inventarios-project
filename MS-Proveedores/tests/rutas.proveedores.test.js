const request = require('supertest');

process.env.SERVICE_TOKEN = 'test-service-token';

jest.mock('../src/config/db', () => ({
  verificarConexionDb: jest.fn(),
  ejecutarConsulta: jest.fn(),
  conTransaccion: jest.fn(),
  cerrarPool: jest.fn(),
}));

jest.mock('../src/repositories/proveedores.repository', () => ({
  listarProveedores: jest.fn(),
  obtenerProveedorPorId: jest.fn(),
  crearProveedor: jest.fn(),
  actualizarProveedor: jest.fn(),
  cambiarEstadoProveedor: jest.fn(),
  crearContacto: jest.fn(),
  actualizarContacto: jest.fn(),
  eliminarContacto: jest.fn(),
  listarProductosProveedor: jest.fn(),
  upsertProductoProveedor: jest.fn(),
  eliminarProductoProveedor: jest.fn(),
}));

const app = require('../src/app');
const db = require('../src/config/db');
const repo = require('../src/repositories/proveedores.repository');
const { AppError } = require('../src/utils/errors');

function headers(rol = 'compras', extra = {}) {
  const base = {
    Authorization: 'Bearer test-service-token',
    'X-User-Id': '10',
  };
  if (rol !== null) {
    base['X-User-Role'] = rol;
  }
  return { ...base, ...extra };
}

describe('MS-Proveedores | Rutas HTTP, seguridad y reglas de negocio', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Salud del servicio y seguridad', () => {
    test('GET /health responde 200 publicamente y /health/ready valida conexion DB', async () => {
      const resLive = await request(app).get('/health');
      expect(resLive.status).toBe(200);
      expect(resLive.body).toEqual({ status: 'ok', service: 'ms-proveedores' });
      expect(resLive.headers['x-correlation-id']).toBeTruthy();

      db.verificarConexionDb.mockResolvedValueOnce(true);
      const resReady = await request(app)
        .get('/health/ready')
        .set('X-Correlation-Id', 'corr-123');
      expect(resReady.status).toBe(200);
      expect(resReady.headers['x-correlation-id']).toBe('corr-123');

      db.verificarConexionDb.mockRejectedValueOnce(
        new AppError(503, 'SERVICIO_NO_DISPONIBLE', 'La base de datos no está disponible.')
      );
      const resDown = await request(app).get('/health/ready');
      expect(resDown.status).toBe(503);
      expect(resDown.body.error.codigo).toBe('SERVICIO_NO_DISPONIBLE');
    });

    test('rechaza peticiones sin token o con token invalido (401) y valida RBAC (403)', async () => {
      const sinAuth = await request(app).get('/proveedores');
      expect(sinAuth.status).toBe(401);
      expect(sinAuth.body.error.codigo).toBe('NO_AUTENTICADO');

      const tokenMalo = await request(app)
        .get('/proveedores')
        .set('Authorization', 'Bearer token-incorrecto');
      expect(tokenMalo.status).toBe(401);

      const sinPermiso = await request(app)
        .post('/proveedores')
        .set(headers('jefe_bodega'))
        .send({
          nit: '900111222',
          razon_social: 'Proveedor Test',
          telefono: '3001112233',
          email: 'a@b.co',
          direccion: 'Calle 1',
        });
      expect(sinPermiso.status).toBe(403);
      expect(sinPermiso.body.error.codigo).toBe('SIN_PERMISO');
    });

    test('permite llamadas internas sin X-User-Role en endpoints de lectura', async () => {
      repo.obtenerProveedorPorId.mockResolvedValueOnce({
        id_proveedor: 1,
        nit: '900123456-7',
        razon_social: 'Insumos Colombia S.A.',
        estado: 'ACTIVO',
        contactos: [],
      });

      const res = await request(app).get('/proveedores/1').set(headers(null));
      expect(res.status).toBe(200);
      expect(res.body.estado).toBe('ACTIVO');
    });
  });

  describe('Casos reales de CRUD, contactos y productos', () => {
    test('lista proveedores filtrando por estado, texto y SKU normalizado', async () => {
      repo.listarProveedores.mockResolvedValueOnce({
        data: [{ id_proveedor: 1, nit: '900123', estado: 'ACTIVO', contactos: [] }],
        total: 1,
      });

      const res = await request(app)
        .get('/proveedores?q=Andina&estado=activo&sku=sku-001&page=1&per_page=10')
        .set(headers('gerente'));

      expect(res.status).toBe(200);
      expect(repo.listarProveedores).toHaveBeenCalledWith({
        q: 'Andina',
        estado: 'ACTIVO',
        sku: 'SKU-001',
        page: 1,
        perPage: 10,
      });
      expect(res.body.meta).toEqual({ page: 1, per_page: 10, total: 1 });
    });

    test('crea, actualiza, inactiva y activa proveedor correctamente', async () => {
      const creado = {
        id_proveedor: 7,
        nit: '800555666-1',
        razon_social: 'Comercializadora Norte',
        telefono: '3112223344',
        email: 'ventas@norte.co',
        direccion: 'Carrera 15 # 20-10',
        estado: 'ACTIVO',
        contactos: [],
      };
      repo.crearProveedor.mockResolvedValueOnce(creado);

      const resPost = await request(app)
        .post('/proveedores')
        .set(headers('compras'))
        .send({
          nit: '800555666-1',
          razon_social: 'Comercializadora Norte',
          telefono: '3112223344',
          email: 'VENTAS@NORTE.CO',
          direccion: 'Carrera 15 # 20-10',
        });
      expect(resPost.status).toBe(201);
      expect(resPost.body.id_proveedor).toBe(7);

      repo.actualizarProveedor.mockResolvedValueOnce({ ...creado, telefono: '3209998877' });
      const resPut = await request(app)
        .put('/proveedores/7')
        .set(headers('Administrador'))
        .send({
          razon_social: 'Comercializadora Norte',
          telefono: '3209998877',
          email: 'ventas@norte.co',
          direccion: 'Carrera 15 # 20-10',
        });
      expect(resPut.status).toBe(200);
      expect(resPut.body.telefono).toBe('3209998877');

      repo.cambiarEstadoProveedor.mockResolvedValueOnce({ ...creado, estado: 'INACTIVO' });
      const resInact = await request(app)
        .post('/proveedores/7/inactivar')
        .set(headers('compras'));
      expect(resInact.status).toBe(200);
      expect(resInact.body.estado).toBe('INACTIVO');

      repo.cambiarEstadoProveedor.mockResolvedValueOnce({ ...creado, estado: 'ACTIVO' });
      const resAct = await request(app)
        .post('/proveedores/7/activar')
        .set(headers('compras'));
      expect(resAct.status).toBe(200);
      expect(resAct.body.estado).toBe('ACTIVO');
    });

    test('gestiona contactos y productos suministrados con respuestas esperadas', async () => {
      repo.crearContacto.mockResolvedValueOnce({
        id_contacto: 3,
        nombre: 'Carlos Perez',
        cargo: 'Asesor',
        telefono: '3009876543',
        email: 'carlos@norte.co',
      });
      const resContPost = await request(app)
        .post('/proveedores/7/contactos')
        .set(headers('compras'))
        .send({
          nombre: 'Carlos Perez',
          cargo: 'Asesor',
          telefono: '3009876543',
          email: 'carlos@norte.co',
        });
      expect(resContPost.status).toBe(201);

      repo.eliminarContacto.mockResolvedValueOnce(true);
      const resContDel = await request(app)
        .delete('/proveedores/7/contactos/3')
        .set(headers('admin'));
      expect(resContDel.status).toBe(204);

      repo.upsertProductoProveedor.mockResolvedValueOnce({
        sku: 'CEM-50KG',
        precio_compra: 34500.5,
        dias_entrega: 3,
        estado: 'ACTIVO',
      });
      const resProdPut = await request(app)
        .put('/proveedores/7/productos/cem-50kg')
        .set(headers('compras'))
        .send({ precio_compra: 34500.5, dias_entrega: 3 });
      expect(resProdPut.status).toBe(200);
      expect(repo.upsertProductoProveedor).toHaveBeenCalledWith(7, 'CEM-50KG', {
        precio_compra: '34500.50',
        dias_entrega: 3,
        estado: 'ACTIVO',
      });

      repo.eliminarProductoProveedor.mockResolvedValueOnce(true);
      const resProdDel = await request(app)
        .delete('/proveedores/7/productos/cem-50kg')
        .set(headers('admin'));
      expect(resProdDel.status).toBe(204);
    });
  });

  describe('Casos ilogicos, fuera de rango y manejo de errores', () => {
    test('retorna 422 si el filtro estado de proveedores es invalido', async () => {
      const res = await request(app)
        .get('/proveedores?estado=SUSPENDIDO')
        .set(headers('compras'));
      expect(res.status).toBe(422);
      expect(res.body.error.codigo).toBe('VALIDACION');
    });

    test('retorna 409 NIT_DUPLICADO al crear proveedor existente y 404 NO_EXISTE al consultar inexistente', async () => {
      repo.crearProveedor.mockRejectedValueOnce(
        new AppError(409, 'NIT_DUPLICADO', 'Ya existe un proveedor con ese NIT.', {
          nit: ['El NIT ya está registrado.'],
        })
      );
      const resDup = await request(app)
        .post('/proveedores')
        .set(headers('compras'))
        .send({
          nit: '900123456-7',
          razon_social: 'Empresa Duplicada',
          telefono: '3001112233',
          email: 'dup@empresa.co',
          direccion: 'Calle 1 # 2-3',
        });
      expect(resDup.status).toBe(409);
      expect(resDup.body.error.codigo).toBe('NIT_DUPLICADO');

      repo.obtenerProveedorPorId.mockResolvedValueOnce(null);
      const resNotFound = await request(app).get('/proveedores/9999').set(headers('compras'));
      expect(resNotFound.status).toBe(404);
      expect(resNotFound.body.error.codigo).toBe('NO_EXISTE');
    });

    test('rechaza JSON mal formado (400), ruta inexistente (404), IDs fuera de rango (400) y SKU invalido (400)', async () => {
      const resBadJson = await request(app)
        .post('/proveedores')
        .set({ ...headers('compras'), 'Content-Type': 'application/json' })
        .send('{"nit": "900123"');
      expect(resBadJson.status).toBe(400);
      expect(resBadJson.body.error.codigo).toBe('PETICION_INVALIDA');

      const res404 = await request(app).get('/ruta-inexistente').set(headers('admin'));
      expect(res404.status).toBe(404);
      expect(res404.body.error.codigo).toBe('NO_EXISTE');

      const resIdFueraRango = await request(app)
        .get('/proveedores/2147483648')
        .set(headers('admin'));
      expect(resIdFueraRango.status).toBe(400);

      const resBadSku = await request(app)
        .put('/proveedores/1/productos/SKU%20INVALIDO!')
        .set(headers('compras'))
        .send({ precio_compra: 100, dias_entrega: 1 });
      expect(resBadSku.status).toBe(400);
      expect(resBadSku.body.error.codigo).toBe('PETICION_INVALIDA');
    });

    test('oculta detalles internos y devuelve 500 ERROR_INTERNO ante excepcion inesperada', async () => {
      repo.listarProveedores.mockRejectedValueOnce(new Error('Fallo interno simulado'));
      const res = await request(app).get('/proveedores').set(headers('admin'));
      expect(res.status).toBe(500);
      expect(res.body.error.codigo).toBe('ERROR_INTERNO');
      expect(res.body.error.mensaje).not.toContain('simulado');
    });
  });
});
