import { RouterProvider } from 'react-router'
import { ProveedorSesion } from './auth/Sesion'
import { ProveedorAvisos } from './contexto/Avisos'
import { ProveedorBodega } from './contexto/Bodega'
import { router } from './rutas'

export default function App() {
  return (
    <ProveedorSesion>
      <ProveedorBodega>
        <ProveedorAvisos>
          <RouterProvider router={router} />
        </ProveedorAvisos>
      </ProveedorBodega>
    </ProveedorSesion>
  )
}
