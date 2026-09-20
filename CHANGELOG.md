# Journal des versions

Les versions sont numérotées `majeure.mineure.corrective` : la mineure avance
avec une fonctionnalité, la corrective avec un correctif. La majeure reste à 0
tant que le périmètre fonctionnel n'est pas arrêté.

## 0.19.2 — 20 septembre 2026

- Le README donnait les commandes `.bat` sans le préfixe `.\`. PowerShell
  n'exécute jamais un fichier du dossier courant sans lui, et répond « n'est pas
  reconnu » que le fichier existe ou non — message qui envoie chercher une
  absence là où il n'y a qu'une règle de résolution.
- Le mode ligne de commande y donnait encore `python -m venv`, remplacé par
  `py -3` pour la raison déjà connue.

## 0.19.1 — 20 septembre 2026

- **`openpyxl` manquait dans `requirements.txt`** : l'import des relevés
  échouait à l'import du module sur un poste où il n'était pas déjà installé.
- Nouveau **`cotations.bat`** : migration, chargement des captures et import des
  relevés en une commande, simulation par défaut. Les outils ne s'appellent plus
  par `python tools/…` — les dépendances vivent dans `.venv`, et sous Windows 11
  le nom `python` désigne un raccourci factice vers le Microsoft Store.
- La résolution de l'interpréteur passe dans **`_preparer.bat`**, appelé par les
  trois scripts. Elle vivait en double dans `lancer.bat` et `construire.bat` ;
  un troisième script en aurait fait une troisième copie.
- `_preparer.bat` **réinstalle les dépendances quand `requirements.txt` a
  changé**, en le comparant à une copie gardée dans `.venv`. Sans quoi une
  dépendance ajoutée par un `git pull` restait absente.
- `lancer.bat` lance la migration des cotations à chaque démarrage : elle est
  sans effet si elle a déjà eu lieu, mais un `git pull` peut faire avancer le
  schéma d'une base qui, elle, ne se reconstruit pas.

## 0.19.0 — 20 septembre 2026

- **La convention de cotation entre dans la clé** de `valeur_liquidative`, qui
  devient `(isin, date, base)`. Un même couple support-date porte deux valeurs
  légitimes : la clôture brute, qui est le prix du jour, et la clôture ajustée
  des dividendes, qui est la base d'une performance dividendes réinvestis. Sur
  un ETF distribuant l'écart dépasse 6 % et grandit avec l'ancienneté. Tant que
  la convention n'était pas dans la clé, un import pouvait écraser l'une par
  l'autre et la série mélangeait deux définitions, sans trace.
- Les captures portaient déjà `adjclose` : les deux conventions sont chargées
  côte à côte, sans nouvelle collecte. La vue `v_serie` tranche à la lecture,
  en préférant la série la plus fournie puis l'ajustée à égalité. Trois supports
  distribuants gagnent leurs dividendes — MSCI World Dist +19,1 → **+20,6 %**
  à un an, S&P 500 Dist +19,4 → **+20,6 %**.
- `tools/importer_vl.py` importe un relevé tableur. La convention et le moment
  se lisent ligne par ligne dans la remarque ; c'est la date retenue qui est
  stockée, jamais la date visée ; **un relevé ponctuel ne remplace jamais une
  valeur présente**, il comble un trou. Simulation par défaut, `--ecrire` pour
  écrire.
- Journal `import_cotation` avec empreinte SHA-256 — un fichier déjà importé est
  reconnu — et table `rejet_cotation` : une ligne écartée est consignée, jamais
  perdue.
- `tools/migrer_cotations.py` migre la base existante, qui s'accumule et ne se
  reconstruit pas. Sauvegarde horodatée, contrôle du nombre de lignes,
  sans effet si la migration est déjà faite.
- Premier import : **25 supports cotés** contre 14. Les 11 nouveaux sont des
  relevés ponctuels : ils n'apparaissent que sur l'exercice clos, qui passe de
  14 à **24 supports**. Les cinq fenêtres glissantes réclament une valeur du
  jour que le relevé ne porte pas.
- Date d'arrêt commune à tous les supports, prise comme **médiane** des
  dernières séances et non comme maximum : un seul support cotant un jour de
  plus déplaçait la performance à un an d'un ETF de +115,5 % à +107,1 %.
- `valeur_au` refuse une valeur vieille de plus de dix jours, et
  `performances_usuelles` accepte une date d'arrêt. 40 tests.

## 0.18.0 — 20 septembre 2026

- Nouveau tableau de bord, en trois menus : **LISTE**, **PERF**, **COMPARE**.
  Date et version passent en haut de la barre latérale ; les filtres
  s'appliquent aux trois menus ; Frais et Qualité des données deviennent deux
  annexes en pied de barre latérale, qui recouvrent le menu courant sans le
  changer. La fiche d'un support s'ouvre en sélectionnant sa ligne dans LISTE.
- Nouvel axe **véhicule** — Fond UC, ETF, Actions, FCPE, SCPI, Livret — qui
  remplace la classe d'actif Morningstar comme filtre. Il classe par ce que le
  support est, non par ce dans quoi il investit. Exhaustif et sans
  recouvrement : les tests le vérifient sur les 1 378 lignes. Deux écarts au
  croquis : SCPI est une sixième case, sans laquelle la part June Opportunity
  disparaîtrait de l'application ; Livret figure sans aucun membre, faute de
  source.
- **PERF** classe la sélection sur six horizons — 1 an, 2 ans, exercice clos,
  année en cours, 3 mois, 6 mois — bâtis sur les seules séries de valeurs
  liquidatives. Les performances annuelles publiées couvriraient plus de
  supports sur la case de l'exercice clos, mais sous une autre définition :
  les mélanger rendrait cette case incomparable à ses cinq voisines.
- **COMPARE** superpose jusqu'à huit trajectoires ramenées à 100 à leur départ
  commun, la première séance où tous les supports retenus cotent.
- Colonne `enveloppe` sur `instrument`, colonne `vehicule` sur `v_univers`.
- Spécification dans `docs/spec-tableau-de-bord.md`. 35 tests.

## 0.17.0 — 19 septembre 2026

- Le tableau de bord d'accueil est supprimé, en amont de sa refonte. Il est
  remplacé par une page d'attente qui le dit : un tableau de bord qu'on sait
  périmé oriente les lectures sans qu'on s'en aperçoive, le laisser en place
  pendant la refonte coûte plus qu'il ne rend.
- Disparaissent avec lui les graphiques qui ne servaient qu'à l'accueil —
  répartition par SRI, dispersion rendement/risque — et le saut de page
  `aller_a`. La rampe ordinale de risque est conservée : elle est validée en
  contraste et resservira. `Parcourir`, `Fiche`, `Frais` et `Qualité des
  données` sont inchangées.

## 0.16.1 — 19 septembre 2026

- `data/favoris.csv` sort du suivi Git. L'application l'écrit à chaque coche :
  un fichier que le programme modifie fait échouer `git pull` — c'est ce qui
  vient d'arriver. La semence versionnée reste `data/raw/favorites.txt` ; le
  CSV en est amorcé quand il manque, puis reste local. Une liste vidée à la
  main n'est pas ressuscitée.
- Six tests couvrent l'amorçage et la portée de l'édition filtrée.

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
