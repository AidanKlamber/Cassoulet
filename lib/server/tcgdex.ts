import type { CardInfo, PriceData } from "../types";

const BASE = process.env.TCGDEX_API_BASE ?? "https://api.tcgdex.net/v2/fr";

type CmPricing = Record<string, number | string | null | undefined>;

interface TcgdexCard {
  id: string;
  localId: string;
  name: string;
  image?: string;
  rarity?: string;
  set?: { id: string; name: string };
  variants?: { normal?: boolean; reverse?: boolean; holo?: boolean; firstEdition?: boolean };
  pricing?: { cardmarket?: CmPricing | null };
}

export class CardNotFoundError extends Error {}

export async function fetchTcgdexCard(ticker: string): Promise<TcgdexCard> {
  const res = await fetch(`${BASE}/cards/${encodeURIComponent(ticker)}`, {
    next: { revalidate: 300 },
  });
  if (res.status === 404) throw new CardNotFoundError(`Carte « ${ticker} » introuvable sur TCGdex`);
  if (!res.ok) throw new Error(`TCGdex a répondu ${res.status}`);
  // TCGdex renvoie parfois 200 avec un corps vide / non-JSON pour un ID inconnu.
  const json = await res.json().catch(() => null);
  if (!json || !json.id) throw new CardNotFoundError(`Carte « ${ticker} » introuvable sur TCGdex`);
  return json as TcgdexCard;
}

export function toCardInfo(c: TcgdexCard): CardInfo {
  return {
    id: c.id,
    name: c.name,
    rarity: c.rarity ?? "—",
    setName: c.set?.name ?? c.id.split("-")[0],
    setId: c.set?.id ?? c.id.split("-")[0],
    number: c.localId,
    image: c.image ? `${c.image}/high.png` : null,
  };
}

const num = (v: unknown): number | null => {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
};

/**
 * Prix Cardmarket (EUR) exposés par TCGdex. Pour les cartes uniquement holo,
 * seules les clés `*-holo` sont renseignées : on choisit la variante la plus
 * pertinente, puis on se replie sur l'autre si les valeurs sont vides.
 */
export function toCardmarketPrice(c: TcgdexCard): PriceData | null {
  const cm = c.pricing?.cardmarket;
  if (!cm) return null;

  const read = (suffix: "" | "-holo") => ({
    avg1: num(cm[`avg1${suffix}`]),
    avg7: num(cm[`avg7${suffix}`]),
    avg30: num(cm[`avg30${suffix}`]),
    trend: num(cm[`trend${suffix}`]),
    low: num(cm[`low${suffix}`]),
    avg: num(cm[`avg${suffix}`]),
  });

  const normal = read("");
  const holo = read("-holo");
  const holoOnly = c.variants?.holo === true && c.variants.normal === false;
  const [first, second] = holoOnly ? [holo, normal] : [normal, holo];
  const v = first.trend || first.avg30 || first.avg ? first : second;

  const current = v.trend ?? v.avg7 ?? v.avg30 ?? v.avg ?? v.low;
  if (current == null) return null;

  const history = (
    [
      ["Moy. 30 j", v.avg30],
      ["Moy. 7 j", v.avg7],
      ["Moy. 1 j", v.avg1],
      ["Tendance", v.trend],
    ] as [string, number | null][]
  )
    .filter((p): p is [string, number] => p[1] != null)
    .map(([label, price]) => ({ label, price }));

  return {
    source: "cardmarket",
    currency: "EUR",
    current,
    avg1: v.avg1,
    avg7: v.avg7,
    avg30: v.avg30,
    trend: v.trend,
    low: v.low,
    history,
    historyKind: "averages",
    updatedAt: typeof cm.updated === "string" ? cm.updated : new Date().toISOString(),
  };
}
