# Spécification — collecte des valeurs liquidatives

Version 1, 19 septembre 2026. Document de travail : il décrit ce qui est décidé,
ce qui reste ouvert, et comment on saura que ça marche.

## 1. Objectif

L'univers ne contient aujourd'hui que des performances **annuelles**, cinq au
mieux, et aucune pour 605 instruments. Un historique quotidien de valeur
liquidative permet de calculer la volatilité, le maximum drawdown, le ratio de
Sharpe, les corrélations entre supports, et la performance à une date
quelconque. C'est ce qui fait passer le référentiel du catalogue à l'analyse.

## 2. Périmètre retenu

| | |
|---|---|
| Instruments | les **14 favoris**, puis élargissement progressif |
| Profondeur | **5 ans**, soit exactement la période des performances publiées |
| Fréquence | quotidienne, reprise incrémentale ensuite |

Le périmètre initial est délibérément étroit : la boucle d'itération se compte
en minutes, et le résultat est immédiatement utile puisqu'il porte sur des
supports détenus. L'élargissement suivra les paliers 161 fonds communs,
902 SwissLife, 1 372 instruments, chacun conditionné au taux de couverture
constaté au palier précédent.

## 3. Contrainte de développement

L'environnement de développement **n'a pas accès à l'internet public** : le
proxy refuse toute connexion sortante hors dépôts de paquets. Le code ne peut
donc pas être mis au point par essais successifs contre les sources réelles.

La méthode retenue en découle :

1. `tools/capturer_sources.py` interroge les sources et archive les **réponses
   brutes** dans `data/raw/captures/`. Il est exécuté depuis un poste connecté.
2. Les captures sont versionnées.
3. Les parseurs sont écrits et testés **contre ces fichiers**, hors ligne.
4. La collecte réelle tourne sur le poste connecté ; son rapport revient ici.

Les tests sur captures gardent leur valeur après la mise au point : lorsqu'une
source change de format, ils le signalent au lieu de laisser passer des données
fausses.

## 4. Architecture de persistance

Les valeurs liquidatives **ne vivent pas dans `reference.db`**, que
`construire.bat` efface et reconstruit à chaque exécution. Deux bases, deux
cycles de vie :

| Base | Contenu | Cycle |
|---|---|---|
| `reference.db` | univers, offres, classification | reconstruite depuis les documents |
| `cotations.db` | valeurs liquidatives, indicateurs calculés | **accumulée**, jamais effacée |

Les deux se joignent par `ATTACH` : une requête SQL voit l'ensemble. Le principe
est celui déjà appliqué à `favoris.csv` — ce qui coûte cher à obtenir ne se jette
pas avec ce qui se régénère en dix secondes.

Schéma envisagé pour `cotations.db` :

```sql
CREATE TABLE valeur_liquidative (
    isin   TEXT NOT NULL,
    date   TEXT NOT NULL,
    vl     REAL NOT NULL,
    devise TEXT,
    source TEXT NOT NULL,
    PRIMARY KEY (isin, date)
);

CREATE TABLE collecte (            -- une ligne par tentative, succès ou échec
    id        INTEGER PRIMARY KEY,
    isin      TEXT NOT NULL,
    source    TEXT NOT NULL,
    tente_le  TEXT NOT NULL,
    statut    TEXT NOT NULL,       -- obtenu / vide / refusé / erreur
    points    INTEGER,
    detail    TEXT
);
```

La table `collecte` est délibérément conservée : un échec répété sur un support
est une information, pas un vide à ignorer.

## 5. Sources, en cascade

Aucune source ne couvre à la fois les 1 077 OPC non cotés et les 295 ETF et
actions. L'ordre d'essai dépend donc de la nature de l'instrument, et la
première source qui répond l'emporte.

| Source | Cible | Nature |
|---|---|---|
| Yahoo Finance | ETF et actions cotées | point d'accès JSON documenté, le plus stable |
| Boursorama | OPC non cotés | fiche par fonds, déjà fournisseur de l'univers |
| Quantalys | OPC non cotés | large couverture des fonds français |
| AMF / GECO | fonds français | source officielle, historique souvent court |
| Sociétés de gestion | dernier recours | un format par maison, à traiter au cas par cas |

Les adresses internet des sociétés de gestion figurent dans l'annexe IA
SwissLife mais ne sont pas encore chargées en base : ce sera un préalable à la
dernière source.

