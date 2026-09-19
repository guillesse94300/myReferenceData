-- Univers d'investissement : schema de la base locale.
--
-- Trois principes structurants :
--   1. l'ISIN est la cle pivot, le fournisseur est une dimension separee : un
--      meme fonds peut etre offert par les deux assureurs a des conditions
--      differentes, et chaque offre porte ses propres frais ;
--   2. les frais publies ne sont pas comparables entre assureurs, car la
--      formule differe -- une mesure homogene est donc calculee a cote ;
--   3. tout provient d'un import date et trace, et les ecarts constates au
--      chargement sont conserves plutot que corriges en silence.

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_arbitrage;
DROP VIEW  IF EXISTS v_univers;
DROP TABLE IF EXISTS anomalie;
DROP TABLE IF EXISTS performance_annuelle;
DROP TABLE IF EXISTS offre;
DROP TABLE IF EXISTS instrument;
DROP TABLE IF EXISTS import;

-- Un import = un document source charge a une date donnee.
CREATE TABLE import (
    id          INTEGER PRIMARY KEY,
    fournisseur TEXT    NOT NULL,
    document    TEXT    NOT NULL,          -- nom du PDF d'origine
    empreinte   TEXT    NOT NULL,          -- sha256 du PDF, pour detecter un nouveau millesime
    millesime   TEXT    NOT NULL,          -- date de reference du document
    importe_le  TEXT    NOT NULL,
    lignes      INTEGER NOT NULL
);

-- Referentiel instrument : ce qui ne depend pas de l'assureur.
CREATE TABLE instrument (
    isin            TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    societe_gestion TEXT,
    type_instrument TEXT NOT NULL CHECK (type_instrument IN ('opc', 'etf', 'action')),
    forme_juridique TEXT,
    devise          TEXT,
    pays            TEXT,                  -- actions en direct uniquement
    notation        TEXT                   -- notation emetteur, actions en direct
);

-- Conditions d'acces a un instrument chez un assureur donne.
CREATE TABLE offre (
    id                       INTEGER PRIMARY KEY,
    import_id                INTEGER NOT NULL REFERENCES import(id),
    isin                     TEXT    NOT NULL REFERENCES instrument(isin),
    fournisseur              TEXT    NOT NULL,
    contrat                  TEXT    NOT NULL,
    -- classification
    grande_classe            TEXT,
    type_actif               TEXT,
    origine_classification   TEXT,         -- fiabilite de la classification ci-dessus
    -- caracteristiques reglementaires
    sfdr                     TEXT,
    sri                      INTEGER CHECK (sri IS NULL OR sri BETWEEN 1 AND 7),
    label                    TEXT,
    statut                   TEXT,         -- maintenu / nouveau, cote SwissLife
    avenant                  INTEGER NOT NULL DEFAULT 0 CHECK (avenant IN (0, 1)),
    -- frais, en points de pourcentage
    frais_fonds              REAL,         -- frais de gestion de l'actif
    frais_contrat            REAL,         -- frais de gestion du contrat
    frais_totaux_publies     REAL,         -- tels qu'affiches par l'assureur
    frais_totaux_comparables REAL,         -- frais_fonds + frais_contrat, homogene entre assureurs
    retrocessions            REAL,
    -- performances du dernier exercice clos
    perf_brute_n1            REAL,
    perf_nette_n1            REAL,
    perf_finale_n1           REAL,
    perf_finale_5a           REAL,         -- moyenne annualisee, SwissLife uniquement
    UNIQUE (isin, fournisseur, contrat)
);

CREATE INDEX idx_offre_isin        ON offre (isin);
CREATE INDEX idx_offre_fournisseur ON offre (fournisseur);
CREATE INDEX idx_offre_classe      ON offre (grande_classe, type_actif);

