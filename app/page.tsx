"use client";

import { useState } from "react";
import { AddForm } from "@/components/AddForm";
import { CardHero } from "@/components/CardHero";
import { Header } from "@/components/Header";
import { PortfolioTable } from "@/components/PortfolioTable";
import { usePortfolio } from "@/lib/usePortfolio";

export default function Home() {
  const { items, ready, refreshing, errors, add, remove, refresh } = usePortfolio();
  const [selected, setSelected] = useState<string | null>(null);

  const current = items.find((i) => i.uid === selected) ?? items[0] ?? null;

  return (
    <>
      <Header />
      <main className="mx-auto flex max-w-[1400px] flex-col gap-4 px-4 py-4">
        <AddForm
          onAdd={async (t, c, p) => {
            const item = await add(t, c, p);
            setSelected(item.uid);
          }}
        />
        {current && <CardHero item={current} />}
        {ready && (
          <PortfolioTable
            items={items}
            selectedUid={current?.uid ?? null}
            errors={errors}
            refreshing={refreshing}
            onSelect={setSelected}
            onRemove={remove}
            onRefresh={refresh}
          />
        )}
      </main>
    </>
  );
}
