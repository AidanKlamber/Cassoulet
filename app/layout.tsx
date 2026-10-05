import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cassoulet — Portefeuille Pokémon",
  description: "Suivi d'investissements et de portefeuille de cartes Pokémon",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
