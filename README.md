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

## Utiliser l'application

Double-cliquer sur **`lancer.bat`** (Windows). Le script crée l'environnement
Python au premier lancement, construit la base si elle est absente, puis ouvre
l'interface dans le navigateur.

Depuis un terminal, **PowerShell exige le préfixe `.\`** — il n'exécute jamais
un fichier du dossier courant sans lui, et répond « n'est pas reconnu » que le
fichier existe ou non : `.\lancer.bat`, `.\construire.bat`, `.\cotations.bat`.

Trois menus, choisis dans la barre latérale :

- **LISTE** — le tableau de la sélection. Sélectionner une ligne fait
  apparaître le support, une bascule pour le suivre et un bouton vers sa fiche.
  Quand des valeurs liquidatives existent, leurs performances remplacent celles
  tirées des exercices publiés plutôt que de s'y ajouter.
- **PERF** — six classements côte à côte : 1 an, 2 ans, exercice clos, année en
  cours, 3 mois, 6 mois. Douze supports par case au plus.
- **COMPARE** — jusqu'à huit trajectoires superposées, ramenées à 100 à leur
  départ commun, suivies des six horizons en clair.

Sélectionner une ligne de LISTE ouvre la **fiche** du support : risque,
rendement, frais, conditions comparées des deux assureurs, performance nette
annuelle, et — lorsque sa valeur liquidative a été collectée — ses six
performances de référence, sa trajectoire quotidienne ramenée à 100, sa perte
depuis chaque plus haut, sa volatilité annualisée et sa perte maximale.

Deux annexes en pied de barre latérale, **Frais** et **Qualité des données**,
recouvrent le menu courant sans le changer ; un bouton de retour ramène où l'on
était.

## Classe d'actif

Le filtre classe par **véhicule** — ce que le support est juridiquement — et
non par classe d'actif au sens Morningstar. Les deux lectures se croisent : un
ETF logé en assurance vie est un ETF *et* une unité de compte.

| Case | Règle | Univers |
|---|---|---|
| Fond UC | OPC offert par au moins un assureur | 1 077 |
| ETF | `type_instrument = etf` | 186 |
| Actions | `type_instrument = action` | 110 |
| FCPE | hors contrats, enveloppe commençant par `PEE` | 4 |
| SCPI | hors contrats, sans épargne salariale | 1 |
| Livret | — | 0 |

La classification est exhaustive et sans recouvrement : tout instrument tombe
dans exactement une case. **Livret** n'a encore aucun membre — aucun assureur
ne le publie et un livret n'a pas d'ISIN — mais la case figure quand même :
une catégorie absente se lit comme une catégorie qui n'existe pas.

Les autres filtres — recherche, favoris, SRI, frais, SFDR, présence d'un
historique — s'appliquent eux aussi aux trois menus. La classification
Morningstar reste en base et s'affiche sur la fiche.

Le détail de la conception est dans
[`docs/spec-tableau-de-bord.md`](docs/spec-tableau-de-bord.md).

## Valeurs liquidatives

Une observation, c'est un support, une date **et une convention** : la clôture
brute est le prix affiché ce jour-là, la clôture ajustée corrige les dividendes
détachés depuis. Sur un support distribuant l'écart dépasse 6 % et grandit avec
l'ancienneté ; les mélanger dans une même série fausserait toute performance
calculée entre deux de ses points. La clé de `valeur_liquidative` est donc
`(isin, date, base)`, et la vue `v_serie` choisit une seule convention par
support — la plus fournie, l'ajustée à égalité.

Double-cliquer sur **`cotations.bat`**, ou en ligne de commande :

| Commande | Effet |
|---|---|
| `.\cotations.bat` | Migre si besoin, charge les captures, puis **simule** l'import des relevés de `data/raw/vl/*.xlsx` |
| `.\cotations.bat --ecrire` | Écrit l'import |

N'appelez pas `python tools/…` directement : les dépendances vivent dans
`.venv`, et sous Windows 11 le nom `python` désigne un raccourci factice vers le
Microsoft Store. Les `.bat` résolvent l'interpréteur — `py -3`, `py`, `python`,
`python3`, chacun réellement exécuté — et réinstallent les dépendances quand la
liste a changé.

Un relevé ponctuel **ne remplace jamais** une valeur présente : il comble un
trou, et le recoupement devient un échantillon de contrôle. Il ne permet que la
performance de l'exercice clos — les fenêtres glissantes réclament une valeur du
jour qu'il ne porte pas.

Conception détaillée dans
[`docs/spec-valeurs-liquidatives.md`](docs/spec-valeurs-liquidatives.md).

## Favoris

Les supports suivis se basculent en sélectionnant leur ligne dans **LISTE**,
ou par la bascule en haut de leur **fiche**. Le filtre
« Favoris » de la barre latérale restreint l'affichage à la liste, ou l'en exclut.

Un support **détenu hors des deux contrats** — fonds de PEE, ETF logé en PEA,
part de SCPI — entre au référentiel comme instrument **sans offre rattachée** :
le schéma le permet, un instrument n'a pas besoin d'être offert pour exister. Il
apparaît dans la liste suivie, marqué « hors contrats », sans SRI ni frais ni
classification puisque aucun assureur ne les publie. Un support dépourvu d'ISIN
ne peut être rattaché à rien : il est signalé dans **Qualité des données** et
sous le filtre Favoris, plutôt que de disparaître en silence.

La liste vit dans **`data/favoris.csv`** — `isin`, `ajoute_le`, `note` —
modifiable dans un tableur. La note est libre et sert aujourd'hui à porter
l'enveloppe de détention ; elle s'affiche sur la fiche du support. Elle est
délibérément tenue **hors de la base** : `construire.bat` efface et reconstruit
`reference.db` à chaque exécution, une donnée saisie ne pourrait pas y survivre.

Ce CSV n'est **pas suivi par Git**, et pour la même raison qu'il vit hors de la
base : l'application l'écrit à chaque coche, or un fichier que le programme
modifie entre en conflit à chaque `git pull`. La semence, elle, est versionnée —
**`data/raw/favorites.txt`**, tenue à la main, colonnes `Fonds`, `ISIN`,
`Détenu dans` séparées par des tabulations. Quand le CSV manque, il en est
amorcé au premier lancement ; ensuite il vit sa vie en local. Une liste vidée à
la main laisse un fichier à en-tête seul : elle n'est pas ressuscitée.

Pour reprendre la semence après l'avoir modifiée, sans perdre les coches
ajoutées depuis : `python tools/importer_favoris.py`.

L'application est en lecture seule : elle n'écrit jamais dans la base.

## Construire la base seule

Double-cliquer sur **`construire.bat`**, qui reconstruit `data/reference.db` à
partir des fiches Markdown de `data/raw/md/`.

En ligne de commande :

```
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python tools\construire_base.py
.venv\Scripts\python -m streamlit run app\univers.py
```

`py -3` plutôt que `python` : sous Windows 11 ce dernier désigne un raccourci
factice vers le Microsoft Store.

La base est **reconstruite intégralement à chaque exécution** : elle n'est jamais
migrée, et n'est donc pas versionnée. Le chargement s'interrompt en erreur si
l'effectif chargé ne correspond pas à l'inventaire des ISIN des PDF d'origine.

## Schéma

Deux bases aux cycles de vie distincts, jointes au besoin par `ATTACH`.

`db/schema.sql` — **`reference.db`**, cinq tables et deux vues, reconstruite
intégralement à chaque exécution.

- **`instrument`** — référentiel par ISIN : ce qui ne dépend pas de l'assureur.
- **`offre`** — conditions d'accès chez un assureur : classification, frais,
  performances. Un même ISIN porte jusqu'à deux offres.
- **`performance_annuelle`** — historique de performance nette, année par année.
- **`import`** — traçabilité : document, empreinte SHA-256, millésime, date.
- **`anomalie`** — écarts relevés par les contrôles de chargement.
- **`v_univers`** — une ligne par instrument, les deux assureurs côte à côte.
- **`v_arbitrage`** — les fonds communs, classés par écart de frais, avec une
  colonne `fiabilite` (voir la réserve ci-dessous).

`db/schema_cotations.sql` — **`cotations.db`**, les valeurs liquidatives et le
journal des collectes. Elle est **accumulée, jamais effacée** : un historique
quotidien coûte des heures de collecte et ne se régénère pas depuis les
documents. Le chargement y est idempotent.

## Comment lire la performance

Le rendement affiché est **annualisé**, au sens géométrique, et net des frais du
fonds. La moyenne arithmétique des performances annuelles, plus simple mais
fausse, surestime le rendement réellement obtenu : de 0,60 point en médiane sur
cet univers, et jusqu'à **8,2 points** sur les fonds les plus volatils.

La couverture est inégale et l'application l'affiche :

| | Instruments |
|---|---|
| Rendement annualisé calculable | 767 |
| dont cinq exercices complets | 600 |
| Indicateur de risque (SRI) renseigné | 902 |

Le SRI vient des annexes SwissLife : les 470 supports présents uniquement chez
BoursoVie n'en portent pas, et forment un segment « non renseigné » à part
entière sur l'axe risque.

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
| `app/univers.py` | Interface de consultation, en lecture seule |
| `tools/construire_base.py` | Construit la base et exécute les contrôles |
| `tools/parse_boursorama_pdf.py` | Extrait les 631 supports du PDF BoursoVie |
| `tools/fiches_boursorama.py` | Gabarit de lecture et d'écriture des fiches |
| `tools/completer_boursorama.py` | Classe et insère des supports dans les fiches |
| `tools/generer_index_boursorama.py` | Régénère l'index et la comparaison SwissLife |
| `tools/importer_favoris.py` | Reprend `data/raw/favorites.txt` vers les favoris |
| `tools/capturer_sources.py` | Sonde les sources de valeur liquidative et archive leurs réponses |
| `tools/capturer_historiques.py` | Sonde les points d'accès d'historique |
| `tools/charger_cotations.py` | Charge les séries capturées dans `cotations.db` |
| `tools/valider_series.py` | Confronte les séries aux performances publiées |

## Suite

Enrichissement web : valeurs liquidatives quotidiennes, et surtout les **frais
courants du DIC**, seule grandeur normalisée réglementairement — c'est elle qui
permettra une comparaison de frais fonds par fonds, que les données des
assureurs ne rendent pas possible aujourd'hui. Puis suivi de portefeuille.

Le thème de l'interface est fixé en clair dans `.streamlit/config.toml` : les
couleurs des graphiques sont validées contre cette surface (séparation des
couleurs pour les daltonismes, contraste), un basculement automatique en sombre
les rendrait non conformes.
