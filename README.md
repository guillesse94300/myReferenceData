# myReferenceData

Univers d'investissement des contrats d'assurance-vie **SwissLife** et **BoursoVie**,
décrit, classifié et interrogeable en local.

## État actuel

| | |
|---|---|
| Instruments | **1 372** — 1 077 OPC, 185 ETF, 110 actions en direct |
| Offres (instrument × assureur) | 1 533 — 902 SwissLife, 631 BoursoVie |
| Disponibles chez les deux | 161 |
| Historiques de performance annuelle | 3 393 points, 2021 à 2025 |

Sources : annexes des deux assureurs, juin 2026 pour SwissLife et septembre 2026
pour BoursoVie, dans `data/raw/`. Le périmètre couvre les OPC et les ETF ; les
titres vifs de l'annexe IB SwissLife servent de référentiel (pays, notation) mais
ne constituent pas des offres.

## Construire la base

Double-cliquer sur **`construire.bat`** (Windows). Le script crée l'environnement
Python au premier lancement, puis reconstruit `data/reference.db` à partir des
fiches Markdown de `data/raw/md/`.

En ligne de commande :

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python tools\construire_base.py
```

La base est **reconstruite intégralement à chaque exécution** : elle n'est jamais
migrée, et n'est donc pas versionnée. Le chargement s'interrompt en erreur si
l'effectif chargé ne correspond pas à l'inventaire des ISIN des PDF d'origine.

## Schéma

`db/schema.sql` — cinq tables et deux vues.

- **`instrument`** — référentiel par ISIN : ce qui ne dépend pas de l'assureur.
- **`offre`** — conditions d'accès chez un assureur : classification, frais,
  performances. Un même ISIN porte jusqu'à deux offres.
- **`performance_annuelle`** — historique de performance nette, année par année.
- **`import`** — traçabilité : document, empreinte SHA-256, millésime, date.
- **`anomalie`** — écarts relevés par les contrôles de chargement.
- **`v_univers`** — une ligne par instrument, les deux assureurs côte à côte.
- **`v_arbitrage`** — les fonds communs, classés par écart de frais, avec une
  colonne `fiabilite` (voir la réserve ci-dessous).

## Réserve importante sur la comparaison de frais

Les deux assureurs ne publient pas la même grandeur.

Les **frais de contrat** sont comparables et connus : 0,96 % chez SwissLife,
0,75 % chez BoursoVie, soit un avantage structurel de 0,21 point pour BoursoVie.

Les **frais du fonds** ne le sont pas. Sur les 161 fonds communs, **139 affichent
une valeur différente selon l'assureur** alors qu'il s'agit du même fonds :
SwissLife paraît publier les charges réellement supportées sur le dernier
exercice, BoursoVie les frais contractuels. Dix offres BoursoVie affichent même
0 %, ce qui traduit une donnée non communiquée publiée comme un zéro.

La vue `v_arbitrage` porte donc une colonne `fiabilite` :

| `fiabilite` | Fonds | Lecture |
|---|---|---|
| `comparable` | 22 | Écart exploitable |
| `définitions divergentes` | 136 | Mélange un écart tarifaire et une différence de définition |
| `frais du fonds nuls chez BoursoVie` | 3 | Donnée manquante, à écarter |

Sur les 22 lignes comparables, BoursoVie est moins cher dans **22 cas sur 22**, de
0,21 à 0,26 point — c'est-à-dire l'écart structurel de frais de contrat, et rien
d'autre. Tout écart nettement supérieur affiché ailleurs relève de la définition,
pas du tarif.

## Fiabilité de la classification

La taxonomie est celle de SwissLife (84 catégories). BoursoVie ne classant rien,
la classification de ses supports est reconstituée, et le champ
`origine_classification` dit toujours comment :

| Origine | Supports | Fiabilité |
|---|---|---|
| Taxonomie SwissLife | 902 | Native |
| Annexe IA SwissLife, par ISIN | 148 | Fiable |
| Annexe IB SwissLife, par ISIN | 109 | Fiable |
| Déduite du libellé | 373 | 88 % d'exactitude mesurée |
| Non déterminée | 1 | — |

## Outils

| Fichier | Rôle |
|---|---|
| `tools/construire_base.py` | Construit la base et exécute les contrôles |
| `tools/parse_boursorama_pdf.py` | Extrait les 631 supports du PDF BoursoVie |
| `tools/fiches_boursorama.py` | Gabarit de lecture et d'écriture des fiches |
| `tools/completer_boursorama.py` | Classe et insère des supports dans les fiches |
| `tools/generer_index_boursorama.py` | Régénère l'index et la comparaison SwissLife |

## Suite

Enrichissement web (valeurs liquidatives, DIC), interface de filtrage, suivi de
portefeuille.
