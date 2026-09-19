# Journal des versions

Les versions sont numérotées `majeure.mineure.corrective` : la mineure avance
avec une fonctionnalité, la corrective avec un correctif. La majeure reste à 0
tant que le périmètre fonctionnel n'est pas arrêté.

## 0.16.0 — 19 septembre 2026

- Les supports détenus hors des deux contrats entrent au référentiel comme
  instruments sans offre rattachée : la liste suivie passe de 14 à 20 supports.
  Ils sont marqués « hors contrats » et n'ont ni SRI, ni frais, ni
  classification, aucun assureur ne les publiant.
- Le 21e support de la liste n'a qu'un code AMF, pas d'ISIN : il est consigné
  comme anomalie et signalé sous le filtre Favoris, au lieu de manquer en
  silence.
- La vue `v_univers` distingue un quatrième cas de disponibilité. Elle
  rattachait jusque-là à BoursoVie tout instrument sans offre.

## 0.15.0 — 19 septembre 2026

- Performances de référence sur la fiche d'un support : dernier exercice civil
  complet, depuis le 1er janvier, et 3, 6, 12 et 24 mois glissants. Toutes
  cumulées, calculées sur la série de valeurs liquidatives.
- Une période que l'historique ne couvre pas reste vide plutôt que d'être
  calculée sur une fenêtre tronquée.
- Dans le tableau de Parcourir, « Depuis 1er janv. » et « 12 mois » remplacent
  les mesures tirées des exercices publiés dès qu'un support affiché porte une
  série : plus fines, plus récentes, et le nombre de colonnes reste lisible.

## 0.14.0 — 19 septembre 2026

- Base `cotations.db`, accumulée et distincte de `reference.db`, chargée depuis
  les captures par `tools/charger_cotations.py` : 16 696 valeurs sur 14 supports.
- La fiche d'un support affiche sa trajectoire quotidienne ramenée à 100, sa
  perte depuis chaque plus haut, et trois mesures : rendement annualisé observé,
  volatilité annualisée, perte maximale.
- `app/indicateurs.py` et ses six tests.
- Le rendement publié et le rendement observé portent désormais des libellés
  distincts : ils ne mesurent ni la même période ni la même devise.

## 0.13.0 — 19 septembre 2026

- Couverture complète : **14 séries sur 14**, de 978 à 1 280 séances. Fidelity
  China répond sur l'identifiant nu, la variante suffixée de Francfort donnant
  404.
- Le validateur tient compte de la devise. Un support libellé en dollar n'est
  pas comparable à une performance publiée en euro : il est écarté du verdict
  plutôt que compté en échec. Deux séries sont dans ce cas.
- Validation : 24 couples sur 7 supports, 0,20 point d'écart médian, aucun hors
  tolérance.

## 0.12.0 — 19 septembre 2026

- La recherche par nom trouve pour Fidelity China l'identifiant `0P00000TDB`,
  que ni son ISIN ni Boursorama ne donnaient.
- Les sondes s'enchaînent : une recherche par nom déclenche aussitôt la demande
  de série sur l'identifiant trouvé, avec et sans suffixe de place. Un tour de
  capture supplémentaire est ainsi évité.

## 0.11.0 — 19 septembre 2026

- La sonde croisée résout Pictet : de 1 à 1 157 séances. Couverture portée à
  13 supports sur 14.
- Sonde par nom ajoutée pour le dernier manquant, Fidelity China, dont aucune
  source ne donne d'identifiant Morningstar. Elle ne vise que les fonds non
  cotés.
- Le validateur retient la série la plus fournie par support, toutes sondes
  confondues, et le lecteur de séries ignore les réponses qui ne suivent pas le
  format attendu au lieu de lever une exception.
- Validation : 24 couples sur 7 supports, 0,20 point d'écart médian, aucun hors
  tolérance.

## 0.10.0 — 19 septembre 2026

- Second tour de capture dépouillé. Les deux points d'accès Boursorama sont
  hors service — 410 pour l'un, réponse vide pour l'autre. Yahoo Finance livre
  978 à 1 280 séances pour 12 des 14 supports.
- `tools/collecte/yahoo.py` lit les séries, `tests/test_yahoo.py` le vérifie
  contre les captures.
