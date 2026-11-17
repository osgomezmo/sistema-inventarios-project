const mysql = require('mysql2/promise');

jest.mock('mysql2/promise', () => ({
  createPool: jest.fn(),
}));

const db = require('../src/config/db');
const repo = require('../src/repositories/proveedores.repository');
const { AppError } = require('../src/utils/errors');

describe('MS-Proveedores | Repositorio y traduccion de errores MySQL', () => {
  let mockPool;
  let mockConn;

  beforeEach(async () => {
    jest.clearAllMocks();
    await db.cerrarPool();

    mockConn = {
      query: jest.fn(),
      beginTransaction: jest.fn().mockResolvedValue(undefined),
      commit: jest.fn().mockResolvedValue(undefined),
      rollback: jest.fn().mockResolvedValue(undefined),
      release: jest.fn(),
    };
    mockPool = {
      query: jest.fn(),
      getConnection: jest.fn().mockResolvedValue(mockConn),
      end: jest.fn().mockResolvedValue(undefined),
    };
    mysql.createPool.mockReturnValue(mockPool);
  });

  afterEach(async () => {
    await db.cerrarPool();
  });

  test('traduce errores de conexion MySQL a 503 SERVICIO_NO_DISPONIBLE', async () => {
    const errConn = new Error('connect ECONNREFUSED');
    errConn.code = 'ECONNREFUSED';
    mockPool.query.mockRejectedValueOnce(errConn);

    await expect(db.verificarConexionDb()).rejects.toMatchObject({
      statusCode: 503,
      codigo: 'SERVICIO_NO_DISPONIBLE',
    });
  });

  test('crearProveedor traduce ER_DUP_ENTRY a 409 NIT_DUPLICADO', async () => {
    const errDup = new Error('Duplicate entry');
    errDup.code = 'ER_DUP_ENTRY';
    mockPool.query.mockRejectedValueOnce(errDup);

    await expect(
      repo.crearProveedor({
        nit: '900123456-7',
        razon_social: 'Empresa X',
        telefono: '3001112233',
        email: 'a@b.co',
        direccion: 'Calle 1',
      })
    ).rejects.toMatchObject({
      statusCode: 409,
      codigo: 'NIT_DUPLICADO',
    });
  });

  test('upsertProductoProveedor ejecuta rollback si el proveedor no existe dentro de transaccion', async () => {
    mockConn.query.mockResolvedValueOnce([[]]);

    await expect(
      repo.upsertProductoProveedor(999, 'SKU-01', {
        precio_compra: '1200.00',
        dias_entrega: 2,
        estado: 'ACTIVO',
      })
    ).rejects.toBeInstanceOf(AppError);

    expect(mockConn.beginTransaction).toHaveBeenCalledTimes(1);
    expect(mockConn.rollback).toHaveBeenCalledTimes(1);
    expect(mockConn.commit).not.toHaveBeenCalled();
    expect(mockConn.release).toHaveBeenCalledTimes(1);
  });
});
