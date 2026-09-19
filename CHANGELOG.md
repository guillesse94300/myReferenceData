# Journal des versions

Les versions sont numérotées `majeure.mineure.corrective` : la mineure avance
avec une fonctionnalité, la corrective avec un correctif. La majeure reste à 0
tant que le périmètre fonctionnel n'est pas arrêté.

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
