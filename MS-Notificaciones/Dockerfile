FROM node:24-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=5006

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

COPY . .
RUN mkdir -p /app/.data && chown -R node:node /app

USER node

EXPOSE 5006

CMD ["node", "src/server.js"]
