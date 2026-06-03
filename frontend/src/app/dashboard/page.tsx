"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useQuotesStream } from "@/lib/useQuotesStream";
import { QuoteTable } from "@/components/QuoteTable";
import { Button } from "@/components/ui/button";
import { dirClass, fmtPct, fmtPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Quote } from "@/lib/types";

const DASHBOARD_SYMBOLS = [
  "SPY", "QQQ", "IWM", "DIA", "VIX",
  "ES", "NQ", "RTY", "CL", "GC", "US10Y", "DXY",
];

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  // Seed snapshot from REST, then take over with the live WS stream.
  const { data: seed } = useQuery({
    queryKey: ["quotes"],
    queryFn: () => api.quotes(DASHBOARD_SYMBOLS),
    enabled: !!user,
    refetchInterval: 30_000,
  });

  const live = useQuotesStream(DASHBOARD_SYMBOLS, seed?.quotes);

  const rows: Quote[] = useMemo(() => {
    return DASHBOARD_SYMBOLS.map((s) => live[s]).filter(Boolean) as Quote[];
  }, [live]);

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center text-terminal-muted">Loading…</div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-terminal-border bg-terminal-panel px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-terminal-amber font-bold tracking-tight">QUANTA</span>
          <span className="text-xs text-terminal-muted">TERMINAL · MVP</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-terminal-muted">{user.displayName || user.email}</span>
          <Button variant="outline" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>

      <main className="space-y-6 p-4">
        {/* Heat strip */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-terminal-muted">
            Market Overview
          </h2>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {rows.map((q) => (
              <HeatTile key={q.symbol} q={q} />
            ))}
            {rows.length === 0 && (
              <div className="col-span-full py-8 text-center text-terminal-muted">
                Waiting for first quotes… (provider may be in mock mode)
              </div>
            )}
          </div>
        </section>

        {/* Full grid */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-terminal-muted">
            Watch Grid
          </h2>
          <QuoteTable data={rows} />
        </section>
      </main>
    </div>
  );
}

function HeatTile({ q }: { q: Quote }) {
  const up = q.changePercent >= 0;
  return (
    <div
      className={cn(
        "rounded-md border border-terminal-border bg-terminal-panel p-3",
        "relative overflow-hidden",
      )}
    >
      <div
        className={cn("absolute inset-y-0 left-0 w-1", up ? "bg-terminal-up" : "bg-terminal-down")}
      />
      <div className="flex items-baseline justify-between">
        <span className="font-semibold">{q.symbol}</span>
        <span className={cn("tnum text-sm", dirClass(q.changePercent))}>
          {fmtPct(q.changePercent)}
        </span>
      </div>
      <div className="tnum mt-1 text-lg">{fmtPrice(q.last)}</div>
      <div className="truncate text-xs text-terminal-muted">{q.name}</div>
    </div>
  );
}
