// Package market defines a pluggable market-data provider interface and adapters
// for Polygon, Finnhub, Alpha Vantage, plus a synthetic mock provider.
package market

import (
	"context"
	"log/slog"
	"net/http"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/config"
	"github.com/quanta/trading-dashboard/backend/internal/models"
)

// Provider is the common interface every market-data adapter implements.
type Provider interface {
	// Name returns the adapter's identifier (e.g. "polygon").
	Name() string
	// Quote returns a normalized quote for one canonical symbol.
	Quote(ctx context.Context, symbol string) (models.Quote, error)
}

// Instrument couples a canonical platform symbol with display metadata and the
// vendor-specific symbol each provider expects.
type Instrument struct {
	Symbol     string
	Name       string
	AssetClass models.AssetClass
	// Per-provider symbol overrides; falls back to Symbol when absent.
	Polygon      string
	Finnhub      string
	AlphaVantage string
}

// DashboardInstruments is the canonical Stage-1 instrument set shown on the
// main dashboard. Futures are mapped to liquid ETF/continuous proxies where a
// provider lacks a futures feed, so the MVP works on free tiers.
var DashboardInstruments = []Instrument{
	{Symbol: "SPY", Name: "S&P 500 ETF", AssetClass: models.AssetETF, Polygon: "SPY", Finnhub: "SPY", AlphaVantage: "SPY"},
	{Symbol: "QQQ", Name: "Nasdaq 100 ETF", AssetClass: models.AssetETF, Polygon: "QQQ", Finnhub: "QQQ", AlphaVantage: "QQQ"},
	{Symbol: "IWM", Name: "Russell 2000 ETF", AssetClass: models.AssetETF, Polygon: "IWM", Finnhub: "IWM", AlphaVantage: "IWM"},
	{Symbol: "DIA", Name: "Dow Jones ETF", AssetClass: models.AssetETF, Polygon: "DIA", Finnhub: "DIA", AlphaVantage: "DIA"},
	{Symbol: "VIX", Name: "Volatility Index", AssetClass: models.AssetIndex, Polygon: "I:VIX", Finnhub: "^VIX", AlphaVantage: "VIXY"},
	{Symbol: "ES", Name: "E-mini S&P 500", AssetClass: models.AssetFuture, Polygon: "SPY", Finnhub: "SPY", AlphaVantage: "SPY"},
	{Symbol: "NQ", Name: "E-mini Nasdaq 100", AssetClass: models.AssetFuture, Polygon: "QQQ", Finnhub: "QQQ", AlphaVantage: "QQQ"},
	{Symbol: "RTY", Name: "E-mini Russell 2000", AssetClass: models.AssetFuture, Polygon: "IWM", Finnhub: "IWM", AlphaVantage: "IWM"},
	{Symbol: "CL", Name: "Crude Oil WTI", AssetClass: models.AssetFuture, Polygon: "USO", Finnhub: "USO", AlphaVantage: "USO"},
	{Symbol: "GC", Name: "Gold", AssetClass: models.AssetFuture, Polygon: "GLD", Finnhub: "GLD", AlphaVantage: "GLD"},
	{Symbol: "US10Y", Name: "US 10Y Yield", AssetClass: models.AssetRate, Polygon: "I:TNX", Finnhub: "^TNX", AlphaVantage: "IEF"},
	{Symbol: "DXY", Name: "US Dollar Index", AssetClass: models.AssetIndex, Polygon: "I:DXY", Finnhub: "^DXY", AlphaVantage: "UUP"},
}

// instrumentBySymbol indexes the dashboard set for quick lookup.
var instrumentBySymbol = func() map[string]Instrument {
	m := make(map[string]Instrument, len(DashboardInstruments))
	for _, in := range DashboardInstruments {
		m[in.Symbol] = in
	}
	return m
}()

// Lookup returns the instrument metadata for a canonical symbol.
func Lookup(symbol string) (Instrument, bool) {
	in, ok := instrumentBySymbol[symbol]
	return in, ok
}

// httpClient is shared by HTTP-based adapters.
var httpClient = &http.Client{Timeout: 10 * time.Second}

// Select chooses a provider based on explicit config, else the first configured
// API key, else the synthetic mock provider so the stack always boots.
func Select(cfg *config.Config, log *slog.Logger) Provider {
	switch cfg.MarketProvider {
	case "polygon":
		return NewPolygon(cfg.PolygonKey)
	case "finnhub":
		return NewFinnhub(cfg.FinnhubKey)
	case "alphavantage":
		return NewAlphaVantage(cfg.AlphaVantageKey)
	case "mock":
		return NewMock()
	}
	// Auto-detect by first configured key.
	switch {
	case cfg.PolygonKey != "":
		log.Info("market provider auto-selected", "provider", "polygon")
		return NewPolygon(cfg.PolygonKey)
	case cfg.FinnhubKey != "":
		log.Info("market provider auto-selected", "provider", "finnhub")
		return NewFinnhub(cfg.FinnhubKey)
	case cfg.AlphaVantageKey != "":
		log.Info("market provider auto-selected", "provider", "alphavantage")
		return NewAlphaVantage(cfg.AlphaVantageKey)
	default:
		log.Warn("no market data API key set — using synthetic mock provider")
		return NewMock()
	}
}
