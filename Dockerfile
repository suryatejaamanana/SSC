# Single-service image: Next.js (public, $PORT) + FastAPI (internal, 127.0.0.1:8000)
FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
# Empty => frontend calls the same origin; /api/* is rewritten to FastAPI.
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

FROM python:3.12-slim
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend-build /app/.next/standalone frontend/
COPY --from=frontend-build /app/.next/static frontend/.next/static
COPY --from=frontend-build /app/public frontend/public
COPY start.sh start.sh
RUN chmod +x start.sh
ENV NODE_ENV=production
CMD ["./start.sh"]
