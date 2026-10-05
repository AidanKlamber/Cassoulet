# Jumeau numérique – Olympiades FANUC AVP BAC+2 2027 (projet DP27-01)

Génération automatique du rapport d'analyse et de dimensionnement à partir de l'archive du sujet.

## Utilisation

```bash
pip install -r requirements.txt
python generate_rapport.py --zip "Jumeau_Numérique_Olympiades_Fanuc_AVP_BAC2_2027.zip" \
                           --out Rapport_AVP_Jumeau_Numerique_FANUC_2027.pdf
```

Option : `--workdir DOSSIER` pour conserver l'archive extraite, les visuels et les graphiques intermédiaires.

## Contenu

| Fichier | Rôle |
|---|---|
| `generate_rapport.py` | Point d'entrée : assemble le PDF (reportlab) – couverture, sommaire, en-tête/pied « X / Y », tableaux, encadrés, figures légendées |
| `fanuc_calculs.py` | Tous les calculs (takt, implantation et portée, choix du robot, temps de cycle, ventouses, pesée, communication). Le texte du rapport est alimenté par ces valeurs |
| `rapport_figures.py` | Extraction des visuels de l'archive (plans PDF, figures du CDC, carte mentale, catalogue, fiche ressources) et graphiques matplotlib |
| `Rapport_AVP_Jumeau_Numerique_FANUC_2027.pdf` | Rapport généré (22 pages) |

Les trois modules doivent rester dans le même dossier.

## Hypothèses

Les hypothèses non issues du dossier sont repérées « HYP » dans le rapport (annexe A) et regroupées dans
`fanuc_calculs.py` (`INPUT`, `CYC`, fonctions `calc_*`). Le temps de cycle est un modèle analytique : il ne remplace
pas la simulation ROBOGUIDE.
