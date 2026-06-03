package market

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/models"
)

// AlphaVantage adapter — GLOBAL_QUOTE endpoint.
// https://www.alphavantage.co/documentation/#latestprice
// Note: the free tier is rate-limited (5 req/min, 25/day); the ingestion poller
// should use a slow interval when this provider is active.
type AlphaVantage struct {
	key string
}

// NewAlphaVantage builds an Alpha Vantage adapter.
func NewAlphaVantage(key string) *AlphaVantage { return &AlphaVantage{key: key} }

func (a *AlphaVantage) Name() string { return "alphavantage" }

type avGlobalQuote struct {
	GlobalQuote struct {
		Price            string `json:"05. price"`
		Open             string `json:"02. open"`
		High             string `json:"03. high"`
		Low              string `json:"04. low"`
		Volume           string `json:"06. volume"`
		PreviousClose    string `json:"08. previous close"`
		Change           string `json:"09. change"`
		ChangePercent    string `json:"10. change percent"`
	} `json:"Global Quote"`
}

// Quote fetches a single-symbol global quote.
func (a *AlphaVantage) Quote(ctx context.Context, symbol string) (models.Quote, error) {
	in, _ := Lookup(symbol)
	vendor := in.AlphaVantage
	if vendor == "" {
		vendor = symbol
	}

	u := fmt.Sprintf("https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=%s&apikey=%s",
		url.QueryEscape(vendor), url.QueryEscape(a.key))
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
		return models.Quote{}, fmt.Errorf("alphavantage status %d for %s", resp.StatusCode, vendor)
	}

	var gq avGlobalQuote
	if err := json.NewDecoder(resp.Body).Decode(&gq); err != nil {
		return models.Quote{}, err
	}
	q := gq.GlobalQuote
	if q.Price == "" {
		return models.Quote{}, fmt.Errorf("alphavantage empty/limited quote for %s", vendor)
	}

	last := parseF(q.Price)
	prev := parseF(q.PreviousClose)
	high := parseF(q.High)
	low := parseF(q.Low)
	return models.Quote{
		Symbol:        symbol,
		Name:          in.Name,
		AssetClass:    string(in.AssetClass),
		Last:          last,
		Change:        parseF(q.Change),
		ChangePercent: parsePct(q.ChangePercent),
		Open:          parseF(q.Open),
		High:          high,
		Low:           low,
		PrevClose:     prev,
		Volume:        parseI(q.Volume),
		ATR:           high - low,
		Time:          time.Now().UTC(),
	}, nil
}

func parseF(s string) float64 {
	f, _ := strconv.ParseFloat(s, 64)
	return f
}

func parseI(s string) int64 {
	i, _ := strconv.ParseInt(s, 10, 64)
	return i
}

// parsePct handles values like "1.2345%".
func parsePct(s string) float64 {
	if len(s) > 0 && s[len(s)-1] == '%' {
		s = s[:len(s)-1]
	}
	return parseF(s)
}
