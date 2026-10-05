import { SCRYDEX_CONDITION } from "../conditions";
import type { Condition, PriceData, PricePoint } from "../types";

const BASE = process.env.SCRYDEX_API_BASE ?? "https://api.scrydex.com/pokemon/v1";
const FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR";
const FALLBACK_USD_EUR = 0.92;

export const scrydexEnabled = () =>
  Boolean(process.env.SCRYDEX_API_KEY && process.env.SCRYDEX_TEAM_ID);

const headers = () => ({
  "X-Api-Key": process.env.SCRYDEX_API_KEY ?? "",
  "X-Team-ID": process.env.SCRYDEX_TEAM_ID ?? "",
  Accept: "application/json",
});

async function get(path: string) {
  const res = await fetch(`${BASE}${path}`, { headers: headers(), next: { revalidate: 900 } });
  if (!res.ok) throw new Error(`Scrydex a répondu ${res.status} sur ${path.split("?")[0]}`);
  return res.json();
}

async function usdToEur(): Promise<{ rate: number; fallback: boolean }> {
  try {
    const res = await fetch(FX_URL, { next: { revalidate: 6 * 3600 } });
    const j = await res.json();
    const r = j?.rates?.EUR;
    if (typeof r === "number" && r > 0) return { rate: r, fallback: false };
  } catch {
    /* repli ci-dessous */
  }
  return { rate: FALLBACK_USD_EUR, fallback: true };
}

interface ScrydexPrice {
  condition?: string;
  type?: string;
  market?: number;
  low?: number;
  currency?: string;
  is_perfect?: boolean;
  is_signed?: boolean;
  is_error?: boolean;
}
interface ScrydexVariant {
  name?: string;
  prices?: ScrydexPrice[];
}

/** Prix RAW (non gradé, ni signé / erreur) pour l'état demandé. */
function pickRaw(variants: ScrydexVariant[] | undefined, cond: string): ScrydexPrice | null {
  const candidates: ScrydexPrice[] = [];
  for (const v of variants ?? []) {
    for (const p of v.prices ?? []) {
      if (p.type && p.type !== "raw") continue;
      if (p.is_signed || p.is_error || p.is_perfect) continue;
      if (p.condition === cond && typeof p.market === "number") candidates.push(p);
    }
  }
  // Plusieurs variantes (normal / holo…) : on retient la plus chère = la variante principale.
  candidates.sort((a, b) => (b.market ?? 0) - (a.market ?? 0));
  return candidates[0] ?? null;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

/**
 * Prix RAW + historique depuis Scrydex.
 * ⚠ Le schéma a été écrit d'après la documentation publique sans pouvoir être
 * testé en direct : tout champ inattendu lève une erreur, et l'appelant se
 * replie alors sur Cardmarket.
 */
export async function fetchScrydexPrice(ticker: string, condition: Condition): Promise<PriceData> {
  const cond = SCRYDEX_CONDITION[condition];
  const id = encodeURIComponent(ticker);
  const [cardJson, histJson] = await Promise.all([
    get(`/cards/${id}?include=prices`),
    get(`/cards/${id}/price_history?days=30`).catch(() => null),
  ]);

  const raw = pickRaw(cardJson?.data?.variants, cond);
  if (!raw || raw.market == null) throw new Error(`Aucun prix RAW ${cond} chez Scrydex pour ${ticker}`);

  const fx = (raw.currency ?? "USD") === "EUR" ? { rate: 1, fallback: false } : await usdToEur();
  const rate = fx.rate;
  const toEur = (n: number) => round2(n * rate);

  const history: PricePoint[] = [];
  for (const day of (histJson?.data as { date?: string; variants?: ScrydexVariant[] }[]) ?? []) {
    const p = day.date ? pickRaw(day.variants, cond) : null;
    if (p?.market != null && day.date) history.push({ label: day.date, price: toEur(p.market) });
  }
  history.sort((a, b) => a.label.localeCompare(b.label));

  const current = toEur(raw.market);
  const avgOver = (days: number) => {
    const cutoff = Date.now() - days * 86_400_000;
    const pts = history.filter((h) => Date.parse(h.label) >= cutoff);
    return pts.length ? round2(pts.reduce((s, p) => s + p.price, 0) / pts.length) : null;
  };

  return {
    source: "scrydex",
    currency: "EUR",
    current,
    avg1: avgOver(1) ?? (history.length ? history[history.length - 1].price : null),
    avg7: avgOver(7),
    avg30: avgOver(30),
    trend: current,
    low: raw.low != null ? toEur(raw.low) : null,
    history,
    historyKind: "daily",
    updatedAt: new Date().toISOString(),
    warning: fx.fallback
      ? `Taux USD→EUR indisponible : taux de secours ${FALLBACK_USD_EUR} appliqué.`
      : undefined,
  };
}
