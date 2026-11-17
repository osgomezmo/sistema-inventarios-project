FROM node:24-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3001

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

COPY . .
RUN chmod +x entrypoint.sh

USER node

EXPOSE 3001

ENTRYPOINT ["./entrypoint.sh"]
CMD ["node", "src/server.js"]
