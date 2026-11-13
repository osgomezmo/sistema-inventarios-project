import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import {
  ArrowDownUp, ArrowRightLeft, Bell, Boxes, ChartColumn, ClipboardList, Factory, FolderTree, KeyRound,
  LayoutDashboard, LogOut, Menu, Package, ScrollText, Search, Undo2, Users, Warehouse, type LucideIcon,
} from 'lucide-react'
import { useSesion, useUsuario } from '../auth/Sesion'
import { nombreRol, puedeVer, type Operacion } from '../auth/permisos'
import { useBodega } from '../contexto/Bodega'
import { notificacionesApi, reportesApi } from '../api/cliente'
import { ProveedorAvisos } from '../contexto/Avisos'
import { Marca } from './Marca'
import { useEsMovil } from '../lib/useEsMovil'

interface Enlace { a: string; texto: string; icono: LucideIcon; op: Operacion | Operacion[]; contador?: 'stockBajo' }

const grupos: Array<{ titulo: string; enlaces: Enlace[] }> = [
  { titulo: 'Operación', enlaces: [
    { a: '/', texto: 'Dashboard', icono: LayoutDashboard, op: 'reportes' },
    { a: '/stock', texto: 'Stock', icono: Boxes, op: 'stock', contador: 'stockBajo' },
    { a: '/movimientos', texto: 'Movimientos', icono: ArrowDownUp, op: 'movimientos' },
    { a: '/kardex', texto: 'Kardex', icono: ScrollText, op: 'movimientos' },
    { a: '/traslados', texto: 'Traslados', icono: ArrowRightLeft, op: 'movimientos' },
    { a: '/devoluciones', texto: 'Devoluciones', icono: Undo2, op: ['devolucionCliente', 'devolucionProveedor'] },
  ] },
  { titulo: 'Abastecimiento', enlaces: [
    { a: '/ordenes-compra', texto: 'Órdenes de compra', icono: ClipboardList, op: 'ordenes' },
    { a: '/proveedores', texto: 'Proveedores', icono: Factory, op: 'proveedores' },
  ] },
  { titulo: 'Catálogo', enlaces: [
    { a: '/productos', texto: 'Productos', icono: Package, op: 'catalogo' },
    { a: '/categorias', texto: 'Categorías', icono: FolderTree, op: 'catalogo' },
    { a: '/bodegas', texto: 'Bodegas', icono: Warehouse, op: 'bodegas' },
  ] },
  { titulo: 'Análisis', enlaces: [
    { a: '/reportes', texto: 'Reportes', icono: ChartColumn, op: 'reportes' },
  ] },
  { titulo: 'Administración', enlaces: [
    { a: '/usuarios', texto: 'Usuarios y roles', icono: Users, op: 'usuarios' },
  ] },
]

const iniciales = (nombre: string) => nombre.split(' ').slice(0, 2).map((p) => p[0]).join('')

