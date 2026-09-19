-- Cotations : valeurs liquidatives et cours, accumules dans le temps.
--
-- Base distincte de reference.db, et pour une raison de fond : reference.db est
-- effacee et reconstruite a chaque execution de construire.bat, ce qui la rend
-- reproductible et dispense de toute migration. Les cotations, elles, coutent
-- des heures de collecte et ne se regenerent pas depuis les documents. Les deux
-- se joignent par ATTACH.

CREATE TABLE IF NOT EXISTS valeur_liquidative (
    isin   TEXT NOT NULL,
    date   TEXT NOT NULL,
    valeur REAL NOT NULL,
    devise TEXT,
    source TEXT NOT NULL,
    PRIMARY KEY (isin, date)
);

CREATE INDEX IF NOT EXISTS idx_vl_isin ON valeur_liquidative (isin);

-- Une ligne par tentative, aboutie ou non : un echec repete sur un support est
-- une information, pas un vide a ignorer.
CREATE TABLE IF NOT EXISTS collecte (
    id       INTEGER PRIMARY KEY,
    isin     TEXT NOT NULL,
    source   TEXT NOT NULL,
    symbole  TEXT,
    tente_le TEXT NOT NULL,
    statut   TEXT NOT NULL,          -- obtenu / vide / erreur
    points   INTEGER,
    debut    TEXT,
    fin      TEXT,
    devise   TEXT,
    detail   TEXT
);
