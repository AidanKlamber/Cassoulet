"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { CONDITIONS } from "@/lib/conditions";
import type { Condition } from "@/lib/types";

interface Props {
  onAdd: (ticker: string, condition: Condition, buyPrice: number) => Promise<unknown>;
}

const field =
  "h-9 rounded border border-line bg-bg px-2.5 text-sm text-white placeholder:text-muted focus:border-brand focus:outline-none";

export function AddForm({ onAdd }: Props) {
  const [ticker, setTicker] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [condition, setCondition] = useState<Condition>("NM");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const price = Number(buyPrice.replace(",", "."));
    if (!ticker.trim()) return setError("Saisis un ticker TCGdex, ex. xy12-1");
    if (!Number.isFinite(price) || price < 0) return setError("Prix d'achat invalide");
    setBusy(true);
    setError(null);
    try {
      await onAdd(ticker, condition, price);
      setTicker("");
      setBuyPrice("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded border border-line bg-panel p-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted">
          Ticker TCGdex
          <input
            className={`${field} w-40`}
            placeholder="xy12-1"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            autoCapitalize="off"
            spellCheck={false}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          Prix d&apos;achat (€)
          <input
            className={`${field} w-32`}
            placeholder="12,50"
            inputMode="decimal"
            value={buyPrice}
            onChange={(e) => setBuyPrice(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          État
          <select
            className={`${field} w-24`}
            value={condition}
            onChange={(e) => setCondition(e.target.value as Condition)}
          >
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={busy}
          className="flex h-9 items-center gap-1.5 rounded bg-brand px-4 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-60"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Ajouter
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </form>
  );
}
