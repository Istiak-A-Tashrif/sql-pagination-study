FROM node:22.23.0-bookworm-slim
WORKDIR /app
COPY app/backend/package*.json ./
RUN npm ci --omit=dev
COPY backend-study/extensions/src/ ./
COPY backend-study/sql/ ./sql/
CMD ["node","server.cjs"]
