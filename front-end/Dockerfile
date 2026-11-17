# Etapa 1: compila la interfaz con Vite
FROM node:24-alpine AS compilacion
WORKDIR /app

# Dependencias primero, para aprovechar la caché de capas
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# Etapa 2: Nginx sirve los archivos estáticos y reenvía /api al API Gateway.
# El navegador habla con un solo origen (este contenedor), así que no hace falta CORS.
FROM nginx:1.27-alpine

# URL del gateway dentro de la red de Docker: esquema, host y puerto, sin ruta.
# Por defecto, el alias api-gateway de la red redapi (puerto 80 de Apache).
ENV GATEWAY_URL=http://api-gateway

# La imagen oficial de Nginx reemplaza ${GATEWAY_URL} en las plantillas al arrancar
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=compilacion /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/salud || exit 1
