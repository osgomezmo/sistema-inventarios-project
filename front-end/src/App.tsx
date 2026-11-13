import { RouterProvider } from 'react-router'
import { ProveedorSesion } from './auth/Sesion'
import { ProveedorBodega } from './contexto/Bodega'
import { router } from './rutas'

// Los avisos (ProveedorAvisos) viven dentro del router, en Shell, porque muestran enlaces.
export default function App() {
  return (
    <ProveedorSesion>
      <ProveedorBodega>
        <RouterProvider router={router} />
      </ProveedorBodega>
    </ProveedorSesion>
  )
}
