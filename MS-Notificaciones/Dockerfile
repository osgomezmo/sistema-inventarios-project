FROM node:24-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=5006

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

COPY --chown=node:node . .
RUN mkdir -p /app/.data && chown -R node:node /app/.data

USER node

EXPOSE 5006

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:5006/health || exit 1

CMD ["node", "src/server.js"]
