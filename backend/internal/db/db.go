// Package db manages the PostgreSQL connection pool and migrations.
package db

import (
	"context"
	"embed"
	"fmt"
	"sort"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed migrations/*.sql
var migrationFS embed.FS

// DB wraps a pgx connection pool.
type DB struct {
	Pool *pgxpool.Pool
}

// Connect opens a pooled connection to Postgres, retrying briefly so the service
// can start alongside the database in compose/k8s.
func Connect(ctx context.Context, url string) (*DB, error) {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		return nil, fmt.Errorf("parse database url: %w", err)
	}
	cfg.MaxConns = 20
	cfg.MaxConnLifetime = time.Hour

	var pool *pgxpool.Pool
	for attempt := 1; attempt <= 15; attempt++ {
		pool, err = pgxpool.NewWithConfig(ctx, cfg)
		if err == nil {
			if pingErr := pool.Ping(ctx); pingErr == nil {
				return &DB{Pool: pool}, nil
			} else {
				err = pingErr
				pool.Close()
			}
		}
		time.Sleep(2 * time.Second)
	}
	return nil, fmt.Errorf("connect postgres after retries: %w", err)
}

// Close releases the pool.
func (d *DB) Close() { d.Pool.Close() }

// Migrate applies all embedded .sql migrations in lexical order. Each file runs
// inside the same connection; idempotent via IF NOT EXISTS guards in the SQL.
func (d *DB) Migrate(ctx context.Context) error {
	entries, err := migrationFS.ReadDir("migrations")
	if err != nil {
		return err
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	for _, name := range names {
		sqlBytes, err := migrationFS.ReadFile("migrations/" + name)
		if err != nil {
			return fmt.Errorf("read migration %s: %w", name, err)
		}
		if _, err := d.Pool.Exec(ctx, string(sqlBytes)); err != nil {
			return fmt.Errorf("apply migration %s: %w", name, err)
		}
	}
	return nil
}
