"use client";

import { useMemo, useRef, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import type { Quote } from "@/lib/types";
import { dirClass, fmtPct, fmtPrice, fmtSignedPrice, fmtVolume } from "@/lib/format";
import { cn } from "@/lib/utils";

/** A price cell that flashes green/red when the value changes. */
function PriceCell({ value }: { value: number }) {
  const prev = useRef(value);
  const [flash, setFlash] = useState("");
  if (value !== prev.current) {
    const dir = value > prev.current ? "flash-up" : "flash-down";
    prev.current = value;
    // schedule clear on next tick
    setTimeout(() => setFlash(""), 600);
    if (flash !== dir) setTimeout(() => setFlash(dir), 0);
  }
  return <span className={cn("tnum px-1 rounded", flash)}>{fmtPrice(value)}</span>;
}

function TrendBar({ value }: { value?: number }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const color = v >= 60 ? "bg-terminal-up" : v >= 35 ? "bg-terminal-amber" : "bg-terminal-down";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded bg-terminal-border">
        <div className={cn("h-1.5 rounded", color)} style={{ width: `${v}%` }} />
      </div>
      <span className="tnum text-xs text-terminal-muted">{v.toFixed(0)}</span>
    </div>
  );
}

export function QuoteTable({ data }: { data: Quote[] }) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<Quote>[]>(
    () => [
      {
        accessorKey: "symbol",
        header: "Symbol",
        cell: (c) => (
          <div className="flex flex-col">
            <span className="font-semibold text-terminal-text">{c.getValue<string>()}</span>
            <span className="text-xs text-terminal-muted">{c.row.original.name}</span>
          </div>
        ),
      },
      {
        accessorKey: "last",
        header: "Last",
        cell: (c) => <PriceCell value={c.getValue<number>()} />,
      },
      {
        accessorKey: "change",
        header: "Chg",
        cell: (c) => (
          <span className={cn("tnum", dirClass(c.getValue<number>()))}>
            {fmtSignedPrice(c.getValue<number>())}
          </span>
        ),
      },
      {
        accessorKey: "changePercent",
        header: "Chg %",
        cell: (c) => (
          <span className={cn("tnum", dirClass(c.getValue<number>()))}>
            {fmtPct(c.getValue<number>())}
          </span>
        ),
      },
      {
        accessorKey: "weekChangePct",
        header: "Wk %",
        cell: (c) => (
          <span className={cn("tnum", dirClass(c.getValue<number>()))}>
            {fmtPct(c.getValue<number>())}
          </span>
        ),
      },
      {
        accessorKey: "volume",
        header: "Volume",
        cell: (c) => <span className="tnum text-terminal-muted">{fmtVolume(c.getValue<number>())}</span>,
      },
      {
        accessorKey: "relVolume",
        header: "RVOL",
        cell: (c) => {
          const v = c.getValue<number>() ?? 0;
          return (
            <span className={cn("tnum", v >= 1.5 ? "text-terminal-amber" : "text-terminal-muted")}>
              {v ? `${v.toFixed(2)}x` : "—"}
            </span>
          );
        },
      },
      {
        accessorKey: "atr",
        header: "ATR",
        cell: (c) => <span className="tnum text-terminal-muted">{fmtPrice(c.getValue<number>())}</span>,
      },
      {
        accessorKey: "trendStrength",
        header: "Trend",
        cell: (c) => <TrendBar value={c.getValue<number>()} />,
      },
    ],
    [],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="overflow-x-auto rounded-lg border border-terminal-border">
      <table className="w-full text-sm">
        <thead className="bg-terminal-panelAlt">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  onClick={h.column.getToggleSortingHandler()}
                  className="cursor-pointer select-none px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-terminal-muted hover:text-terminal-text"
                >
                  {flexRender(h.column.columnDef.header, h.getContext())}
                  {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="border-t border-terminal-border hover:bg-terminal-panelAlt/50"
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