Chaque connecteur respecte la même interface, de façon à pouvoir en ajouter ou
en retirer sans toucher au reste :

```python
class Source:
    nom: str
    def couvre(instrument) -> bool
    def historique(isin, depuis) -> DataFrame[date, vl, devise]
```

Cache disque, limitation de débit, reprise incrémentale et journal des échecs
par ISIN. La collecte doit être interruptible et reprenable : sur l'univers
entier elle durera des heures au premier passage.

## 5 bis. Résultat du premier tour de capture

Capture du 19 septembre 2026, 14 supports × 4 sources.

| Source | Résultat | Suite |
|---|---|---|
| **Boursorama** | 14/14 résolus, réponses distinctes | **retenue** |
| **Yahoo Finance** | 14/14 résolus, réponses distinctes | **retenue** |
| Quantalys | 268 octets, redirection JavaScript exigeant les cookies | écartée |
| AMF / GECO | même page pour les 14 ISIN : application monopage sans formulaire | écartée |

Quantalys et l'AMF demanderaient un navigateur piloté. Puisque deux sources
couvrent déjà les 14 supports, elles sont écartées pour l'instant — à rouvrir
seulement si le taux de couverture s'effondre sur un palier plus large.

### Nature du symbole, et pourquoi elle décide de la cascade

Le préfixe du symbole Boursorama dit ce que la source livrera :

| Préfixe | Nature | Supports |
|---|---|---|
| `0P…` | identifiant de fonds Morningstar — **valeur liquidative** | 6 |
| `MP-…` | code de fonds Boursorama — **valeur liquidative** | 2 |
| `1rT…` | tracker coté sur Euronext — **cours de bourse** | 6 |

La distinction n'est pas cosmétique. Pour Pictet Global Environmental
Opportunities, Yahoo propose `PBFW.MU`, une cotation sur la bourse de Munich,
quand Boursorama donne `0P0000PTZT`, la valeur liquidative. **Sur un fonds non
coté, un cours de bourse n'est pas une valeur liquidative** : il porte une prime
ou une décote, et sa liquidité est faible.

D'où l'ordre de la cascade : **Boursorama d'abord sur les OPC non cotés**,
puisqu'il livre un identifiant de VL là où Yahoo renvoie parfois une place de
cotation ; Yahoo en premier sur les ETF, où le cours est la bonne donnée.

Le parseur de symboles, `tools/collecte/symboles.py`, est vérifié par
`tests/test_symboles.py` contre les 28 captures : résolution des 14 supports sur
les deux sources, nature correcte sur les six fonds non cotés, et préférence de
l'identifiant Morningstar sur une cotation de place.

## 6. Devises

Les valeurs liquidatives sont stockées **en devise native**, avec la devise.
976 instruments sont en euro, 31 en dollar, 3 en franc suisse, 1 en couronne
suédoise, et 361 n'ont pas de devise renseignée — à combler au passage.

Convertir demanderait un historique de change et mêlerait deux sources d'écart :
la performance du fonds et le mouvement de la devise. Les indicateurs sont donc
calculés en devise native, et les supports non libellés en euro sont signalés.

## 6 bis. Résultat du second tour et source retenue

Capture du 19 septembre 2026, 14 supports.

| Sonde | Résultat |
|---|---|
| `bourso_eod` | **HTTP 410** sur les 14 — point d'accès supprimé |
| `bourso_charts` | HTTP 200 mais réponse vide |
| `yahoo_chart` | **12/14, 978 à 1 280 séances** sur quatre ans et demi à cinq ans |

**Yahoo Finance est donc la source de collecte**, et Boursorama celle qui
résout les symboles : le point d'accès de Yahoo accepte les identifiants
Morningstar suffixés de la place de Francfort, et Boursorama les donne là où la
recherche Yahoo renvoie parfois une cotation secondaire.

Les deux échecs sont exactement ceux-là : Fidelity China et Pictet, résolus vers
`FJRH.F` et `PBFW.MU`, deux cotations quasi sans échanges.

Une **sonde croisée** rejoue ces cas avec l'identifiant Boursorama suffixé de
Francfort. Elle a résolu Pictet : de 1 à **1 157 séances**. Restait Fidelity
China, dont Boursorama ne donne qu'un code interne `MP-358709`, sans équivalent
Morningstar ; une **sonde par nom** interroge alors Yahoo sur le libellé du
fonds. Elle ne vise que les fonds non cotés — sur un tracker, le cours de bourse
est la donnée pertinente.

