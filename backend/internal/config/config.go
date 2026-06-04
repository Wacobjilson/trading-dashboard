// Package config loads runtime configuration from environment variables.
package config

import (
	"os"
	"strings"
	"time"
)

// Config holds all runtime configuration for the backend.
type Config struct {
	APIPort     string
	LogLevel    string
	JWTSecret   string
	CORSOrigins []string
	// DisableAuth runs the app in single-user mode: no login/register required,
	// all requests act as a built-in local user. For private/self-hosted use only.
	DisableAuth bool

	DatabaseURL string
	RedisURL    string

	// Market data
	MarketProvider    string // explicit override; empty = auto-detect
	PolygonKey        string
	FinnhubKey        string
	AlphaVantageKey   string
	TwelveDataKey     string
	QuotePollInterval time.Duration

	// AI
	AIProvider     string
	AnthropicKey   string
	AnthropicModel string
	OpenAIKey      string
	GeminiKey      string
	OpenRouterKey  string
	OllamaBaseURL  string
}

// Load reads configuration from the environment, applying sensible defaults.
func Load() *Config {
	return &Config{
		APIPort:     env("API_PORT", "8080"),
		LogLevel:    env("LOG_LEVEL", "info"),
		JWTSecret:   env("JWT_SECRET", "change-me-to-a-long-random-secret"),
		CORSOrigins: splitCSV(env("CORS_ALLOWED_ORIGINS", "http://localhost:3000")),
		DisableAuth: envBool("DISABLE_AUTH", false),

		DatabaseURL: env("DATABASE_URL", "postgres://quanta:quanta@localhost:5432/quanta?sslmode=disable"),
		RedisURL:    env("REDIS_URL", "redis://localhost:6379/0"),

		MarketProvider:    strings.ToLower(env("MARKET_DATA_PROVIDER", "")),
		PolygonKey:        env("POLYGON_API_KEY", ""),
		FinnhubKey:        env("FINNHUB_API_KEY", ""),
		AlphaVantageKey:   env("ALPHAVANTAGE_API_KEY", ""),
		TwelveDataKey:     env("TWELVEDATA_API_KEY", ""),
		QuotePollInterval: envDuration("QUOTE_POLL_INTERVAL", 5*time.Second),

		AIProvider:     strings.ToLower(env("AI_PROVIDER", "anthropic")),
		AnthropicKey:   env("ANTHROPIC_API_KEY", ""),
		AnthropicModel: env("ANTHROPIC_MODEL", "claude-opus-4-8"),
		OpenAIKey:      env("OPENAI_API_KEY", ""),
		GeminiKey:      env("GEMINI_API_KEY", ""),
		OpenRouterKey:  env("OPENROUTER_API_KEY", ""),
		OllamaBaseURL:  env("OLLAMA_BASE_URL", "http://localhost:11434"),
	}
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envBool(key string, def bool) bool {
	switch strings.ToLower(os.Getenv(key)) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return def
	}
}

func envDuration(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}

func splitCSV(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}
