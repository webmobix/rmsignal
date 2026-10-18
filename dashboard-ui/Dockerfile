# Production image for the TanStack Start / Nitro app (node-server preset).
# Build:  docker build -t dashboard-ui .
# Run:    docker run --rm -p 8080:8080 -e RM_API_URL=... dashboard-ui

# ---- deps ----------------------------------------------------------------
FROM node:24-bookworm-slim AS deps
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN npm install -g pnpm@12.14.0
WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# ---- build ---------------------------------------------------------------
FROM deps AS build
COPY . .
RUN pnpm build

# ---- runtime -------------------------------------------------------------
FROM node:24-bookworm-slim AS runner
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8080
# RM_API_URL is supplied at runtime, e.g.:
#   docker run ... -e RM_API_URL=https://rm-api-xxxx.run.app dashboard-ui
#   gcloud run deploy ... --set-env-vars RM_API_URL=https://rm-api-xxxx.run.app
WORKDIR /app

# Nitro's node-server output is self-contained (deps are traced/bundled).
COPY --from=build --chown=node:node /app/.output ./.output

USER node
EXPOSE 8080
CMD ["node", ".output/server/index.mjs"]
