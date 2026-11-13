import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router'
import { ConPermiso, RequiereSesion } from './auth/Sesion'
import type { Operacion } from './auth/permisos'
import { Shell } from './componentes/Shell'
import { Buscar, Perfil, Usuarios } from './paginas/Admin'
import { Bodegas, Categorias, Productos } from './paginas/Catalogo'
import { Dashboard } from './paginas/Dashboard'
import { Devoluciones, NuevaDevolucionCliente } from './paginas/Devoluciones'
import { ErrorDePantalla, NoEncontrado } from './paginas/Errores'
import { Ingreso, Recuperar } from './paginas/Ingreso'
import { Kardex } from './paginas/Kardex'
import { Movimientos, NuevoMovimiento } from './paginas/Movimientos'
import { Notificaciones } from './paginas/Notificaciones'
import { NuevaOrden, OrdenDetalle, Ordenes } from './paginas/Ordenes'
import { ProveedorDetalle, Proveedores } from './paginas/Proveedores'
import { Reportes } from './paginas/Reportes'
import { Stock, StockDetalle } from './paginas/Stock'
import { NuevoTraslado, Traslados } from './paginas/Traslados'

const con = (op: Operacion, elemento: ReactNode) => <ConPermiso op={op}>{elemento}</ConPermiso>

export const router = createBrowserRouter([
  { path: '/ingresar', element: <Ingreso />, errorElement: <ErrorDePantalla /> },
  { path: '/recuperar', element: <Recuperar />, errorElement: <ErrorDePantalla /> },
  {
    element: <RequiereSesion />,
    errorElement: <ErrorDePantalla />,
    children: [
      {
        element: <Shell />,
        errorElement: <ErrorDePantalla />,
        children: [
          { index: true, element: con('reportes', <Dashboard />) },
          { path: 'stock', element: con('stock', <Stock />) },
          { path: 'stock/:sku', element: con('stock', <StockDetalle />) },
          { path: 'movimientos', element: con('movimientos', <Movimientos />) },
          { path: 'movimientos/nuevo', element: con('movimientos', <NuevoMovimiento />) },
          { path: 'kardex', element: con('movimientos', <Kardex />) },
          { path: 'traslados', element: con('movimientos', <Traslados />) },
          { path: 'traslados/nuevo', element: con('movimientos', <NuevoTraslado />) },
          { path: 'devoluciones', element: con('reportes', <Devoluciones />) },
          { path: 'devoluciones/cliente/nueva', element: con('devolucionCliente', <NuevaDevolucionCliente />) },
          { path: 'ordenes-compra', element: con('ordenes', <Ordenes />) },
          { path: 'ordenes-compra/nueva', element: con('ordenes', <NuevaOrden />) },
          { path: 'ordenes-compra/:id', element: con('ordenes', <OrdenDetalle />) },
          { path: 'proveedores', element: con('proveedores', <Proveedores />) },
          { path: 'proveedores/:id', element: con('proveedores', <ProveedorDetalle />) },
          { path: 'productos', element: con('catalogo', <Productos />) },
          { path: 'categorias', element: con('catalogo', <Categorias />) },
          { path: 'bodegas', element: con('bodegas', <Bodegas />) },
          { path: 'notificaciones', element: <Notificaciones /> },
          { path: 'reportes', element: con('reportes', <Reportes />) },
          { path: 'usuarios', element: con('usuarios', <Usuarios />) },
          { path: 'perfil', element: <Perfil /> },
          { path: 'buscar', element: <Buscar /> },
          { path: '*', element: <NoEncontrado /> },
        ],
      },
    ],
  },
])
