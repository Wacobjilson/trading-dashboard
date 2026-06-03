package market

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/models"
)

// Polygon adapter — uses the v2 snapshot endpoint for rich single-symbol data.
// https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_tickers__stocksTicker
type Polygon struct {
	key string
}

// NewPolygon builds a Polygon adapter.
func NewPolygon(key string) *Polygon { return &Polygon{key: key} }

func (p *Polygon) Name() string { return "polygon" }

type polygonSnapshotResp struct {
	Ticker struct {
		Day struct {
			O float64 `json:"o"`
			H float64 `json:"h"`
			L float64 `json:"l"`
			C float64 `json:"c"`
			V float64 `json:"v"`
		} `json:"day"`
		PrevDay struct {
			C float64 `json:"c"`
			V float64 `json:"v"`
		} `json:"prevDay"`
		LastTrade struct {
			P float64 `json:"p"`
			T int64   `json:"t"` // ns timestamp
		} `json:"lastTrade"`
		TodaysChange    float64 `json:"todaysChange"`
		TodaysChangePct float64 `json:"todaysChangePerc"`
	} `json:"ticker"`
}

// Quote fetches a single-symbol snapshot. Index symbols (prefixed "I:") use the
// indices snapshot path; everything else uses the stocks path.
func (p *Polygon) Quote(ctx context.Context, symbol string) (models.Quote, error) {
	in, _ := Lookup(symbol)
	vendor := in.Polygon
	if vendor == "" {
		vendor = symbol
	}

	var u string
	if strings.HasPrefix(vendor, "I:") {
		u = fmt.Sprintf("https://api.polygon.io/v3/snapshot/indices?ticker=%s&apiKey=%s",
			url.QueryEscape(vendor), url.QueryEscape(p.key))
		return p.quoteIndex(ctx, symbol, in, u)
	}
	u = fmt.Sprintf("https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/%s?apiKey=%s",
		url.QueryEscape(vendor), url.QueryEscape(p.key))

	body, err := p.get(ctx, u)
	if err != nil {
		return models.Quote{}, err
	}
	var sr polygonSnapshotResp
	if err := json.Unmarshal(body, &sr); err != nil {
		return models.Quote{}, err
	}

	t := sr.Ticker
	last := t.LastTrade.P
	if last == 0 {
		last = t.Day.C
	}
	prev := t.PrevDay.C
	weekPct := 0.0
	if prev != 0 {
		weekPct = (last - prev) / prev * 100 // refined to true 5d in Stage 2
	}
	relVol := 0.0
	if t.PrevDay.V > 0 {
		relVol = t.Day.V / t.PrevDay.V
	}
	ts := time.Now().UTC()
	if t.LastTrade.T > 0 {
		ts = time.Unix(0, t.LastTrade.T).UTC()
	}
	return models.Quote{
		Symbol:        symbol,
		Name:          in.Name,
		AssetClass:    string(in.AssetClass),
		Last:          last,
		Change:        t.TodaysChange,
		ChangePercent: t.TodaysChangePct,
		WeekChangePct: weekPct,
		Open:          t.Day.O,
		High:          t.Day.H,
		Low:           t.Day.L,
		PrevClose:     prev,
		Volume:        int64(t.Day.V),
		AvgVolume:     int64(t.PrevDay.V),
		RelVolume:     relVol,
		ATR:           t.Day.H - t.Day.L,
		Time:          ts,
	}, nil
}

type polygonIndexResp struct {
	Results []struct {
		Value   float64 `json:"value"`
		Session struct {
			Change        float64 `json:"change"`
			ChangePercent float64 `json:"change_percent"`
			Open          float64 `json:"open"`
			High          float64 `json:"high"`
			Low           float64 `json:"low"`
			PreviousClose float64 `json:"previous_close"`
		} `json:"session"`
	} `json:"results"`
}

func (p *Polygon) quoteIndex(ctx context.Context, symbol string, in Instrument, u string) (models.Quote, error) {
	body, err := p.get(ctx, u)
	if err != nil {
		return models.Quote{}, err
	}
	var ir polygonIndexResp
	if err := json.Unmarshal(body, &ir); err != nil {
		return models.Quote{}, err
	}
	if len(ir.Results) == 0 {
		return models.Quote{}, fmt.Errorf("polygon index empty for %s", symbol)
	}
	r := ir.Results[0]
	return models.Quote{
		Symbol:        symbol,
		Name:          in.Name,
		AssetClass:    string(in.AssetClass),
		Last:          r.Value,
		Change:        r.Session.Change,
		ChangePercent: r.Session.ChangePercent,
		Open:          r.Session.Open,
		High:          r.Session.High,
		Low:           r.Session.Low,
		PrevClose:     r.Session.PreviousClose,
		ATR:           r.Session.High - r.Session.Low,
		Time:          time.Now().UTC(),
	}, nil
}

func (p *Polygon) get(ctx context.Context, u string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("polygon status %d", resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}
