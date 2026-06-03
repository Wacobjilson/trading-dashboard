# ─── Build stage ──────────────────────────────────────────────────────────────
FROM golang:1.22-alpine AS build
WORKDIR /src

RUN apk add --no-cache git ca-certificates

# Resolve dependencies. No go.sum is committed, so `go mod tidy` generates it
# (and downloads modules) at build time.
COPY go.mod ./
RUN go mod download || true

COPY . .
RUN go mod tidy
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/api ./cmd/api

# ─── Runtime stage ──────────────────────────────────────────────────────────────
FROM alpine:3.20
RUN apk add --no-cache ca-certificates && adduser -D -u 10001 app
USER app
WORKDIR /app
COPY --from=build /out/api /app/api

EXPOSE 8080
ENV API_PORT=8080
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["/app/api"]
