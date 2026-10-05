import { Layers } from "lucide-react";

export function Header() {
  return (
    <header className="border-b border-line bg-panel">
      <div className="mx-auto flex h-12 max-w-[1400px] items-center gap-3 px-4">
        <Layers className="h-5 w-5 text-brand" />
        <span className="text-base font-bold tracking-tight">
          Cassoulet<span className="text-brand">.</span>
        </span>
        <span className="hidden text-xs text-muted sm:inline">Portefeuille Pokémon · prix RAW en EUR</span>
      </div>
    </header>
  );
}
