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

## 6. Devises

Les valeurs liquidatives sont stockées **en devise native**, avec la devise.
976 instruments sont en euro, 31 en dollar, 3 en franc suisse, 1 en couronne
suédoise, et 361 n'ont pas de devise renseignée — à combler au passage.

Convertir demanderait un historique de change et mêlerait deux sources d'écart :
la performance du fonds et le mouvement de la devise. Les indicateurs sont donc
calculés en devise native, et les supports non libellés en euro sont signalés.

## 7. Critère d'acceptation

C'est ce qui distingue ce lot de la collecte des DIC : **il est vérifiable sans
avoir à croire personne**.

Une valeur liquidative est par construction nette des frais du fonds, exactement
comme la performance annuelle publiée par les assureurs. Pour chaque fonds et
chaque exercice, la performance recalculée depuis les VL doit donc retrouver le
chiffre publié.

La base contient **3 393 performances annuelles publiées**. Le contrôle compare
chaque couple et le lot n'est accepté que si :

- l'écart médian est inférieur à **0,10 point** ;
- moins de **5 %** des couples dépassent 0,50 point d'écart ;
- chaque dépassement est expliqué, ou le support écarté.

Un parseur défaillant ou une source de mauvaise qualité échoue immédiatement ce
contrôle.

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

L'étape 1 est livrée : `tools/capturer_sources.py`.
