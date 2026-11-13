// Datos maestros de ejemplo (sintéticos). Ninguna empresa, persona ni cifra es real.
import type { Bodega, Categoria, Producto, Proveedor, ProductoSuministrado, RolConPermisos, Usuario } from '../types'

export const usuarios: Usuario[] = [
  { id: 1, nombre: 'Andrea Ríos', email: 'andrea.rios@supermercado.example', rol: 'ADMINISTRADOR', estado: 'ACTIVO', ultimo_acceso: '2026-10-29T13:05:00Z' },
  { id: 2, nombre: 'Laura Gómez', email: 'laura.gomez@supermercado.example', rol: 'JEFE_BODEGA', estado: 'ACTIVO', ultimo_acceso: '2026-10-29T12:41:00Z' },
  { id: 3, nombre: 'Julián Cárdenas', email: 'julian.cardenas@supermercado.example', rol: 'JEFE_BODEGA', estado: 'ACTIVO', ultimo_acceso: '2026-10-29T11:58:00Z' },
  { id: 4, nombre: 'Camilo Arango', email: 'camilo.arango@supermercado.example', rol: 'COMPRAS', estado: 'ACTIVO', ultimo_acceso: '2026-10-29T13:20:00Z' },
  { id: 5, nombre: 'Marta Lucía Ospina', email: 'marta.ospina@supermercado.example', rol: 'GERENTE', estado: 'ACTIVO', ultimo_acceso: '2026-10-28T22:10:00Z' },
  { id: 6, nombre: 'Sergio Valencia', email: 'sergio.valencia@supermercado.example', rol: 'JEFE_BODEGA', estado: 'INACTIVO', ultimo_acceso: '2026-09-30T20:02:00Z' },
]

export const roles: RolConPermisos[] = [
  { id_rol: 1, nombre: 'ADMINISTRADOR', permisos: ['usuarios.*', 'catalogo.*', 'bodegas.*', 'stock.ver', 'movimientos.*', 'devoluciones_cliente.*', 'proveedores.*', 'ordenes.*', 'ordenes.aprobar', 'ordenes.recibir', 'devoluciones_proveedor.*', 'reportes.ver'] },
  { id_rol: 2, nombre: 'JEFE_BODEGA', permisos: ['catalogo.ver', 'bodegas.*', 'stock.ver', 'movimientos.*', 'devoluciones_cliente.*', 'proveedores.ver', 'ordenes.ver', 'ordenes.recibir', 'devoluciones_proveedor.*', 'reportes.ver'] },
  { id_rol: 3, nombre: 'COMPRAS', permisos: ['catalogo.ver', 'bodegas.ver', 'stock.ver', 'proveedores.*', 'ordenes.*', 'devoluciones_proveedor.*', 'reportes.ver'] },
  { id_rol: 4, nombre: 'GERENTE', permisos: ['catalogo.ver', 'bodegas.ver', 'stock.ver', 'movimientos.ver', 'devoluciones_cliente.ver', 'proveedores.ver', 'ordenes.ver', 'ordenes.aprobar', 'reportes.ver'] },
]

export const bodegas: Bodega[] = [
  { id_bodega: 1, codigo: 'B1', nombre: 'Bodega Principal', direccion: 'Carrera 23 # 64-15, Manizales', estado: 'ACTIVO' },
  { id_bodega: 2, codigo: 'B2', nombre: 'Bodega Norte', direccion: 'Avenida Santander # 70-30, Manizales', estado: 'ACTIVO' },
  { id_bodega: 3, codigo: 'B3', nombre: 'Cuarto frío', direccion: 'Carrera 23 # 64-15, sótano, Manizales', estado: 'ACTIVO' },
  { id_bodega: 4, codigo: 'B4', nombre: 'Bodega Sur', direccion: 'Calle 48 # 12-05, Manizales', estado: 'INACTIVO' },
]

const cat = (id_categoria: number, nombre: string, descripcion: string, id_categoria_padre: number | null = null, estado: Categoria['estado'] = 'ACTIVO'): Categoria =>
  ({ id_categoria, nombre, descripcion, id_categoria_padre, estado })

