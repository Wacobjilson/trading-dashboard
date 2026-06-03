-- Stage 1 schema. Idempotent via IF NOT EXISTS so Migrate() can re-run safely.
-- Designed to scale to millions of rows; ohlcv is TimescaleDB-hypertable-ready.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Users ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Symbols (instrument reference) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS symbols (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    asset_class TEXT NOT NULL DEFAULT 'equity',
    exchange    TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Latest quote snapshot (one row per symbol, upserted) ──────────────────────
CREATE TABLE IF NOT EXISTS quotes (
    symbol         TEXT PRIMARY KEY REFERENCES symbols(symbol) ON DELETE CASCADE,
    last           DOUBLE PRECISION NOT NULL DEFAULT 0,
    change         DOUBLE PRECISION NOT NULL DEFAULT 0,
    change_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
    week_change_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    open           DOUBLE PRECISION NOT NULL DEFAULT 0,
    high           DOUBLE PRECISION NOT NULL DEFAULT 0,
    low            DOUBLE PRECISION NOT NULL DEFAULT 0,
    prev_close     DOUBLE PRECISION NOT NULL DEFAULT 0,
    volume         BIGINT NOT NULL DEFAULT 0,
    avg_volume     BIGINT NOT NULL DEFAULT 0,
    atr            DOUBLE PRECISION NOT NULL DEFAULT 0,
    trend_strength DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── OHLCV timeseries (hypertable-ready; partition/convert in Stage 2) ─────────
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol   TEXT NOT NULL REFERENCES symbols(symbol) ON DELETE CASCADE,
    ts       TIMESTAMPTZ NOT NULL,
    timeframe TEXT NOT NULL DEFAULT '1d',
    open     DOUBLE PRECISION NOT NULL,
    high     DOUBLE PRECISION NOT NULL,
    low      DOUBLE PRECISION NOT NULL,
    close    DOUBLE PRECISION NOT NULL,
    volume   BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, timeframe, ts)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_ts ON ohlcv (symbol, ts DESC);

-- ─── Watchlists ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlists (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id UUID NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol       TEXT NOT NULL,
    position     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (watchlist_id, symbol)
);

-- ─── Forward-looking stubs (fleshed out in later stages) ───────────────────────
CREATE TABLE IF NOT EXISTS news (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source       TEXT NOT NULL,
    headline     TEXT NOT NULL,
    url          TEXT,
    summary      TEXT,
    symbols      TEXT[] DEFAULT '{}',
    category     TEXT,
    sentiment    TEXT,
    impact_score INT,
    urgency_score INT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news (published_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol     TEXT,
    kind       TEXT NOT NULL,            -- price | volume | rvol | technical | flow | news | econ | earnings
    condition  JSONB NOT NULL DEFAULT '{}',
    channels   TEXT[] NOT NULL DEFAULT '{}', -- browser | email | telegram | discord | slack | push
    enabled    BOOLEAN NOT NULL DEFAULT true,
    last_fired TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_summaries (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind       TEXT NOT NULL,            -- daily | intraday | watchlist | futures
    scope      TEXT,                     -- e.g. watchlist id or 'market'
    content    TEXT NOT NULL,
    model      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_summaries_kind ON ai_summaries (kind, created_at DESC);

-- ─── Seed the core dashboard instruments ───────────────────────────────────────
INSERT INTO symbols (symbol, name, asset_class, exchange) VALUES
    ('SPY',  'SPDR S&P 500 ETF',          'etf',    'ARCA'),
    ('QQQ',  'Invesco QQQ Trust',         'etf',    'NASDAQ'),
    ('IWM',  'iShares Russell 2000 ETF',  'etf',    'ARCA'),
    ('DIA',  'SPDR Dow Jones ETF',        'etf',    'ARCA'),
    ('VIX',  'CBOE Volatility Index',     'index',  'CBOE'),
    ('ES',   'E-mini S&P 500 Futures',    'future', 'CME'),
    ('NQ',   'E-mini Nasdaq 100 Futures', 'future', 'CME'),
    ('RTY',  'E-mini Russell 2000 Futures','future','CME'),
    ('CL',   'Crude Oil WTI Futures',     'future', 'NYMEX'),
    ('GC',   'Gold Futures',              'future', 'COMEX'),
    ('US10Y','US 10-Year Treasury Yield', 'rate',   'TNX'),
    ('DXY',  'US Dollar Index',           'index',  'ICE')
ON CONFLICT (symbol) DO NOTHING;
