FROM node:22-slim AS build
RUN corepack enable
WORKDIR /app
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile --filter @firstlook/web...
COPY apps/web apps/web
ENV NEXT_TELEMETRY_DISABLED=1
# Rewrites are resolved at build time; point them at in-cluster service names.
ARG API_URL=http://api:8080
ARG INGEST_URL=http://ingest:8080
RUN API_URL=$API_URL INGEST_URL=$INGEST_URL pnpm --filter @firstlook/web build

FROM node:22-slim
WORKDIR /app
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
USER node
EXPOSE 8080
CMD ["node", "apps/web/server.js"]