export const categorias: Categoria[] = [
  cat(1, 'Abarrotes', 'Granos, aceites, café y despensa'),
  cat(11, 'Granos', 'Arroz, fríjol y lenteja', 1),
  cat(12, 'Aceites y grasas', 'Aceites vegetales', 1),
  cat(13, 'Café y chocolate', 'Café molido y chocolate de mesa', 1),
  cat(2, 'Lácteos', 'Leches, yogures y quesos'),
  cat(21, 'Leches', 'Leche entera y deslactosada', 2),
  cat(22, 'Yogures', 'Yogures y bebidas lácteas', 2),
  cat(23, 'Quesos', 'Quesos frescos', 2),
  cat(3, 'Carnes', 'Res y pollo'),
  cat(31, 'Res', 'Cortes y carne molida de res', 3),
  cat(32, 'Pollo', 'Presas y pechuga', 3),
  cat(4, 'Frutas y verduras', 'Productos frescos por kilo'),
  cat(41, 'Frutas', 'Frutas frescas', 4),
  cat(42, 'Verduras', 'Verduras y tubérculos', 4),
  cat(5, 'Bebidas', 'Aguas, gaseosas y jugos'),
  cat(51, 'Aguas', 'Agua embotellada', 5),
  cat(52, 'Gaseosas', 'Bebidas gaseosas', 5),
  cat(53, 'Jugos', 'Jugos y néctares', 5),
  cat(6, 'Aseo', 'Aseo del hogar'),
  cat(61, 'Detergentes', 'Detergentes para ropa', 6),
  cat(62, 'Limpieza', 'Limpiadores y papel', 6),
  cat(7, 'Cuidado personal', 'Higiene personal'),
  cat(8, 'Panadería', 'Pan y repostería', null, 'INACTIVO'),
]

type FilaProducto = [sku: string, nombre: string, marca: string, id_categoria: number, unidad: Producto['unidad_medida'], precio: number, minimo: number, descripcion: string]

const filas: FilaProducto[] = [
  ['ABA-0112', 'Arroz blanco 5 kg', 'Grano de Oro', 11, 'UNIDAD', 24900, 120, 'Arroz blanco de grano largo, bolsa de 5 kg'],
  ['ABA-0118', 'Fríjol cargamanto 1 kg', 'La Vereda', 11, 'UNIDAD', 11800, 60, 'Fríjol cargamanto rojo, bolsa de 1 kg'],
  ['ABA-0131', 'Lenteja 500 g', 'La Vereda', 11, 'UNIDAD', 4200, 80, 'Lenteja seleccionada, bolsa de 500 g'],
  ['ABA-0204', 'Aceite de girasol 3 L', 'Campo Sol', 12, 'UNIDAD', 32900, 40, 'Aceite vegetal de girasol, botella de 3 L'],
  ['ABA-0310', 'Café molido 500 g', 'Alto de Caldas', 13, 'UNIDAD', 18500, 70, 'Café tostado y molido, tueste medio'],
  ['ABA-0322', 'Chocolate de mesa 500 g', 'Cacao Real', 13, 'UNIDAD', 9800, 50, 'Chocolate de mesa con canela, 16 pastillas'],
  ['LAC-0001', 'Leche entera UHT 1 L', 'La Pradera', 21, 'UNIDAD', 4600, 300, 'Leche entera ultrapasteurizada, bolsa de 1 L'],
  ['LAC-0014', 'Leche deslactosada 1 L', 'La Pradera', 21, 'UNIDAD', 5100, 200, 'Leche deslactosada semidescremada, caja de 1 L'],
  ['LAC-0102', 'Yogur de fresa 1 L', 'La Pradera', 22, 'UNIDAD', 8900, 60, 'Yogur con trozos de fresa, botella de 1 L'],
  ['LAC-0201', 'Queso campesino 500 g', 'La Pradera', 23, 'UNIDAD', 12400, 40, 'Queso fresco campesino, bloque de 500 g'],
  ['CAR-0010', 'Carne molida de res', 'El Roble', 31, 'KILO', 26900, 50, 'Carne molida de res, porcionada en bandeja'],
  ['CAR-0105', 'Pechuga de pollo', 'El Roble', 32, 'KILO', 17900, 60, 'Pechuga de pollo sin hueso, refrigerada'],
  ['FRU-0031', 'Banano criollo', 'Hortalizas de Caldas', 41, 'KILO', 3200, 80, 'Banano criollo por kilo'],
  ['FRU-0044', 'Tomate chonto', 'Hortalizas de Caldas', 42, 'KILO', 4800, 70, 'Tomate chonto maduro por kilo'],
  ['FRU-0052', 'Papa pastusa', 'Hortalizas de Caldas', 42, 'KILO', 2900, 150, 'Papa pastusa lavada por kilo'],
  ['FRU-0067', 'Aguacate Hass', 'Hortalizas de Caldas', 41, 'KILO', 9600, 30, 'Aguacate Hass por kilo'],
  ['BEB-0044', 'Agua sin gas 600 ml', 'Cumbre', 51, 'UNIDAD', 2200, 240, 'Agua potable sin gas, botella de 600 ml'],
  ['BEB-0120', 'Gaseosa cola 1,5 L', 'Cumbre', 52, 'UNIDAD', 6200, 120, 'Bebida gaseosa sabor cola, botella de 1,5 L'],
  ['BEB-0207', 'Jugo de naranja 1 L', 'Cumbre', 53, 'UNIDAD', 7400, 60, 'Jugo de naranja con pulpa, caja de 1 L'],
  ['ASE-0207', 'Detergente líquido 3 L', 'Aseo Total', 61, 'UNIDAD', 29800, 40, 'Detergente líquido para ropa, garrafa de 3 L'],
  ['ASE-0450', 'Limpiador desinfectante 2 L', 'Aseo Total', 62, 'UNIDAD', 11900, 30, 'Limpiador multiusos con aroma a lavanda'],
  ['ASE-0512', 'Papel higiénico x12', 'Aseo Total', 62, 'UNIDAD', 23900, 50, 'Papel higiénico doble hoja, paca de 12 rollos'],
  ['CUI-0018', 'Crema dental 100 ml', 'Cuidado Natural', 7, 'UNIDAD', 6900, 60, 'Crema dental con flúor, tubo de 100 ml'],
  ['CUI-0103', 'Champú 400 ml', 'Cuidado Natural', 7, 'UNIDAD', 14900, 35, 'Champú para uso diario, frasco de 400 ml'],
  ['PAN-0005', 'Pan tajado 500 g', 'Molino San Mateo', 8, 'UNIDAD', 6500, 30, 'Pan tajado blanco (descontinuado)'],
]

