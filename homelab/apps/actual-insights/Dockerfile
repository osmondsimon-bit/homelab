# Reproducible Node runtime for the Actual Budget monthly category-insights companion.
ARG NODE_IMAGE=node:24.18.0-bookworm-slim
FROM ${NODE_IMAGE} AS build

WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3 \
    && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
RUN npm_config_build_from_source=true npm ci --omit=dev \
    && npm cache clean --force

FROM ${NODE_IMAGE}

ENV NODE_ENV=production \
    HOME=/tmp
WORKDIR /app

COPY --from=build --chown=node:node /build/node_modules ./node_modules
COPY --chown=node:node package.json package-lock.json ./
COPY --chown=node:node src ./src
COPY --chown=node:node public ./public

USER node
EXPOSE 5007
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:5007/healthz').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "src/main.mjs"]
