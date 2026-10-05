import { RefreshCw, Trash2 } from "lucide-react";
import { formatEur, formatPct, formatSignedEur } from "@/lib/format";
import type { PortfolioItem } from "@/lib/types";
import { ConditionBadge } from "./ConditionBadge";

interface Props {
  items: PortfolioItem[];
  selectedUid: string | null;
  errors: Record<string, string>;
  refreshing: boolean;
  onSelect: (uid: string) => void;
  onRemove: (uid: string) => void;
  onRefresh: () => void;
}

const th = "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted";

export function PortfolioTable({ items, selectedUid, errors, refreshing, onSelect, onRemove, onRefresh }: Props) {
  const invested = items.reduce((s, i) => s + i.buyPrice, 0);
  const value = items.reduce((s, i) => s + (i.price?.current ?? i.buyPrice), 0);
  const gain = value - invested;
  const gainPct = invested > 0 ? (gain / invested) * 100 : 0;
  const gainColor = gain > 0 ? "text-emerald-400" : gain < 0 ? "text-red-400" : "text-muted";

  return (
    <section className="rounded border border-line bg-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <h2 className="font-semibold">Mon portefeuille ({items.length})</h2>
          <span className="text-muted">
            Investi <b className="text-white">{formatEur(invested)}</b>
          </span>
          <span className="text-muted">
            Valeur <b className="text-white">{formatEur(value)}</b>
          </span>
          <span className="text-muted">
            P&amp;L{" "}
            <b className={gainColor}>
              {formatSignedEur(gain)} ({formatPct(gainPct)})
            </b>
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={refreshing || items.length === 0}
          className="flex h-8 items-center gap-1.5 rounded border border-line bg-bg px-3 text-xs font-semibold hover:border-brand disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Actualiser les cours
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line bg-bg/40">
              <th className={th}>Visuel</th>
              <th className={th}>Ticker</th>
              <th className={th}>Nom</th>
              <th className={th}>État</th>
              <th className={`${th} text-right`}>Prix d&apos;achat</th>
              <th className={`${th} text-right`}>Prix RAW actuel</th>
              <th className={`${th} text-right`}>Plus-value</th>
              <th className={`${th} text-right`}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-muted">
                  Portefeuille vide — ajoute une carte avec son ticker TCGdex (ex. <code>xy12-1</code>).
                </td>
              </tr>
            )}
            {items.map((i) => {
              const cur = i.price?.current ?? null;
              const g = cur != null ? cur - i.buyPrice : null;
              const gp = g != null && i.buyPrice > 0 ? (g / i.buyPrice) * 100 : null;
              const color = g == null ? "text-muted" : g > 0 ? "text-emerald-400" : g < 0 ? "text-red-400" : "text-muted";
              const active = i.uid === selectedUid;
              return (
                <tr
                  key={i.uid}
                  onClick={() => onSelect(i.uid)}
                  className={`cursor-pointer border-b border-line/60 last:border-0 hover:bg-white/[0.03] ${
                    active ? "bg-brand/10" : ""
                  }`}
                >
                  <td className="px-3 py-1.5">
                    {i.card.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={i.card.image.replace("/high.png", "/low.png")}
                        alt=""
                        width={34}
                        height={47}
                        loading="lazy"
                        className="h-[47px] w-[34px] rounded-sm object-cover"
                      />
                    ) : (
                      <div className="h-[47px] w-[34px] rounded-sm bg-bg" />
                    )}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs text-brand">{i.ticker}</td>
                  <td className="px-3 py-1.5">
                    <div className="font-medium">{i.card.name}</div>
                    <div className="text-xs text-muted">
                      {i.card.setName} · {i.card.rarity}
                    </div>
                    {errors[i.uid] && <div className="text-xs text-red-400">{errors[i.uid]}</div>}
                  </td>
                  <td className="px-3 py-1.5">
                    <ConditionBadge condition={i.condition} />
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{formatEur(i.buyPrice)}</td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums">{formatEur(cur)}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums ${color}`}>
                    {g == null ? (
                      "—"
                    ) : (
                      <>
                        {formatSignedEur(g)}
                        {gp != null && <div className="text-xs">{formatPct(gp)}</div>}
                      </>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <button
                      aria-label={`Supprimer ${i.card.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemove(i.uid);
                      }}
                      className="rounded p-1.5 text-muted hover:bg-red-500/10 hover:text-red-400"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
