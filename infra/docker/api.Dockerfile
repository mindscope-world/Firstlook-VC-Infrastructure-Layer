FROM node:22-slim AS build
RUN corepack enable
WORKDIR /app
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY services/api/package.json services/api/
RUN pnpm install --frozen-lockfile --filter @firstlook/api...
COPY services/api services/api
RUN pnpm --filter @firstlook/api build && pnpm --filter @firstlook/api deploy --prod --legacy /out

FROM node:22-slim
# The runtime only needs node. npm and corepack ship with the base image and
# carry their own CVEs, so remove them.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack
WORKDIR /app
COPY --from=build /out /app
ENV NODE_ENV=production API_PORT=8080
USER node
EXPOSE 8080
CMD ["node", "dist/server.js"]
