import { useState } from 'react'
import { Link } from 'react-router'
import { BellOff, CheckCheck, PackageX, TriangleAlert } from 'lucide-react'
import { notificacionesApi } from '../api/cliente'
import { bodegaPorId } from '../api/mock/maestros'
import { useUsuario } from '../auth/Sesion'
import { nombreRol } from '../auth/permisos'
import { Cargando, Encabezado, ErrorCaja, Vacio } from '../componentes/ui'
import { fechaHora } from '../lib/formato'
import { useConsulta } from '../lib/useConsulta'

export function Notificaciones() {
  const usuario = useUsuario()
  const [soloSinLeer, setSoloSinLeer] = useState(false)
  const c = useConsulta(() => notificacionesApi.listar(usuario.rol, soloSinLeer ? { leida: false } : {}), [usuario.rol, soloSinLeer])
  const sinLeer = c.datos?.data.filter((n) => !n.leida) ?? []

  async function marcar(id: string) { await notificacionesApi.marcarLeida(id); c.recargar() }
  async function marcarTodas() { await Promise.all(sinLeer.map((n) => notificacionesApi.marcarLeida(n.id))); c.recargar() }

  return (
    <>
      <Encabezado
        titulo="Notificaciones"
        descripcion={`Alertas de stock bajo enviadas al rol ${nombreRol[usuario.rol === 'ADMINISTRADOR' ? 'JEFE_BODEGA' : usuario.rol].toLowerCase()}. Nacen del evento StockBajoUmbral en el momento del movimiento.`}
        acciones={sinLeer.length > 0 && <button type="button" className="btn" onClick={marcarTodas}><CheckCheck size={18} aria-hidden />Marcar todas como leídas</button>}
      />
      <div className="chips" role="group" aria-label="Filtro">
        <button type="button" className="chip" aria-pressed={!soloSinLeer} onClick={() => setSoloSinLeer(false)}>Todas</button>
        <button type="button" className="chip" aria-pressed={soloSinLeer} onClick={() => setSoloSinLeer(true)}>Sin leer</button>
      </div>
      {c.error && <ErrorCaja error={c.error} reintentar={c.recargar} />}
      <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
        {!c.datos && !c.error && <Cargando />}
        {c.datos && (c.datos.data.length === 0 ? (
          <Vacio titulo={soloSinLeer ? 'Estás al día' : 'Sin notificaciones'} icono={<BellOff size={40} aria-hidden />}>
            {usuario.rol === 'GERENTE' ? 'Las alertas de stock bajo llegan a Compras y a los jefes de bodega; tú las ves en el dashboard.' : 'Cuando un movimiento deje un producto en su mínimo, aparecerá aquí.'}
          </Vacio>
        ) : c.datos.data.map((n) => {
          const agotado = n.titulo.includes('agotado')
          return (
            <article key={n.id} className="notificacion" data-leida={n.leida}>
              <span className={`icono-aviso${agotado ? ' agotado' : ''}`} aria-hidden>{agotado ? <PackageX size={20} /> : <TriangleAlert size={18} />}</span>
              <div>
                <strong>{n.titulo}</strong>
                <p>{n.mensaje}</p>
                <p style={{ display: 'flex', gap: 16, marginTop: 6 }}>
                  {n.sku && <Link to={`/kardex?sku=${n.sku}&id_bodega=${n.id_bodega}`}>Ver kardex</Link>}
                  {n.sku && usuario.rol !== 'JEFE_BODEGA' && <Link to="/ordenes-compra/nueva">Crear orden de compra</Link>}
                </p>
              </div>
              <div style={{ display: 'grid', justifyItems: 'end', gap: 8 }}>
                <time dateTime={n.fecha}>{fechaHora(n.fecha)}</time>
                {n.id_bodega && <span className="tag">{bodegaPorId.get(n.id_bodega)!.codigo}</span>}
                {!n.leida && <button type="button" className="btn btn-sm" onClick={() => marcar(n.id)}>Marcar como leída</button>}
              </div>
            </article>
          )
        }))}
      </div>
    </>
  )
}
