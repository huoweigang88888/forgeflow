# =============================================================================
# ForgeFlow AI - Web Frontend Dockerfile
# =============================================================================
# Multi-stage build for Next.js application.
#
# Build:
#   docker build -t forgeflow-web -f apps/web/Dockerfile .
# Run:
#   docker run -p 3000:3000 forgeflow-web

# ---- Stage 1: Build ----
FROM node:20-alpine AS builder

WORKDIR /app

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@9 --activate

# Copy workspace config
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./
COPY apps/web/package.json apps/web/

# Install dependencies
RUN pnpm install --filter @forgeflow/web --frozen-lockfile

# Copy source
COPY apps/web/ apps/web/

# Build
WORKDIR /app/apps/web
RUN pnpm build

# ---- Stage 2: Runtime ----
FROM node:20-alpine AS runtime

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S forgeflow && adduser -S forgeflow -u 1001 -G forgeflow

# Copy only what's needed
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./.next/static
COPY --from=builder /app/apps/web/public ./public

# Set environment
ENV NODE_ENV=production
ENV PORT=3000

USER forgeflow

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
