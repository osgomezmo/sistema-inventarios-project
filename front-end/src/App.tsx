import { RouterProvider } from 'react-router'
import { ProveedorSesion } from './auth/Sesion'
import { router } from './rutas'

// La bodega activa y los datos maestros se cargan dentro de las rutas protegidas
// (RequiereSesion), porque necesitan el token. Los avisos viven en Shell porque muestran enlaces.
export default function App() {
  return (
    <ProveedorSesion>
      <RouterProvider router={router} />
    </ProveedorSesion>
  )
}