export const productos: Producto[] = filas.map(([sku, nombre, marca, id_categoria, unidad_medida, precio_venta, stock_minimo, descripcion], i) => ({
  id_producto: i + 1,
  sku,
  nombre,
  descripcion,
  marca,
  id_categoria,
  unidad_medida,
  precio_venta,
  stock_minimo,
  estado: sku.startsWith('PAN') ? 'INACTIVO' : 'ACTIVO',
}))

export const proveedores: Proveedor[] = [
  { id_proveedor: 1, nit: '900.481.227-3', razon_social: 'Distribuidora Andina de Granos S.A.S.', telefono: '606 884 1020', email: 'pedidos@andinagranos.example', direccion: 'Parque Industrial Juanchito, Manizales', estado: 'ACTIVO',
    contactos: [{ id_contacto: 1, nombre: 'Diana Marcela López', cargo: 'Ejecutiva de cuenta', telefono: '310 455 2091', email: 'dlopez@andinagranos.example' }] },
  { id_proveedor: 2, nit: '900.112.584-1', razon_social: 'Lácteos La Pradera S.A.S.', telefono: '606 872 4410', email: 'ventas@lapradera.example', direccion: 'Vereda La Cabaña, Villamaría', estado: 'ACTIVO',
    contactos: [{ id_contacto: 2, nombre: 'Hernán Zuluaga', cargo: 'Jefe de despachos', telefono: '315 602 7788', email: 'hzuluaga@lapradera.example' }, { id_contacto: 3, nombre: 'Paola Giraldo', cargo: 'Cartera', telefono: '606 872 4411', email: 'cartera@lapradera.example' }] },
  { id_proveedor: 3, nit: '890.807.311-6', razon_social: 'Frigorífico El Roble S.A.S.', telefono: '606 891 3300', email: 'comercial@elroble.example', direccion: 'Km 7 vía al Magdalena, Manizales', estado: 'ACTIVO',
    contactos: [{ id_contacto: 4, nombre: 'Óscar Henao', cargo: 'Representante comercial', telefono: '320 118 4502', email: 'ohenao@elroble.example' }] },
  { id_proveedor: 4, nit: '810.004.562-9', razon_social: 'Hortalizas de Caldas Ltda.', telefono: '606 878 0915', email: 'pedidos@hortalizascaldas.example', direccion: 'Plaza de mercado, bodega 14, Manizales', estado: 'ACTIVO',
    contactos: [{ id_contacto: 5, nombre: 'Rubiela Castaño', cargo: 'Gerente', telefono: '311 734 9020', email: 'rcastano@hortalizascaldas.example' }] },
  { id_proveedor: 5, nit: '901.233.870-4', razon_social: 'Bebidas Cumbre S.A.S.', telefono: '604 444 6120', email: 'clientes@bebidascumbre.example', direccion: 'Zona franca, Rionegro', estado: 'ACTIVO',
    contactos: [{ id_contacto: 6, nombre: 'Felipe Restrepo', cargo: 'Asesor de canal', telefono: '300 912 3346', email: 'frestrepo@bebidascumbre.example' }] },
  { id_proveedor: 6, nit: '900.774.019-2', razon_social: 'Químicos Aseo Total S.A.S.', telefono: '602 485 7731', email: 'ventas@aseototal.example', direccion: 'Acopi, Yumbo', estado: 'ACTIVO',
    contactos: [{ id_contacto: 7, nombre: 'Natalia Mejía', cargo: 'Ejecutiva comercial', telefono: '316 220 5418', email: 'nmejia@aseototal.example' }] },
  { id_proveedor: 7, nit: '901.050.336-8', razon_social: 'Aceites y Café del Eje S.A.S.', telefono: '606 886 2290', email: 'pedidos@cafedeleje.example', direccion: 'Avenida Kevin Ángel # 70-21, Manizales', estado: 'ACTIVO',
    contactos: [{ id_contacto: 8, nombre: 'Gustavo Arias', cargo: 'Vendedor', telefono: '313 645 1187', email: 'garias@cafedeleje.example' }] },
  { id_proveedor: 8, nit: '900.361.945-0', razon_social: 'Cuidado Natural S.A.S.', telefono: '601 742 3005', email: 'pedidos@cuidadonatural.example', direccion: 'Calle 13 # 68-40, Bogotá', estado: 'ACTIVO',
    contactos: [{ id_contacto: 9, nombre: 'Lina Vargas', cargo: 'Asesora', telefono: '318 504 6612', email: 'lvargas@cuidadonatural.example' }] },
  { id_proveedor: 9, nit: '890.302.118-5', razon_social: 'Empaques del Centro Ltda.', telefono: '606 870 1144', email: 'info@empaquescentro.example', direccion: 'Carrera 20 # 30-12, Manizales', estado: 'INACTIVO', contactos: [] },
]

