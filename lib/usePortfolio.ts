"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CardResponse, Condition, PortfolioItem } from "./types";

const KEY = "cassoulet.portfolio.v1";

export async function fetchCard(ticker: string, condition: Condition): Promise<CardResponse> {
  const res = await fetch(`/api/card/${encodeURIComponent(ticker)}?condition=${condition}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error ?? `Erreur ${res.status}`);
  return body as CardResponse;
}

export function usePortfolio() {
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [ready, setReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {
      /* stockage indisponible ou corrompu : on repart d'un portefeuille vide */
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch {
      /* quota dépassé / navigation privée */
    }
  }, [items, ready]);

  const add = useCallback(async (ticker: string, condition: Condition, buyPrice: number) => {
    const clean = ticker.trim().toLowerCase();
    const { card, price } = await fetchCard(clean, condition);
    const item: PortfolioItem = {
      uid: crypto.randomUUID(),
      ticker: card.id,
      condition,
      buyPrice,
      addedAt: new Date().toISOString(),
      card,
      price,
    };
    setItems((prev) => [item, ...prev]);
    return item;
  }, []);

  const remove = useCallback((uid: string) => {
    setItems((prev) => prev.filter((i) => i.uid !== uid));
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setErrors({});
    const queue = [...itemsRef.current];
    const worker = async () => {
      for (let it = queue.shift(); it; it = queue.shift()) {
        try {
          const { card, price } = await fetchCard(it.ticker, it.condition);
          setItems((prev) => prev.map((p) => (p.uid === it.uid ? { ...p, card, price } : p)));
        } catch (e) {
          setErrors((prev) => ({ ...prev, [it.uid]: (e as Error).message }));
        }
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    setRefreshing(false);
  }, []);

  return { items, ready, refreshing, errors, add, remove, refresh };
}
