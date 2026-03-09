FROM node:20-bookworm-slim AS builder
WORKDIR /workspace
ENV ORION_CORE_DB_PATH=/tmp/orion-core-build.sqlite

COPY app/package*.json ./app/
RUN cd app && npm ci

COPY app ./app
COPY db ./db

RUN cd app && npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /workspace
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV HOST=0.0.0.0
ENV PORT=8080
ENV NODE_OPTIONS=--max-old-space-size=192
ENV ORION_CORE_DB_PATH=/data/orion-core.sqlite
ENV ORION_CORE_TIMEZONE=America/New_York

RUN mkdir -p /data

COPY --from=builder /workspace/app/.next/standalone ./
COPY --from=builder /workspace/app/.next/static ./app/.next/static

EXPOSE 8080
CMD ["node", "app/server.js"]
