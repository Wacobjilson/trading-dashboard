// Package models defines core domain types shared across the backend.
package models

import "time"

// AssetClass categorizes a tradable instrument.
type AssetClass string

const (
	AssetEquity AssetClass = "equity"
	AssetETF    AssetClass = "etf"
	AssetIndex  AssetClass = "index"
	AssetFuture AssetClass = "future"
	AssetForex  AssetClass = "forex"
	AssetCrypto AssetClass = "crypto"
	AssetRate   AssetClass = "rate" // treasury yields, etc.
)

// Symbol describes a tradable instrument tracked by the platform.
type Symbol struct {
	Symbol     string     `json:"symbol"`
	Name       string     `json:"name"`
	AssetClass AssetClass `json:"assetClass"`
	Exchange   string     `json:"exchange,omitempty"`
}

// Quote is a normalized market snapshot for a single instrument.
// All adapters map their vendor payloads into this shape.
type Quote struct {
	Symbol        string    `json:"symbol"`
	Name          string    `json:"name,omitempty"`
	AssetClass    string    `json:"assetClass,omitempty"`
	Last          float64   `json:"last"`
	Change        float64   `json:"change"`         // absolute day change
	ChangePercent float64   `json:"changePercent"`  // day change %
	WeekChangePct float64   `json:"weekChangePct"`  // 5-day change %
	Open          float64   `json:"open"`
	High          float64   `json:"high"`
	Low           float64   `json:"low"`
	PrevClose     float64   `json:"prevClose"`
	Volume        int64     `json:"volume"`
	AvgVolume     int64     `json:"avgVolume,omitempty"`
	RelVolume     float64   `json:"relVolume,omitempty"` // volume / avgVolume
	ATR           float64   `json:"atr,omitempty"`
	TrendStrength float64   `json:"trendStrength,omitempty"` // 0..100 (ADX-like proxy)
	Time          time.Time `json:"time"`
}

// User is an authenticated account.
type User struct {
	ID           string    `json:"id"`
	Email        string    `json:"email"`
	DisplayName  string    `json:"displayName"`
	PasswordHash string    `json:"-"`
	CreatedAt    time.Time `json:"createdAt"`
}

// Watchlist is a named collection of symbols owned by a user.
type Watchlist struct {
	ID      string   `json:"id"`
	UserID  string   `json:"userId"`
	Name    string   `json:"name"`
	Symbols []string `json:"symbols"`
}