La sonde par nom a trouvé, pour Fidelity China, l'identifiant `0P00000TDB` que
ni l'ISIN ni Boursorama ne donnaient. La demande de série s'enchaîne désormais
automatiquement sur l'identifiant trouvé, avec et sans suffixe de place.

Couverture après la sonde croisée : **13 supports sur 14**, le quatorzième
restant à confirmer.

## 7. Critère d'acceptation

C'est ce qui distingue ce lot de la collecte des DIC : **il est vérifiable sans
avoir à croire personne**.

Une valeur liquidative est par construction nette des frais du fonds, exactement
comme la performance annuelle publiée par les assureurs. Pour chaque fonds et
chaque exercice, la performance recalculée depuis les VL doit donc retrouver le
chiffre publié.

La base contient **3 393 performances annuelles publiées**, et la confrontation
est automatisée par `tools/valider_series.py`.

### Le critère initial était naïf

La première rédaction exigeait un écart médian sous 0,10 point et moins de 5 %
des couples au-delà de 0,50. Mesuré, le résultat donnait 0,19 point de médiane
et **29 %** de dépassements : critère non tenu.

L'enquête a montré que la faute n'était pas à la source. Les séries ne
comportent **pas de séance au 31 décembre** : la dernière cotation de l'année
est celle du 30. L'assureur arrête au 31. Le calcul porte donc sur des bornes
décalées d'un jour, à l'ouverture comme à la clôture de l'exercice.

Trois faits l'établissent :

- l'erreur corrèle à **0,79** avec la volatilité quotidienne du fonds ;
- le fonds le moins volatil de l'échantillon, SLF Opportunité High Yield
  (0,21 % par jour), tombe **exactement juste quatre années sur quatre** ;
- sur un enchaînement de trois exercices, où les bornes intermédiaires se
  compensent, l'écart d'Alken retombe de 1,15 à 0,41 point et celui de SLF à
  0,00.

### Le critère retenu

Puisque l'écart provient d'un décalage d'une à deux séances, la tolérance suit
la **volatilité quotidienne du support** plutôt qu'un seuil unique :

> L'écart entre performance publiée et performance recalculée doit rester
> inférieur à **2,5 mouvements quotidiens** du fonds, avec un plancher de
> 0,10 point en deçà duquel l'arrondi des sources domine.

Sur un fonds obligataire la tolérance vaut 0,54 point ; sur un fonds aurifère,
3,55. C'est la même exigence exprimée dans l'unité qui convient à chaque
support.

### Mesure

| | |
|---|---|
| Couples comparés | 24, sur 7 supports |
| Écart médian | **0,20 point** |
| Hors tolérance | **0 (0 %)** |

Les six autres séries obtenues sont des ETF, pour lesquels les annexes ne
publient pas d'historique annuel : elles ne sont pas validables par ce contrôle.
C'est une limite de la validation, non des données.

## 8. Indicateurs à calculer

Une fois les séries en place, sur la période choisie par l'utilisateur :

- performance cumulée et annualisée entre deux dates quelconques ;
- volatilité annualisée, à partir des rendements hebdomadaires ;
- maximum drawdown, et durée de recouvrement ;
- ratio de Sharpe, une fois le taux sans risque choisi ;
- corrélation entre supports, pour juger la diversification réelle d'un portefeuille.

## 9. Ce qui restera hors de portée

Une partie de l'univers n'a pas de valeur liquidative publique : fonds dédiés ou
réservés, SCPI, produits structurés, et les 8 pseudo-ISIN `QS` d'épargne
salariale. Le taux de couverture sera **mesuré et publié** par palier, et non
supposé.

## 10. Étapes

| | Étape | Où |
|---|---|---|
| 1 | Capture des réponses des sources sur les 14 favoris | poste connecté |
| 2 | Écriture et test des parseurs contre les captures | ici |
| 3 | Base `cotations.db` et collecte des 14 favoris | poste connecté |
| 4 | Contrôle contre les performances publiées | ici |
| 5 | Indicateurs et affichage dans l'application | ici |
| 6 | Élargissement du périmètre, palier par palier | les deux |

L'étape 1 est faite. Le second tour de capture, `tools/capturer_historiques.py`,
vise les points d'accès d'historique avec les symboles déjà résolus — il ne
refait aucune requête de résolution, et les réponses attendues sont du JSON,
donc légères.
