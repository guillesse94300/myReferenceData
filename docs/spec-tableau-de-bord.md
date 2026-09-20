# Tableau de bord — spécification

Établie le 20 septembre 2026 à partir du croquis papier, et tenue à jour à
mesure que l'interface évolue.

## Ce que la page doit faire

Donner **l'état d'ensemble** : la photo des supports, pas une liste d'alertes.
Le catalogue de 1 378 instruments n'est plus le sujet — il est la toile de fond
que les filtres découpent.

Aucun montant n'est saisi : chaque support est traité à égalité. Il n'y a donc
ni valeur de portefeuille, ni performance pondérée. C'est un choix, pas une
lacune : rien à tenir à jour, et aucune somme d'argent sur le disque.

## Structure

```
┌────────────────┬─────────┬─────────┬───────────┐
│ date du jour   │  LISTE  │  PERF   │  COMPARE  │
│ version, source│         │         │           │
├────────────────┼─────────┴─────────┴───────────┤
│ Nom ou ISIN    │                               │
│ Favoris ○○○    │   contenu du menu courant     │
│ Classe d'actif │                               │
│  ☐ Fond UC     │                               │
│  ☐ ETF         │                               │
│  ☐ Actions     │                               │
│  ☐ FCPE        │                               │
│  ☐ SCPI        │                               │
│  ☐ Livret      │                               │
│ ▸ Autres       │                               │
│ n sur 1378     │                               │
│ [Frais]        │                               │
│ [Qualité]      │                               │
└────────────────┴───────────────────────────────┘
```

Les filtres s'appliquent aux trois menus. Frais et Qualité des données ont
leurs propres sélecteurs et ignorent la sélection ; elles recouvrent le menu
courant sans le changer, et un bouton de retour ramène où l'on était.

## L'axe « classe d'actif »

Les six cases classent par **véhicule** — ce que le support est juridiquement —
et non par classe d'actif au sens Morningstar. Les deux lectures se croisent :
un ETF logé en assurance vie est un ETF *et* une unité de compte.

| Case | Règle | Univers |
|---|---|---|
| Fond UC | OPC offert par au moins un assureur | 1 077 |
| ETF | `type_instrument = etf` | 186 |
| Actions | `type_instrument = action` | 110 |
| FCPE | hors contrats, enveloppe commençant par `PEE` | 4 |
| SCPI | hors contrats, sans épargne salariale | 1 |
| Livret | — | 0 |

La classification est **exhaustive et sans recouvrement** : tout instrument
tombe dans exactement une case, ce que les tests vérifient sur les 1 378 lignes.

Deux écarts au croquis, assumés :

- **SCPI** est une sixième case, absente du croquis. Sans elle, la part June
  Opportunity — détenue — ne tomberait nulle part et disparaîtrait de
  l'application. Une classification qui perd un support détenu est fausse.
- **Livret** n'a aucun membre. Aucun assureur ne le publie, un livret n'a pas
  d'ISIN, et son rendement est un taux connu d'avance. La case figure quand
  même : une catégorie absente se lit comme une catégorie qui n'existe pas, et
  celle-ci existe. L'y faire entrer demanderait une source saisie à la main.

## LISTE

Tableau de la sélection. Sélectionner une ligne fait apparaître le support
choisi, une bascule **Suivi** et un bouton vers sa **fiche**.

`Détenu dans` remplace `Disponible` seulement quand **tous** les supports
affichés sont détenus. Sinon la colonne serait vide sur l'essentiel des lignes
et chasserait une information qui, elle, y est.

Quand des valeurs liquidatives existent, les colonnes de performance issues des
exercices publiés leur cèdent la place plutôt que de s'y ajouter — plus fines,
plus récentes, et le tableau garde un nombre de colonnes lisible.

## PERF

Six classements côte à côte, dans l'ordre du croquis :

| | | |
|---|---|---|
| 1 an | 2 ans | exercice clos |
| année en cours | 3 mois | 6 mois |

Douze supports par case au plus ; au-delà, le nombre total est indiqué.

Le millésime de l'exercice clos est **lu dans les séries**, non écrit en dur :
la grille se figerait sinon sur 2025.

**La grille est bâtie sur les seules séries de valeurs liquidatives.** Les
performances annuelles publiées par les assureurs couvriraient bien plus de
supports sur la case de l'exercice clos, mais elles obéissent à une autre
définition — exercice civil, en euro, nette des frais du fonds. Les mélanger
rendrait cette case incomparable à ses cinq voisines, ce qui est précisément ce
que la grille sert à faire.

Aujourd'hui **14 supports sur 1 378** ont un historique. Le chiffre est affiché
en tête de page plutôt que sous-entendu.

## COMPARE

Sélection à gauche, trajectoires superposées à droite, ramenées à 100 à leur
**départ commun** — la première séance où tous les supports retenus cotent,
sans quoi une série plus courte partirait avec un avantage qu'elle n'a pas.

Huit supports au maximum : c'est la longueur de la palette catégorielle, et
au-delà les courbes ne se distinguent plus.

Sous le graphique, les six horizons des supports retenus en clair. Ce n'est pas
une redite : trois teintes de la palette passent sous 3:1 de contraste, et
l'identité ne peut donc pas reposer sur la couleur seule.

## Couleurs

Palette catégorielle de huit teintes, ordre fixe, jamais cyclé, validée contre
la surface `#fcfcfb` — bande de clarté, plancher de chroma, séparation
daltonienne et vision normale sur les paires adjacentes.

```
#2a78d6  #eb6834  #1baf7a  #eda100  #e87ba4  #008300  #4a3aa7  #e34948
```

Pour le signe d'une performance, paire divergente bleu/rouge : la polarité est
le signe, jamais le rang.

## Pièges rencontrés

**Une règle verticale layerée sur une échelle de bande casse le rendu Vega.**
La couche du zéro doit porter explicitement la même échelle que les barres,
sinon Vega abandonne le rendu du graphique entier — silencieusement, la page
restant simplement vide. Même effet avec un tri `-x` dont le champ manque à
l'une des couches.
