import { ArrowDownRight, ArrowRight, ArrowUpRight, ImageOff } from "lucide-react";
import { formatEur, formatPct, formatSignedEur } from "@/lib/format";
import type { PortfolioItem } from "@/lib/types";
import { ConditionBadge } from "./ConditionBadge";
import { PriceChart } from "./PriceChart";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-bg px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Trend({ avg30, trend }: { avg30: number | null; trend: number | null }) {
  if (avg30 == null || trend == null || avg30 === 0) return <Metric label="Tendance" value="—" />;
  const delta = ((trend - avg30) / avg30) * 100;
  const Icon = delta > 1 ? ArrowUpRight : delta < -1 ? ArrowDownRight : ArrowRight;
  const color = delta > 1 ? "text-emerald-400" : delta < -1 ? "text-red-400" : "text-muted";
  return (
    <div className="rounded border border-line bg-bg px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-muted">Tendance</div>
      <div className={`mt-0.5 flex items-center gap-1 text-base font-semibold tabular-nums ${color}`}>
        <Icon className="h-4 w-4" />
        {formatEur(trend)} <span className="text-xs font-normal">({formatPct(delta)} vs 30 j)</span>
      </div>
    </div>
  );
}

export function CardHero({ item }: { item: PortfolioItem }) {
  const { card, price } = item;
  const gain = price?.current != null ? price.current - item.buyPrice : null;
  const gainPct = gain != null && item.buyPrice > 0 ? (gain / item.buyPrice) * 100 : null;

  return (
    <section className="grid gap-5 rounded border border-line bg-panel p-4 lg:grid-cols-[220px_minmax(0,1.1fr)_minmax(0,1fr)]">
      <div className="mx-auto w-[220px]">
        {card.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={card.image}
            alt={card.name}
            className="w-full rounded-[4.5%] shadow-lg shadow-black/50"
            width={220}
            height={307}
          />
        ) : (
          <div className="flex aspect-[5/7] w-full items-center justify-center rounded border border-line text-muted">
            <ImageOff className="h-8 w-8" />
          </div>
        )}
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-bold">{card.name}</h1>
          <ConditionBadge condition={item.condition} />
        </div>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">Ticker</dt>
          <dd className="font-mono">{item.ticker}</dd>
          <dt className="text-muted">Extension</dt>
          <dd>
            {card.setName} <span className="text-muted">({card.setId})</span>
          </dd>
          <dt className="text-muted">Numéro</dt>
          <dd>{card.number}</dd>
          <dt className="text-muted">Rareté</dt>
          <dd>{card.rarity}</dd>
        </dl>

        {price ? (
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Metric label="Prix d'achat" value={formatEur(item.buyPrice)} />
            <Metric label="Prix RAW actuel" value={formatEur(price.current)} />
            <Metric
              label="Plus-value"
              value={
                gain == null ? "—" : `${formatSignedEur(gain)}${gainPct != null ? ` (${formatPct(gainPct)})` : ""}`
              }
            />
            <Metric label="Moy. 1 j" value={formatEur(price.avg1)} />
            <Metric label="Moy. 7 j" value={formatEur(price.avg7)} />
            <Metric label="Moy. 30 j" value={formatEur(price.avg30)} />
            <div className="col-span-2 sm:col-span-3">
              <Trend avg30={price.avg30} trend={price.trend} />
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted">Aucun prix disponible.</p>
        )}
        {price && (
          <p className="mt-2 text-[11px] text-muted">
            Source : {price.source === "scrydex" ? "Scrydex" : "Cardmarket via TCGdex"} · mis à jour le{" "}
            {new Date(price.updatedAt).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
          </p>
        )}
        {price?.warning && <p className="mt-1 text-[11px] text-amber-400">{price.warning}</p>}
      </div>

      <div className="min-w-0 rounded border border-line bg-bg p-3">
        {price ? (
          <PriceChart price={price} buyPrice={item.buyPrice} />
        ) : (
          <div className="flex h-full min-h-[200px] items-center justify-center text-sm text-muted">—</div>
        )}
      </div>
    </section>
  );
}