export function Shell() {
  const usuario = useUsuario()
  const { cerrar } = useSesion()
  const { idBodega, cambiar, activas } = useBodega()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [rielAbierto, setRielAbierto] = useState(false)
  const [sinLeer, setSinLeer] = useState(0)
  const [stockBajo, setStockBajo] = useState(0)
  const [avisoBusqueda, setAvisoBusqueda] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const esMovil = useEsMovil()

  useEffect(() => {
    let vigente = true
    notificacionesApi.listar(usuario.rol, { leida: false }).then((r) => vigente && setSinLeer(r.meta.total))
    reportesApi.stockBajo(idBodega).then((r) => vigente && setStockBajo(r.length))
    setRielAbierto(false)
    return () => { vigente = false }
  }, [usuario.rol, idBodega, ubicacion.pathname])

  useEffect(() => {
    if (!menuAbierto) return
    const fuera = (e: MouseEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenuAbierto(false) }
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuAbierto(false) }
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', tecla)
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', tecla) }
  }, [menuAbierto])

  function buscar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const q = String(new FormData(e.currentTarget).get('q') ?? '').trim()
    if (q.length < 2) { setAvisoBusqueda(true); return }
    setAvisoBusqueda(false)
    navegar(`/buscar?q=${encodeURIComponent(q)}`)
  }

  const visible = (op: Enlace['op']) => (Array.isArray(op) ? op : [op]).some((o) => puedeVer(usuario.rol, o))

  return (
    <ProveedorAvisos>
    <div className="app">
      <header className="barra">
        <button type="button" className="icono-btn abrir-riel" aria-label="Abrir menú" aria-expanded={rielAbierto} onClick={() => setRielAbierto((v) => !v)}>
          <Menu size={24} aria-hidden />
        </button>
        <Link to="/" className="marca" aria-label="Estiba, ir al dashboard"><Marca /></Link>

        <form className="buscador" role="search" onSubmit={buscar}>
          <Search size={20} aria-hidden />
          <label htmlFor="buscar-global" className="solo-lector">Buscar</label>
          <input id="buscar-global" name="q" type="search" placeholder="Buscar SKU, producto o documento (OC-2026-0015)" autoComplete="off" maxLength={60}
            aria-invalid={avisoBusqueda || undefined} aria-describedby={avisoBusqueda ? 'buscar-aviso' : undefined} onInput={() => avisoBusqueda && setAvisoBusqueda(false)} />
          {avisoBusqueda && <span id="buscar-aviso" className="buscador-aviso" role="alert">Escribe al menos 2 caracteres para buscar.</span>}
        </form>

        <div className="barra-bodega">
          <label htmlFor="bodega-activa">Bodega</label>
          <select id="bodega-activa" value={idBodega} onChange={(e) => cambiar(Number(e.target.value))}>
            {activas.map((b) => <option key={b.id_bodega} value={b.id_bodega}>{esMovil ? b.codigo : `${b.codigo} · ${b.nombre}`}</option>)}
          </select>
        </div>

        <div className="barra-derecha">
          <span className="muestra" title="Plantilla de interfaz: todos los datos son de ejemplo">Datos de ejemplo</span>
          <Link to="/notificaciones" className="icono-btn" aria-label={`Notificaciones, ${sinLeer} sin leer`}>
            <Bell size={24} aria-hidden />
            {sinLeer > 0 && <span className="contador" aria-hidden>{sinLeer}</span>}
          </Link>
          <div ref={menuRef} style={{ position: 'relative' }}>
            <button type="button" className="usuario-btn" aria-haspopup="menu" aria-expanded={menuAbierto} onClick={() => setMenuAbierto((v) => !v)}>
              <span className="iniciales" aria-hidden>{iniciales(usuario.nombre)}</span>
              <span className="usuario-texto"><strong>{usuario.nombre}</strong><span>{nombreRol[usuario.rol]}</span></span>
            </button>
            {menuAbierto && (
              <div className="menu-flotante" role="menu">
                <Link role="menuitem" to="/perfil" onClick={() => setMenuAbierto(false)}><KeyRound size={18} aria-hidden />Cambiar contraseña</Link>
                <hr />
                <button role="menuitem" type="button" onClick={async () => { await cerrar(); navegar('/ingresar') }}><LogOut size={18} aria-hidden />Cerrar sesión</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <nav className="riel" aria-label="Módulos" data-abierto={rielAbierto}>
        {grupos.map((g) => {
          const enlaces = g.enlaces.filter((e) => visible(e.op))
          if (!enlaces.length) return null
          return (
            <div className="riel-grupo" key={g.titulo}>
              <h2>{g.titulo}</h2>
              <ul>
                {enlaces.map((e) => (
                  <li key={e.a}>
                    <NavLink to={e.a} end={e.a === '/'} title={e.texto}>
                      <e.icono size={20} aria-hidden />
                      <span className="rotulo-riel">{e.texto}</span>
                      {e.contador === 'stockBajo' && stockBajo > 0 && (
                        <span className="contador-riel" aria-label={`${stockBajo} productos en stock bajo`}>{stockBajo}</span>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
        <div className="riel-pie">Plantilla de interfaz · entrega 3</div>
      </nav>

      <main className="contenido" id="contenido">
        <Outlet />
      </main>
    </div>
    </ProveedorAvisos>
  )
}
