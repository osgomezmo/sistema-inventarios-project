require('dotenv').config();

const mysql = require('mysql2/promise');
const { config } = require('../src/config/env');

const PROVEEDORES = [
  {
    nit: '890.900.291-8',
    razon_social: 'Cooperativa de Lácteos y Cárnicos S.A.',
    telefono: '+57 601 7421100',
    email: 'pedidos@cooplacteos.com.co',
    direccion: 'Autopista Medellín Km 3.5, Cota',
    estado: 'ACTIVO',
    contactos: [
      {
        nombre: 'Claudia Marcela Ríos',
        cargo: 'Ejecutiva de cuentas clave',
        telefono: '+57 310 4512233',
        email: 'crios@cooplacteos.com.co',
      },
      {
        nombre: 'Jorge Eliécer Vargas',
        cargo: 'Coordinador de despachos en frío',
        telefono: '+57 311 8903344',
        email: 'despachos@cooplacteos.com.co',
      },
    ],
    productos: [
      { sku: 'LAC-0001', precio_compra: '3450.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'LAC-0002', precio_compra: '3950.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'LAC-0003', precio_compra: '2900.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'LAC-0004', precio_compra: '9100.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'LAC-0005', precio_compra: '20500.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'LAC-0006', precio_compra: '6900.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'CAR-0001', precio_compra: '19800.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'CAR-0002', precio_compra: '32400.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'CAR-0003', precio_compra: '13900.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'CAR-0004', precio_compra: '9300.00', dias_entrega: 1, estado: 'ACTIVO' },
    ],
  },
  {
    nit: '860.002.527-9',
    razon_social: 'Embotelladora Nacional de Bebidas S.A.S.',
    telefono: '+57 601 3804500',
    email: 'ventas.institucionales@embotelladoranacional.co',
    direccion: 'Calle 17 # 65B-90, Zona Industrial, Bogotá',
    estado: 'ACTIVO',
    contactos: [
      {
        nombre: 'Andrés Felipe Morales',
        cargo: 'Jefe comercial canal supermercados',
        telefono: '+57 315 6208899',
        email: 'amorales@embotelladoranacional.co',
      },
    ],
    productos: [
      { sku: 'BEB-0001', precio_compra: '4600.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'BEB-0002', precio_compra: '3300.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'BEB-0003', precio_compra: '2950.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'BEB-0004', precio_compra: '3650.00', dias_entrega: 3, estado: 'ACTIVO' },
      { sku: 'BEB-0005', precio_compra: '1100.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'BEB-0006', precio_compra: '1300.00', dias_entrega: 2, estado: 'INACTIVO' },
    ],
  },
  {
    nit: '890.100.577-6',
    razon_social: 'Distribuidora Mayorista de Abarrotes y Aseo S.A.',
    telefono: '+57 601 4128800',
    email: 'ordenes@mayoristaabarrotes.com.co',
    direccion: 'Avenida Centenario # 103-40, Fontibón, Bogotá',
    estado: 'ACTIVO',
    contactos: [
      {
        nombre: 'Patricia Elena Gómez',
        cargo: 'Directora de atención a cadenas',
        telefono: '+57 318 7745566',
        email: 'pgomez@mayoristaabarrotes.com.co',
      },
      {
        nombre: 'Camilo Ernesto Ruiz',
        cargo: 'Asesor línea aseo y hogar',
        telefono: '+57 316 3309911',
        email: 'cruiz@mayoristaabarrotes.com.co',
      },
    ],
    productos: [
      { sku: 'GRA-0001', precio_compra: '3300.00', dias_entrega: 3, estado: 'ACTIVO' },
      { sku: 'GRA-0002', precio_compra: '15800.00', dias_entrega: 3, estado: 'ACTIVO' },
      { sku: 'GRA-0003', precio_compra: '5600.00', dias_entrega: 3, estado: 'ACTIVO' },
      { sku: 'GRA-0004', precio_compra: '4700.00', dias_entrega: 4, estado: 'ACTIVO' },
      { sku: 'GRA-0005', precio_compra: '8500.00', dias_entrega: 3, estado: 'ACTIVO' },
      { sku: 'GRA-0006', precio_compra: '23900.00', dias_entrega: 3, estado: 'ACTIVO' },
      { sku: 'ASE-0001', precio_compra: '17200.00', dias_entrega: 4, estado: 'ACTIVO' },
      { sku: 'ASE-0002', precio_compra: '20100.00', dias_entrega: 4, estado: 'ACTIVO' },
      { sku: 'ASE-0003', precio_compra: '2200.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'ASE-0004', precio_compra: '2700.00', dias_entrega: 2, estado: 'ACTIVO' },
      { sku: 'ASE-0005', precio_compra: '5300.00', dias_entrega: 3, estado: 'ACTIVO' },
    ],
  },
  {
    nit: '900.245.180-4',
    razon_social: 'Central Agropecuaria y Panificadora de la Sabana S.A.S.',
    telefono: '+57 601 2943300',
    email: 'despachos@agrosabana.com.co',
    direccion: 'Carrera 80 # 2-51, Corabastos Bodega 14, Bogotá',
    estado: 'ACTIVO',
    contactos: [
      {
        nombre: 'Hernán Darío Castellanos',
        cargo: 'Coordinador de abastecimiento diario',
        telefono: '+57 320 5117788',
        email: 'hcastellanos@agrosabana.com.co',
      },
    ],
    productos: [
      { sku: 'PAN-0001', precio_compra: '5600.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'PAN-0002', precio_compra: '350.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'PAN-0003', precio_compra: '3100.00', dias_entrega: 1, estado: 'INACTIVO' },
      { sku: 'FRU-0001', precio_compra: '2100.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'FRU-0002', precio_compra: '1800.00', dias_entrega: 1, estado: 'ACTIVO' },
      { sku: 'FRU-0003', precio_compra: '3000.00', dias_entrega: 1, estado: 'ACTIVO' },
    ],
  },
  {
    nit: '800.198.342-6',
    razon_social: 'Comercializadora del Sur Ltda.',
    telefono: '+57 601 7102200',
    email: 'contacto@comercializadoradelsur.co',
    direccion: 'Autopista Sur # 57-12, Bogotá',
    estado: 'INACTIVO',
    contactos: [
      {
        nombre: 'Lucía Fernanda Ospina',
        cargo: 'Representante comercial',
        telefono: '+57 312 9081122',
        email: 'lospina@comercializadoradelsur.co',
      },
    ],
    productos: [],
  },
];

async function insertar(conexion, proveedores = PROVEEDORES) {
  let provInsertados = 0;
  let prodInsertados = 0;

  for (const prov of proveedores) {
    const [existe] = await conexion.query('SELECT id_proveedor FROM proveedores WHERE nit = ?', [prov.nit]);
    if (existe.length > 0) {
      continue;
    }

    const [res] = await conexion.query(
      `INSERT INTO proveedores (nit, razon_social, telefono, email, direccion, estado)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [prov.nit, prov.razon_social, prov.telefono, prov.email, prov.direccion, prov.estado]
    );
    const idProveedor = res.insertId;
    provInsertados += 1;

    for (const ct of prov.contactos || []) {
      await conexion.query(
        `INSERT INTO contactos (id_proveedor, nombre, cargo, telefono, email)
         VALUES (?, ?, ?, ?, ?)`,
        [idProveedor, ct.nombre, ct.cargo, ct.telefono, ct.email]
      );
    }

    for (const pr of prov.productos || []) {
      await conexion.query(
        `INSERT INTO productos_suministrados (id_proveedor, sku, precio_compra, dias_entrega, estado)
         VALUES (?, ?, ?, ?, ?)`,
        [idProveedor, pr.sku, pr.precio_compra, pr.dias_entrega, pr.estado]
      );
      prodInsertados += 1;
    }
  }

  return { provInsertados, prodInsertados };
}

async function sembrarDatosIniciales() {
  const conexion = await mysql.createConnection({
    host: config.db.host,
    port: config.db.port,
    user: config.db.user,
    password: config.db.password,
    database: config.db.database,
    timezone: 'Z',
    charset: 'utf8mb4',
    connectTimeout: 5000,
  });

  try {
    await conexion.beginTransaction();
    try {
      await conexion.query('SELECT nombre FROM migraciones_aplicadas FOR UPDATE');
      const [conteo] = await conexion.query('SELECT COUNT(*) AS n FROM proveedores');
      if (Number(conteo[0].n) > 0) {
        await conexion.rollback();
        console.log('[MS-Proveedores] La base ya tiene proveedores: no se siembran datos iniciales.');
        return false;
      }

      const { provInsertados, prodInsertados } = await insertar(conexion);
      await conexion.commit();
      console.log(
        `[MS-Proveedores] Datos iniciales sembrados: ${provInsertados} proveedores y ${prodInsertados} productos suministrados.`
      );
      return true;
    } catch (err) {
      await conexion.rollback();
      throw err;
    }
  } finally {
    await conexion.end();
  }
}

if (require.main === module) {
  sembrarDatosIniciales().catch((err) => {
    console.error('[MS-Proveedores] Error sembrando datos iniciales:', err.message);
    process.exit(1);
  });
}

module.exports = { PROVEEDORES, insertar, sembrarDatosIniciales };
