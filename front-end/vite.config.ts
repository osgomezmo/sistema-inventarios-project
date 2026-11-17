import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// En desarrollo, /api se reenvía al gateway publicado por su docker-compose
// (127.0.0.1:8000). Así el navegador habla con un solo origen y no hace falta CORS,
// igual que en el contenedor, donde Nginx hace el mismo reenvío.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const gateway = env.GATEWAY_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target: gateway, changeOrigin: true },
      },
    },
    preview: {
      proxy: {
        '/api': { target: gateway, changeOrigin: true },
      },
    },
  }
})
