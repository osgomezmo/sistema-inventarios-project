// Carga el rack 3D (three.js) en un archivo aparte: el resto de la pantalla aparece
// primero y el rack llega cuando su código termina de descargar.
import { lazy, Suspense, type ComponentProps } from 'react'

const Rack = lazy(() => import('./RackBodega').then((m) => ({ default: m.RackBodega })))

export function RackBodega(props: ComponentProps<typeof Rack>) {
  return (
    <Suspense fallback={<div className="rack-3d rack-cargando" style={{ height: props.alto ?? 460 }} aria-busy="true">Cargando el rack de la bodega…</div>}>
      <Rack {...props} />
    </Suspense>
  )
}
