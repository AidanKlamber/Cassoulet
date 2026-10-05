const eur = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });
const pct = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, signDisplay: "exceptZero" });

export const formatEur = (v: number | null | undefined) =>
  v == null || Number.isNaN(v) ? "—" : eur.format(v);

export const formatSignedEur = (v: number) =>
  `${v > 0 ? "+" : ""}${eur.format(v)}`;

export const formatPct = (v: number) => `${pct.format(v)} %`;
