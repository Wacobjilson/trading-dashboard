"use client";

import { useEffect, useRef, useState } from "react";
import { getToken } from "./api";
import type { Quote } from "./types";

// Resolve the WebSocket base URL. If NEXT_PUBLIC_WS_BASE_URL is unset, derive it
// from the current page origin (same-origin behind an ingress).
function wsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_BASE_URL) return process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

/**
 * useQuotesStream opens a WebSocket to the backend, subscribes to the given
 * symbols' quote topics, and returns a live symbol→Quote map. Reconnects with
 * backoff. Seed with initial REST data to avoid an empty first paint.
 */
export function useQuotesStream(symbols: string[], seed?: Quote[]) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>(() => {
    const m: Record<string, Quote> = {};
    (seed || []).forEach((q) => (m[q.symbol] = q));
    return m;
  });
  const wsRef = useRef<WebSocket | null>(null);
  const symbolsKey = symbols.join(",");

  useEffect(() => {
    let closed = false;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout>;

    function connect() {
      const token = getToken();
      if (!token) return;
      const ws = new WebSocket(`${wsBase()}/ws?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        retry = 0;
        ws.send(
          JSON.stringify({
            action: "subscribe",
            topics: symbols.map((s) => `quote:${s}`),
          }),
        );
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as { topic: string; data: Quote };
          if (msg.topic?.startsWith("quote:") && msg.data?.symbol) {
            setQuotes((prev) => ({ ...prev, [msg.data.symbol]: msg.data }));
          }
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = () => {
        if (closed) return;
        retry += 1;
        const delay = Math.min(1000 * 2 ** retry, 15000);
        timer = setTimeout(connect, delay);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey]);

  return quotes;
}
