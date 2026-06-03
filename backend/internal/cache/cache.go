// Package cache wraps Redis for quote caching, pub/sub fan-out, and rate limiting.
package cache

import (
	"context"
	"encoding/json"
	"time"

	"github.com/redis/go-redis/v9"
)

// Cache wraps a Redis client.
type Cache struct {
	rdb *redis.Client
}

// QuotesChannel is the Redis pub/sub channel used to fan quote updates out to all
// backend replicas so WebSocket clients on any pod receive them.
const QuotesChannel = "quotes"

// Connect parses a redis:// URL and returns a ready client.
func Connect(ctx context.Context, url string) (*Cache, error) {
	opt, err := redis.ParseURL(url)
	if err != nil {
		return nil, err
	}
	rdb := redis.NewClient(opt)
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, err
	}
	return &Cache{rdb: rdb}, nil
}

// Close shuts the client down.
func (c *Cache) Close() error { return c.rdb.Close() }

// Raw exposes the underlying client for advanced use.
func (c *Cache) Raw() *redis.Client { return c.rdb }

// SetJSON stores any value as JSON with a TTL.
func (c *Cache) SetJSON(ctx context.Context, key string, v any, ttl time.Duration) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return c.rdb.Set(ctx, key, b, ttl).Err()
}

// GetJSON loads a JSON value into dst; returns false if the key is missing.
func (c *Cache) GetJSON(ctx context.Context, key string, dst any) (bool, error) {
	b, err := c.rdb.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, json.Unmarshal(b, dst)
}

// Publish sends a JSON-encoded message on a channel.
func (c *Cache) Publish(ctx context.Context, channel string, v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return c.rdb.Publish(ctx, channel, b).Err()
}

// Subscribe returns a pub/sub subscription on the given channel.
func (c *Cache) Subscribe(ctx context.Context, channel string) *redis.PubSub {
	return c.rdb.Subscribe(ctx, channel)
}

// AllowN implements a simple fixed-window rate limit. Returns true if the action
// is permitted, incrementing the per-key counter (window resets via TTL).
func (c *Cache) AllowN(ctx context.Context, key string, limit int64, window time.Duration) (bool, error) {
	n, err := c.rdb.Incr(ctx, key).Result()
	if err != nil {
		return false, err
	}
	if n == 1 {
		_ = c.rdb.Expire(ctx, key, window).Err()
	}
	return n <= limit, nil
}
