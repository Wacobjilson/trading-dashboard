// Package store provides typed data access over the Postgres pool.
package store

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/quanta/trading-dashboard/backend/internal/models"
)

// ErrNotFound is returned when a row does not exist.
var ErrNotFound = errors.New("not found")

// Store wraps the connection pool.
type Store struct {
	pool *pgxpool.Pool
}

// New creates a Store.
func New(pool *pgxpool.Pool) *Store { return &Store{pool: pool} }

// ─── Users ──────────────────────────────────────────────────────────────────

// CreateUser inserts a new user and returns it. Email uniqueness is enforced by
// the DB; the caller should surface a 409 on a unique-violation error.
func (s *Store) CreateUser(ctx context.Context, email, displayName, passwordHash string) (models.User, error) {
	var u models.User
	err := s.pool.QueryRow(ctx,
		`INSERT INTO users (email, display_name, password_hash)
		 VALUES ($1, $2, $3)
		 RETURNING id, email, display_name, password_hash, created_at`,
		email, displayName, passwordHash,
	).Scan(&u.ID, &u.Email, &u.DisplayName, &u.PasswordHash, &u.CreatedAt)
	return u, err
}

// UserByEmail looks up a user by email.
func (s *Store) UserByEmail(ctx context.Context, email string) (models.User, error) {
	var u models.User
	err := s.pool.QueryRow(ctx,
		`SELECT id, email, display_name, password_hash, created_at
		 FROM users WHERE email = $1`, email,
	).Scan(&u.ID, &u.Email, &u.DisplayName, &u.PasswordHash, &u.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

// UserByID looks up a user by id.
func (s *Store) UserByID(ctx context.Context, id string) (models.User, error) {
	var u models.User
	err := s.pool.QueryRow(ctx,
		`SELECT id, email, display_name, password_hash, created_at
		 FROM users WHERE id = $1`, id,
	).Scan(&u.ID, &u.Email, &u.DisplayName, &u.PasswordHash, &u.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

// ─── Quotes ──────────────────────────────────────────────────────────────────

// UpsertQuote writes the latest snapshot for a symbol.
func (s *Store) UpsertQuote(ctx context.Context, q models.Quote) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO quotes
		   (symbol, last, change, change_percent, week_change_pct, open, high, low,
		    prev_close, volume, avg_volume, atr, trend_strength, updated_at)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13, now())
		 ON CONFLICT (symbol) DO UPDATE SET
		   last=EXCLUDED.last, change=EXCLUDED.change, change_percent=EXCLUDED.change_percent,
		   week_change_pct=EXCLUDED.week_change_pct, open=EXCLUDED.open, high=EXCLUDED.high,
		   low=EXCLUDED.low, prev_close=EXCLUDED.prev_close, volume=EXCLUDED.volume,
		   avg_volume=EXCLUDED.avg_volume, atr=EXCLUDED.atr,
		   trend_strength=EXCLUDED.trend_strength, updated_at=now()`,
		q.Symbol, q.Last, q.Change, q.ChangePercent, q.WeekChangePct, q.Open, q.High,
		q.Low, q.PrevClose, q.Volume, q.AvgVolume, q.ATR, q.TrendStrength,
	)
	return err
}

// LatestQuotes returns the latest snapshot for the requested symbols.
func (s *Store) LatestQuotes(ctx context.Context, symbols []string) ([]models.Quote, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT q.symbol, COALESCE(s.name,''), COALESCE(s.asset_class,''),
		        q.last, q.change, q.change_percent, q.week_change_pct, q.open, q.high,
		        q.low, q.prev_close, q.volume, q.avg_volume, q.atr, q.trend_strength, q.updated_at
		 FROM quotes q LEFT JOIN symbols s ON s.symbol = q.symbol
		 WHERE q.symbol = ANY($1)
		 ORDER BY q.symbol`, symbols)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []models.Quote
	for rows.Next() {
		var q models.Quote
		if err := rows.Scan(&q.Symbol, &q.Name, &q.AssetClass, &q.Last, &q.Change,
			&q.ChangePercent, &q.WeekChangePct, &q.Open, &q.High, &q.Low, &q.PrevClose,
			&q.Volume, &q.AvgVolume, &q.ATR, &q.TrendStrength, &q.Time); err != nil {
			return nil, err
		}
		out = append(out, q)
	}
	return out, rows.Err()
}