-- Historique annuel de performance nette (SwissLife : 2021 a 2025).
CREATE TABLE performance_annuelle (
    isin        TEXT    NOT NULL REFERENCES instrument(isin),
    fournisseur TEXT    NOT NULL,
    annee       INTEGER NOT NULL,
    perf_nette  REAL    NOT NULL,
    PRIMARY KEY (isin, fournisseur, annee)
);

-- Ecarts releves par les controles de chargement.
CREATE TABLE anomalie (
    id       INTEGER PRIMARY KEY,
    controle TEXT NOT NULL,
    gravite  TEXT NOT NULL CHECK (gravite IN ('bloquant', 'avertissement')),
    isin     TEXT,
    detail   TEXT NOT NULL
);

-- Univers consolide : une ligne par instrument, les deux assureurs cote a cote.
CREATE VIEW v_univers AS
SELECT i.isin,
       i.nom,
       i.societe_gestion,
       i.type_instrument,
       i.devise,
       COALESCE(sl.grande_classe, bo.grande_classe, 'Hors contrats') AS grande_classe,
       COALESCE(sl.type_actif,    bo.type_actif,    'Non classé')    AS type_actif,
       COALESCE(sl.origine_classification, bo.origine_classification) AS origine_classification,
       COALESCE(sl.sfdr, bo.sfdr)                   AS sfdr,
       sl.sri                                       AS sri,
       sl.frais_fonds                               AS frais_fonds_swisslife,
       bo.frais_fonds                               AS frais_fonds_boursorama,
       sl.frais_totaux_comparables                  AS frais_swisslife,
       bo.frais_totaux_comparables                  AS frais_boursorama,
       -- Un instrument peut n'etre offert par aucun des deux assureurs : c'est le
       -- cas des supports detenus hors assurance-vie, suivis mais non achetables ici.
       CASE WHEN sl.isin IS NOT NULL AND bo.isin IS NOT NULL THEN 'les deux'
            WHEN sl.isin IS NOT NULL                         THEN 'SwissLife'
            WHEN bo.isin IS NOT NULL                         THEN 'BoursoVie'
            ELSE 'hors contrats' END                AS disponibilite
FROM instrument i
LEFT JOIN offre sl ON sl.isin = i.isin AND sl.fournisseur = 'SwissLife'
LEFT JOIN offre bo ON bo.isin = i.isin AND bo.fournisseur = 'BoursoVie';

-- Fonds accessibles chez les deux assureurs, ranges par economie de frais.
--
-- Reserve importante : les deux assureurs ne publient pas la meme grandeur pour
-- les frais du fonds lui-meme -- charges reellement supportees sur le dernier
-- exercice d'un cote, frais contractuels de l'autre. L'ecart affiche melange
-- donc un differentiel tarifaire reel et une difference de definition. Seul
-- l'ecart de frais de contrat (0,96 % contre 0,75 %) est pleinement comparable,
-- et la colonne fiabilite dit sur quelles lignes s'appuyer.
CREATE VIEW v_arbitrage AS
SELECT isin,
       nom,
       grande_classe,
       type_actif,
       frais_swisslife,
       frais_boursorama,
       ROUND(frais_boursorama - frais_swisslife, 4)                      AS ecart,
       ROUND(frais_fonds_boursorama - frais_fonds_swisslife, 4)          AS ecart_frais_fonds,
       CASE WHEN frais_boursorama < frais_swisslife THEN 'BoursoVie' ELSE 'SwissLife' END AS moins_cher,
       CASE WHEN frais_fonds_boursorama = 0 THEN 'frais du fonds nuls chez BoursoVie'
            WHEN ABS(frais_fonds_boursorama - frais_fonds_swisslife) > 0.05
                 THEN 'définitions divergentes'
            ELSE 'comparable' END                                        AS fiabilite
FROM v_univers
WHERE disponibilite = 'les deux'
  AND frais_swisslife IS NOT NULL
  AND frais_boursorama IS NOT NULL
ORDER BY ecart;
