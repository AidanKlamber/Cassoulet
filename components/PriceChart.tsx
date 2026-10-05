"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatEur } from "@/lib/format";
import type { PriceData } from "@/lib/types";

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });

export function PriceChart({ price, buyPrice }: { price: PriceData; buyPrice: number }) {
  const daily = price.historyKind === "daily";
  const data = price.history;
  const up = data.length > 1 && data[data.length - 1].price >= data[0].price;
  const color = up ? "#10b981" : "#ef4444";

  if (data.length < 2) {
    return (
      <div className="flex h-full min-h-[200px] items-center justify-center text-sm text-muted">
        Historique indisponible pour cette carte
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#2a3241" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tickFormatter={daily ? fmtDate : undefined}
            stroke="#8b95a7"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#2a3241" }}
            minTickGap={24}
          />
          <YAxis
            stroke="#8b95a7"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={56}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => `${v.toFixed(v >= 10 ? 0 : 2)} €`}
          />
          <Tooltip
            contentStyle={{ background: "#12161f", border: "1px solid #2a3241", borderRadius: 4, fontSize: 12 }}
            labelStyle={{ color: "#8b95a7" }}
            labelFormatter={(l) => (daily ? fmtDate(String(l)) : String(l))}
            formatter={(v: number) => [formatEur(v), "Prix RAW"]}
          />
          <Area
            type="monotone"
            dataKey="price"
            stroke={color}
            strokeWidth={2}
            fill="url(#fill)"
            dot={!daily}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      <p className="mt-1 text-[11px] text-muted">
        {daily
          ? "Historique quotidien du prix RAW (Scrydex)"
          : "Moyennes Cardmarket 30 j / 7 j / 1 j et tendance — pas d'historique quotidien sans Scrydex"}
        {" · "}achat {formatEur(buyPrice)}
      </p>
    </div>
  );
}