const suministra = (skus: string[], margen = 0.72, dias = 2): ProductoSuministrado[] =>
  skus.map((sku) => {
    const p = productos.find((x) => x.sku === sku)!
    return { sku, precio_compra: Math.round(p.precio_venta * margen), dias_entrega: dias, estado: 'ACTIVO' }
  })

/** GET /api/proveedores/{id}/productos: la relación proveedor–producto vive en ms-proveedores. */
export const productosPorProveedor: Record<number, ProductoSuministrado[]> = {
  1: suministra(['ABA-0112', 'ABA-0118', 'ABA-0131'], 0.74, 3),
  2: suministra(['LAC-0001', 'LAC-0014', 'LAC-0102', 'LAC-0201'], 0.7, 1),
  3: suministra(['CAR-0010', 'CAR-0105'], 0.75, 1),
  4: suministra(['FRU-0031', 'FRU-0044', 'FRU-0052', 'FRU-0067'], 0.62, 1),
  5: suministra(['BEB-0044', 'BEB-0120', 'BEB-0207'], 0.68, 4),
  6: suministra(['ASE-0207', 'ASE-0450', 'ASE-0512'], 0.7, 5),
  7: suministra(['ABA-0204', 'ABA-0310', 'ABA-0322'], 0.73, 3),
  8: suministra(['CUI-0018', 'CUI-0103'], 0.66, 6),
  9: [],
}

export const productoPorSku = new Map(productos.map((p) => [p.sku, p]))
export const bodegaPorId = new Map(bodegas.map((b) => [b.id_bodega, b]))
export const usuarioPorId = new Map(usuarios.map((u) => [u.id, u]))
export const proveedorPorId = new Map(proveedores.map((p) => [p.id_proveedor, p]))
export const categoriaPorId = new Map(categorias.map((c) => [c.id_categoria, c]))

/** Categoría raíz de un producto (Lácteos para Yogures, etc.). */
export function categoriaRaiz(id_categoria: number): Categoria {
  let c = categoriaPorId.get(id_categoria)!
  while (c.id_categoria_padre !== null) c = categoriaPorId.get(c.id_categoria_padre)!
  return c
}
