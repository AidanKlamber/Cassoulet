export type Condition = "MT" | "NM" | "EX" | "GD" | "LP" | "PL" | "PO";

export type PriceSource = "cardmarket" | "scrydex";

export interface CardInfo {
  id: string;
  name: string;
  rarity: string;
  setName: string;
  setId: string;
  number: string;
  /** URL absolue de l'image haute définition */
  image: string | null;
}

export interface PricePoint {
  /** Étiquette de l'axe X (date ISO ou libellé de moyenne) */
  label: string;
  price: number;
}

export interface PriceData {
  source: PriceSource;
  currency: "EUR";
  /** Prix RAW courant (EUR) */
  current: number | null;
  avg1: number | null;
  avg7: number | null;
  avg30: number | null;
  trend: number | null;
  low: number | null;
  /** Courbe : série datée (Scrydex) ou moyennes 30j/7j/1j/tendance (Cardmarket) */
  history: PricePoint[];
  historyKind: "daily" | "averages";
  updatedAt: string;
  /** Avertissement non bloquant (ex. Scrydex en échec, repli Cardmarket) */
  warning?: string;
}

export interface CardResponse {
  card: CardInfo;
  price: PriceData;
}

export interface PortfolioItem {
  uid: string;
  ticker: string;
  condition: Condition;
  buyPrice: number;
  addedAt: string;
  card: CardInfo;
  price: PriceData | null;
}
