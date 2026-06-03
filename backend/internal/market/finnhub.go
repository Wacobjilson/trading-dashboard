package market

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/models"
)

// Finnhub adapter — https://finnhub.io/docs/api/quote
type Finnhub struct {
	key string
}

// NewFinnhub builds a Finnhub adapter.
func NewFinnhub(key string) *Finnhub { return &Finnhub{key: key} }

func (f *Finnhub) Name() string { return "finnhub" }

// finnhubQuote maps the /quote response.
type finnhubQuote struct {
	C  float64 `json:"c"`  // current price
	D  float64 `json:"d"`  // change
	DP float64 `json:"dp"` // percent change
	H  float64 `json:"h"`  // high
	L  float64 `json:"l"`  // low
	O  float64 `json:"o"`  // open
	PC float64 `json:"pc"` // previous close
	T  int64   `json:"t"`  // unix timestamp
}

// Quote fetches a single-symbol quote. Finnhub's /quote omits volume, so volume
// fields are left zero (enriched by OHLCV ingestion in Stage 2).
func (f *Finnhub) Quote(ctx context.Context, symbol string) (models.Quote, error) {
	in, _ := Lookup(symbol)
	vendor := in.Finnhub
	if vendor == "" {
		vendor = symbol
	}

	u := fmt.Sprintf("https://finnhub.io/api/v1/quote?symbol=%s&token=%s",
		url.QueryEscape(vendor), url.QueryEscape(f.key))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return models.Quote{}, err
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return models.Quote{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return models.Quote{}, fmt.Errorf("finnhub status %d for %s", resp.StatusCode, vendor)
	}

	var fq finnhubQuote
	if err := json.NewDecoder(resp.Body).Decode(&fq); err != nil {
		return models.Quote{}, err
	}
	if fq.C == 0 && fq.PC == 0 {
		return models.Quote{}, fmt.Errorf("finnhub empty quote for %s", vendor)
	}

	ts := time.Now().UTC()
	if fq.T > 0 {
		ts = time.Unix(fq.T, 0).UTC()
	}
	return models.Quote{
		Symbol:        symbol,
		Name:          in.Name,
		AssetClass:    string(in.AssetClass),
		Last:          fq.C,
		Change:        fq.D,
		ChangePercent: fq.DP,
		Open:          fq.O,
		High:          fq.H,
		Low:           fq.L,
		PrevClose:     fq.PC,
		ATR:           fq.H - fq.L,
		Time:          ts,
	}, nil
}