- `tools/valider_series.py` confronte les séries aux performances publiées.
- Le critère d'acceptation est reformulé : il suit désormais la volatilité
  quotidienne du support, l'écart provenant d'un décalage de bornes et non d'un
  défaut de la source. Résultat : 21 couples, 0,19 point d'écart médian, aucun
  hors tolérance.

## 0.9.0 — 19 septembre 2026

- Premier tour de capture dépouillé : Boursorama et Yahoo Finance résolvent
  chacun les 14 supports, Quantalys et l'AMF sont écartés faute de répondre sans
  navigateur piloté.
- `tools/collecte/symboles.py` extrait le symbole d'un support et en qualifie la
  nature — valeur liquidative ou cours de bourse. `tests/test_symboles.py` le
  vérifie contre les 28 captures réelles.
- `tools/capturer_historiques.py` sonde les points d'accès d'historique avec les
  symboles déjà résolus.

## 0.8.0 — 19 septembre 2026

- Spécification de la collecte des valeurs liquidatives :
  `docs/spec-valeurs-liquidatives.md`.
- `tools/capturer_sources.py` interroge les sources candidates et archive leurs
  réponses brutes, qui serviront de jeu de test aux parseurs. L'environnement de
  développement n'ayant pas accès à l'internet public, les parseurs ne peuvent
  être mis au point et vérifiés que contre ces captures.

## 0.7.0 — 19 septembre 2026

- Les favoris portent une note libre, qui sert à indiquer l'enveloppe de
  détention. Elle s'affiche sur la fiche du support, et remplace la colonne
  « Disponible » dans le tableau dès qu'un support affiché en porte une.
- `tools/importer_favoris.py` reprend la liste tenue à la main dans
  `data/raw/favorites.txt` vers les favoris de l'application, et énumère les
  supports qu'il n'a pas pu rattacher.
- Premier import : 14 des 21 supports de la liste. Les 6 autres — fonds de PEE,
  ETF réservé au PEA, part de SCPI — ne figurent dans aucun des deux contrats,
  et un septième ne porte pas d'ISIN.

## 0.6.0 — 19 septembre 2026

- Favoris : une case à cocher dans le tableau de la page Parcourir et une
  bascule sur la fiche d'un support permettent de tenir une liste de supports
  suivis, filtrable par « Favoris : Oui / Non » dans la barre latérale.
- La liste vit dans `data/favoris.csv`, hors de la base : celle-ci est effacée
  et reconstruite à chaque exécution de `construire.bat`, elle ne peut donc pas
  accueillir de donnée saisie par l'utilisateur.

## 0.5.0 — 19 septembre 2026

- Version et date affichées en tête de chaque page, avec le millésime des
  documents sources.

## 0.4.0 — 19 septembre 2026

- Page d'accueil : composition de l'univers, profil de risque, et dispersion du
  rendement à chaque niveau de risque.
- Page Parcourir : exploration par classe d'actif, par risque ou par
  performance, avec mise en avant du segment retenu.
- Le rendement affiché devient annualisé au sens géométrique. La moyenne
  arithmétique employée jusque-là surestimait le rendement réellement obtenu de
  0,60 point en médiane, et jusqu'à 8,2 points.
- Les trous de couverture apparaissent comme des segments à part entière :
  470 supports sans SRI, 495 sans historique de performance.
- Les frais quittent les filtres principaux pour un volet replié.

## 0.3.0 — 19 septembre 2026

- Interface Streamlit de consultation, en lecture seule.
- Correctif des lanceurs Windows : `py` est essayé en premier et chaque
  interpréteur candidat est réellement exécuté, le raccourci Microsoft Store
  faisant échouer la détection par le PATH. Fichiers `.bat` en CRLF.

## 0.2.0 — 19 septembre 2026

- Base SQLite locale : 1 372 instruments, 1 533 offres, 3 393 performances
  annuelles, reconstruite intégralement à chaque exécution.
- Contrôles au chargement consignés dans la table `anomalie`, dont la
  réconciliation des effectifs contre l'inventaire ISIN des PDF.
- Mise en évidence de l'écart de définition des frais entre assureurs :
  139 des 161 fonds communs affichent des frais de fonds divergents.

## 0.1.0 — 19 septembre 2026

- Récupération des 57 supports BoursoVie absents des fiches, portant l'univers
  à la totalité des 631 supports du document source.
- Outils d'extraction, de classification et de génération des fiches.
