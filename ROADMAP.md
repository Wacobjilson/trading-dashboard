# Roadmap

The platform is built in modular stages. Stage 1 (this repo) is a deployable MVP.
Each later stage is additive and does not require rewriting earlier stages.

## Stage 1 — MVP foundation ✅ (shipped)

- [x] Monorepo + Docker Compose + Helm/K8s deploy
- [x] PostgreSQL + Redis
- [x] User registration / login (JWT, Argon2id)
- [x] Pluggable market-data provider layer (Polygon / Finnhub / Alpha Vantage / mock)
- [x] Live dashboard: SPY, QQQ, IWM, DIA, VIX, ES, NQ, RTY, CL, GC, US10Y, DXY
- [x] Per-instrument daily/weekly change, volume, relative volume, ATR, trend strength
- [x] REST API + WebSocket streaming (Redis pub/sub fan-out)
- [x] Bloomberg-style dark terminal UI

## Stage 2 — Watchlists & charting

- [ ] CRUD watchlists, persisted per user
- [ ] OHLCV ingestion → TimescaleDB hypertables
- [ ] Candlestick + volume charts (Recharts/lightweight-charts)
- [ ] Core technical indicators server-side: SMA, EMA, VWAP, RSI, MACD, ATR, Bollinger

## Stage 3 — Stock screener engine

- [ ] Fundamentals ingestion (PE, PEG, margins, growth, balance sheet, float, short interest)
- [ ] Filter DSL + query builder over Postgres
- [ ] TanStack Table results grid with saved screens
- [ ] AI scores: Bullish / Bearish / Momentum / Risk

## Stage 4 — News + economic calendar

- [ ] News aggregation workers (Benzinga, Finnhub, Polygon, FMP, NewsAPI, RSS)
- [ ] AI classification (sentiment, category, impact + urgency scores)
- [ ] Economic calendar (CPI, PPI, NFP, FOMC, GDP, auctions) with consensus/actual/surprise
- [ ] Breaking / Hot / Market Movers feeds

## Stage 5 — Options module

- [ ] Option chain ingestion, Greeks, IV / IV Rank / IV Percentile
- [ ] Unusual volume/OI, sweeps, blocks scanner
- [ ] Expected move, max pain, gamma exposure (GEX) + dealer positioning charts

## Stage 6 — Futures & order flow

- [ ] Footprint / volume delta / cumulative delta
- [ ] Market & volume profile (POC, VAH/VAL, HVN/LVN)
- [ ] Anchored VWAP, realized vol

## Stage 7 — Alert engine + AI intelligence

- [ ] Rules engine (price, volume, RVOL, technicals, flow, news, econ, earnings)
- [ ] Delivery: browser, email, Telegram, Discord, Slack, mobile push
- [ ] AI summaries: daily, intraday, watchlist, futures

## Stage 8 — Hardening & production

- [ ] GraphQL gateway, OpenAPI spec, SDK
- [ ] CI/CD (GitHub Actions → GHCR → Helm), image signing
- [ ] Observability: Prometheus metrics, Grafana, OTel tracing, structured logs
- [ ] Backups (pgBackRest), PITR, DR runbook
- [ ] Role-based access, audit log, 2FA
