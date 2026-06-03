// Package ingest runs background workers that poll the active market-data
// provider for the dashboard instruments, persist snapshots, cache them in
// Redis, and fan updates out to WebSocket clients (locally and via Redis pub/sub).
package ingest

import (
	"context"
	"encoding/json"
	"log/slog"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/cache"
	"github.com/quanta/trading-dashboard/backend/internal/market"
	"github.com/quanta/trading-dashboard/backend/internal/models"
	"github.com/quanta/trading-dashboard/backend/internal/store"
	"github.com/quanta/trading-dashboard/backend/internal/ws"
)

// Ingestor coordinates polling and fan-out.
type Ingestor struct {
	provider market.Provider
	store    *store.Store
	cache    *cache.Cache
	hub      *ws.Hub
	interval time.Duration
	log      *slog.Logger
}

// New builds an Ingestor.
func New(p market.Provider, s *store.Store, c *cache.Cache, hub *ws.Hub, interval time.Duration, log *slog.Logger) *Ingestor {
	return &Ingestor{provider: p, store: s, cache: c, hub: hub, interval: interval, log: log}
}

// Run starts the poll loop and the Redis subscriber. It blocks until ctx is done.
func (i *Ingestor) Run(ctx context.Context) {
	go i.subscribeFanout(ctx)

	// Prime once immediately, then on the configured interval.
	i.pollOnce(ctx)
	ticker := time.NewTicker(i.interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			i.pollOnce(ctx)
		}
	}
}

func (i *Ingestor) pollOnce(ctx context.Context) {
	for _, in := range market.DashboardInstruments {
		select {
		case <-ctx.Done():
			return
		default:
		}
		q, err := i.provider.Quote(ctx, in.Symbol)
		if err != nil {
			i.log.Debug("quote fetch failed", "symbol", in.Symbol, "provider", i.provider.Name(), "err", err)
			continue
		}
		i.handleQuote(ctx, q)
	}
}

// handleQuote persists, caches, and publishes a single quote.
func (i *Ingestor) handleQuote(ctx context.Context, q models.Quote) {
	if err := i.store.UpsertQuote(ctx, q); err != nil {
		i.log.Debug("upsert quote failed", "symbol", q.Symbol, "err", err)
	}
	_ = i.cache.SetJSON(ctx, "quote:"+q.Symbol, q, 30*time.Second)

	// Publish to Redis so other replicas can fan out to their own WS clients.
	if err := i.cache.Publish(ctx, cache.QuotesChannel, q); err != nil {
		i.log.Debug("publish quote failed", "symbol", q.Symbol, "err", err)
	}
	// Also broadcast locally (covers the single-replica case immediately).
	i.hub.Broadcast("quote:"+q.Symbol, q)
}

// subscribeFanout relays quotes published by any replica to this pod's clients.
func (i *Ingestor) subscribeFanout(ctx context.Context) {
	sub := i.cache.Subscribe(ctx, cache.QuotesChannel)
	defer sub.Close()
	ch := sub.Channel()
	for {
		select {
		case <-ctx.Done():
			return
		case msg, ok := <-ch:
			if !ok {
				return
			}
			var q models.Quote
			if err := json.Unmarshal([]byte(msg.Payload), &q); err != nil {
				continue
			}
			i.hub.Broadcast("quote:"+q.Symbol, q)
		}
	}
}
