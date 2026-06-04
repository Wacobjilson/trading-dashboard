// Command api is the Quanta backend: REST API + WebSocket gateway + ingestion.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/auth"
	"github.com/quanta/trading-dashboard/backend/internal/cache"
	"github.com/quanta/trading-dashboard/backend/internal/config"
	"github.com/quanta/trading-dashboard/backend/internal/db"
	"github.com/quanta/trading-dashboard/backend/internal/httpapi"
	"github.com/quanta/trading-dashboard/backend/internal/ingest"
	"github.com/quanta/trading-dashboard/backend/internal/market"
	"github.com/quanta/trading-dashboard/backend/internal/store"
	"github.com/quanta/trading-dashboard/backend/internal/ws"
)

func main() {
	cfg := config.Load()
	log := newLogger(cfg.LogLevel)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// Postgres.
	database, err := db.Connect(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Error("database connect", "err", err)
		os.Exit(1)
	}
	defer database.Close()
	if err := database.Migrate(ctx); err != nil {
		log.Error("migrate", "err", err)
		os.Exit(1)
	}
	log.Info("database ready, migrations applied")

	// Redis.
	rc, err := cache.Connect(ctx, cfg.RedisURL)
	if err != nil {
		log.Error("redis connect", "err", err)
		os.Exit(1)
	}
	defer rc.Close()
	log.Info("redis ready")

	// Wiring.
	st := store.New(database.Pool)
	am := auth.NewManager(cfg.JWTSecret, cfg.DisableAuth)
	if cfg.DisableAuth {
		log.Warn("AUTH DISABLED — running in single-user mode (no login required)")
	}
	provider := market.Select(cfg, log)
	log.Info("market provider selected", "provider", provider.Name())

	hub := ws.NewHub(log, originChecker(cfg.CORSOrigins))
	ig := ingest.New(provider, st, rc, hub, cfg.QuotePollInterval, log)
	go ig.Run(ctx)

	srv := httpapi.NewServer(st, rc, am, provider, hub, log)
	handler := srv.Router(cfg.CORSOrigins)

	httpServer := &http.Server{
		Addr:              ":" + cfg.APIPort,
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
	}

	go func() {
		log.Info("http server listening", "port", cfg.APIPort)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("http server", "err", err)
			stop()
		}
	}()

	<-ctx.Done()
	log.Info("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(shutdownCtx)
}

func newLogger(level string) *slog.Logger {
	var lvl slog.Level
	switch strings.ToLower(level) {
	case "debug":
		lvl = slog.LevelDebug
	case "warn":
		lvl = slog.LevelWarn
	case "error":
		lvl = slog.LevelError
	default:
		lvl = slog.LevelInfo
	}
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: lvl}))
}

// originChecker allows WebSocket upgrades only from configured origins (or any
// when none configured, useful for local/dev).
func originChecker(allowed []string) func(r *http.Request) bool {
	set := make(map[string]struct{}, len(allowed))
	for _, o := range allowed {
		set[o] = struct{}{}
	}
	return func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		if origin == "" || len(set) == 0 {
			return true
		}
		_, ok := set[origin]
		return ok
	}
}
