package market

import (
	"context"
	"math"
	"math/rand"
	"sync"
	"time"

	"github.com/quanta/trading-dashboard/backend/internal/models"
)

// Mock is a synthetic provider that produces plausible, gently-drifting quotes so
// the full stack can be demoed without any market-data subscription.
type Mock struct {
	mu    sync.Mutex
	state map[string]*mockState
}

type mockState struct {
	last      float64
	prevClose float64
	weekBase  float64
	dayOpen   float64
	high      float64
	low       float64
	volume    int64
	avgVolume int64
}

// seedPrices give each instrument a realistic starting point.
var seedPrices = map[string]float64{
	"SPY": 545.0, "QQQ": 470.0, "IWM": 205.0, "DIA": 395.0, "VIX": 14.2,
	"ES": 5460.0, "NQ": 19500.0, "RTY": 2050.0, "CL": 78.5, "GC": 2350.0,
	"US10Y": 4.35, "DXY": 104.8,
}

// NewMock builds a mock provider seeded from the dashboard instrument set.
func NewMock() *Mock {
	m := &Mock{state: make(map[string]*mockState)}
	for _, in := range DashboardInstruments {
		base := seedPrices[in.Symbol]
		if base == 0 {
			base = 100
		}
		vol := int64(20_000_000 + rand.Intn(60_000_000))
		m.state[in.Symbol] = &mockState{
			last:      base,
			prevClose: base * (1 - (rand.Float64()-0.5)*0.01),
			weekBase:  base * (1 - (rand.Float64()-0.5)*0.04),
			dayOpen:   base,
			high:      base,
			low:       base,
			volume:    vol / 2,
			avgVolume: vol,
		}
	}
	return m
}

func (m *Mock) Name() string { return "mock" }

// Quote returns a fresh synthetic quote, advancing a small random walk each call.
func (m *Mock) Quote(_ context.Context, symbol string) (models.Quote, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	st, ok := m.state[symbol]
	if !ok {
		st = &mockState{last: 100, prevClose: 100, weekBase: 100, dayOpen: 100, high: 100, low: 100, avgVolume: 1_000_000}
		m.state[symbol] = st
	}

	// Random walk ~0.05% step.
	step := (rand.Float64() - 0.5) * 0.001 * st.last
	st.last = math.Max(0.01, st.last+step)
	st.high = math.Max(st.high, st.last)
	st.low = math.Min(st.low, st.last)
	st.volume += int64(rand.Intn(250_000))

	in, _ := Lookup(symbol)
	q := models.Quote{
		Symbol:        symbol,
		Name:          in.Name,
		AssetClass:    string(in.AssetClass),
		Last:          round2(st.last),
		PrevClose:     round2(st.prevClose),
		Open:          round2(st.dayOpen),
		High:          round2(st.high),
		Low:           round2(st.low),
		Volume:        st.volume,
		AvgVolume:     st.avgVolume,
		Change:        round2(st.last - st.prevClose),
		ChangePercent: round2((st.last - st.prevClose) / st.prevClose * 100),
		WeekChangePct: round2((st.last - st.weekBase) / st.weekBase * 100),
		RelVolume:     round2(float64(st.volume) / float64(max64(st.avgVolume, 1))),
		ATR:           round2(st.last * 0.012),
		TrendStrength: round2(20 + rand.Float64()*60),
		Time:          time.Now().UTC(),
	}
	return q, nil
}

func round2(f float64) float64 { return math.Round(f*100) / 100 }

func max64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}
