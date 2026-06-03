/** Number/price formatting helpers for the terminal UI. */

export function fmtPrice(n: number | undefined | null, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtPct(n: number | undefined | null, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

export function fmtSignedPrice(n: number | undefined | null, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${fmtPrice(n, digits)}`;
}

/** Compact volume: 12.3M, 4.1B, etc. */
export function fmtVolume(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n) || n === 0) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

export function dirClass(n: number | undefined | null): string {
  if (n == null || n === 0) return "text-terminal-muted";
  return n > 0 ? "text-terminal-up" : "text-terminal-down";
}
