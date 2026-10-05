import type { Condition } from "./types";

export const CONDITIONS: Condition[] = ["MT", "NM", "EX", "GD", "LP", "PL", "PO"];

/** Couleurs des badges (NM et EX imposés par le cahier des charges). */
export const CONDITION_COLORS: Record<Condition, string> = {
  MT: "#059669",
  NM: "#10b981",
  EX: "#84cc16",
  GD: "#eab308",
  LP: "#f59e0b",
  PL: "#f97316",
  PO: "#ef4444",
};

export const CONDITION_LABELS: Record<Condition, string> = {
  MT: "Mint",
  NM: "Near Mint",
  EX: "Excellent",
  GD: "Good",
  LP: "Light Played",
  PL: "Played",
  PO: "Poor",
};

/** Correspondance échelle Cardmarket -> échelle Scrydex (NM/LP/MP/HP/DM). */
export const SCRYDEX_CONDITION: Record<Condition, string> = {
  MT: "NM",
  NM: "NM",
  EX: "LP",
  GD: "MP",
  LP: "MP",
  PL: "HP",
  PO: "DM",
};
