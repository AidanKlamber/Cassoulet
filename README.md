# Cassoulet — Portefeuille Pokémon

Suivi d'investissements de cartes Pokémon, style Cardmarket sombre.
Next.js 15 (App Router) · Tailwind CSS 3 · Recharts · Lucide.

```bash
npm install
npm run dev     # http://localhost:3000
```

Saisis un **ticker TCGdex** (`<extension>-<numéro>`, ex. `xy12-1` = Florizarre EX, XY Évolutions ;
`swsh1-1`, `sv03.5-199`…), ton prix d'achat et l'état (MT/NM/EX/GD/LP/PL/PO).
Le portefeuille est mémorisé dans le `localStorage` du navigateur.

## Sources de données

| Donnée | Source | Clé requise |
|---|---|---|
| Image HD, nom, rareté, extension, n° (FR) | [TCGdex](https://tcgdex.dev) | non |
| Prix RAW en EUR, moyennes 1 j / 7 j / 30 j, tendance | **Cardmarket**, exposé par TCGdex (`pricing.cardmarket`) | non |
| Prix RAW par état + historique quotidien | [Scrydex](https://scrydex.com/docs) (**optionnel, payant**) | oui |

Les appels partent du serveur Next (`/api/card/[id]`) : pas de CORS, et les clés Scrydex
ne sont jamais envoyées au navigateur.

- **Par défaut (sans clé)** : prix Cardmarket en EUR. TCGdex ne fournit pas de série
  temporelle, donc la courbe montre les moyennes 30 j → 7 j → 1 j → tendance (indiqué dans l'UI).
- **Avec Scrydex** : copie `.env.example` en `.env.local` et renseigne `SCRYDEX_API_KEY` et
  `SCRYDEX_TEAM_ID`. La courbe devient un historique quotidien 30 j, et le prix correspond
  à l'état de la carte. Les prix Scrydex étant en USD, ils sont convertis en EUR (taux
  frankfurter.dev, taux de secours signalé dans l'UI). En cas d'erreur Scrydex, l'app se
  replie sur Cardmarket et affiche un avertissement.

> ⚠ Le schéma Scrydex (`/cards/{id}?include=prices`, `/cards/{id}/price_history`) a été écrit
> d'après la doc publique et testé uniquement contre un faux serveur : à valider avec une
> vraie clé (`lib/server/scrydex.ts`).

Le prix Cardmarket n'est pas ajusté selon l'état de la carte (référence NM) : pour une carte
EX/GD, la plus-value affichée est donc optimiste sans Scrydex.
