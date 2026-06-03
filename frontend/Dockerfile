# ─── Dependencies ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
# No lockfile committed; install resolves the ranges in package.json.
RUN npm install

# ─── Build ──────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
# NEXT_PUBLIC_* are baked into the client bundle at build time. Default empty so
# the image is host-agnostic and uses same-origin URLs (works behind any ingress).
# Override only for setups where the frontend and backend are on different origins
# (e.g. local docker-compose passes the localhost:8080 values).
ARG NEXT_PUBLIC_API_BASE_URL=""
ARG NEXT_PUBLIC_WS_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_WS_BASE_URL=$NEXT_PUBLIC_WS_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ─── Runtime ──────────────────────────────────────────────────────────────────
FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup -g 1001 nodejs && adduser -D -u 1001 -G nodejs nextjs

# Standalone output bundles a minimal server + only required deps.
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
