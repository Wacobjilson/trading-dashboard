# Quanta standalone — tiny image (stdlib-only Python, no pip install needed).
FROM python:3.12-alpine

# CA certs for outbound HTTPS to Polygon / Finnhub / the calendar feed.
RUN apk add --no-cache ca-certificates wget && adduser -D -u 10001 app

WORKDIR /app
# App = the server + the dashboard page. Research/backtest scripts included so you
# can `docker exec` into the container and run them.
# *.md docs are the AI analyst's RAG knowledge base (see RAG_ARCHITECTURE.md)
COPY quanta.py index.html backtest.py research.py research_futures.py smoketest.py *.md ./

# Build gate (STRESS_TEST.md Fix #3): every view must run clean on synthetic
# data before an image ships. No network needed; ~2s.
RUN python smoketest.py && rm -rf smoke_data

USER app
EXPOSE 8000
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=5 \
  CMD wget -qO- "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 || exit 1

CMD ["python", "quanta.py"]
