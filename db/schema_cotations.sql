-- Cotations : valeurs liquidatives et cours, accumules dans le temps.
--
-- Base distincte de reference.db, et pour une raison de fond : reference.db est
-- effacee et reconstruite a chaque execution de construire.bat, ce qui la rend
-- reproductible et dispense de toute migration. Les cotations, elles, coutent
-- des heures de collecte et ne se regenerent pas depuis les documents. Les deux
-- se joignent par ATTACH. Le revers est qu'un changement de schema ici demande
-- une vraie migration : tools/migrer_cotations.py.

-- Un lot d'import. L'empreinte rend l'operation idempotente au niveau du
-- fichier, et l'identifiant rend un lot defaisable d'un seul DELETE.
CREATE TABLE IF NOT EXISTS import_cotation (
    id          INTEGER PRIMARY KEY,
    fichier     TEXT NOT NULL,
    empreinte   TEXT NOT NULL,          -- SHA-256 de la source
    extrait_le  TEXT,                   -- date d'extraction declaree par la source
    importe_le  TEXT NOT NULL,
    lignes_lues INTEGER,
    retenues    INTEGER,
    rejetees    INTEGER
);

-- Une observation, c'est un support, une date ET une convention.
--
-- Le meme couple (support, date) porte legitimement deux valeurs differentes :
-- la cloture brute, qui est le prix affiche ce jour-la, et la cloture ajustee
-- des dividendes detaches depuis, qui est la bonne base pour une performance
-- dividendes reinvestis. Sur un ETF distribuant l'ecart depasse 6 %, et il
-- grandit avec l'anciennete. Tant que la convention n'etait pas dans la cle, un
-- import pouvait ecraser l'une par l'autre : la serie melangeait alors deux
-- definitions, et toute performance calculee entre deux de ses points etait
-- fausse d'un montant devenu irretrouvable. La convention est donc dans la cle,
-- et melanger les deux n'est plus une question de discipline.
CREATE TABLE IF NOT EXISTS valeur_liquidative (
    isin      TEXT NOT NULL,
    date      TEXT NOT NULL,            -- la date reelle de la valeur, jamais la date visee
    base      TEXT NOT NULL CHECK (base IN ('brute', 'ajustee')),
    valeur    REAL NOT NULL,
    devise    TEXT,
    -- Une ouverture presentee pour une cloture n'est pas la meme mesure : les
    -- releves ponctuels en produisent, faute de donnee journaliere.
    moment    TEXT NOT NULL DEFAULT 'cloture' CHECK (moment IN ('cloture', 'ouverture')),
    source    TEXT NOT NULL,
    import_id INTEGER REFERENCES import_cotation(id),
    PRIMARY KEY (isin, date, base)
);

CREATE INDEX IF NOT EXISTS idx_vl_isin ON valeur_liquidative (isin, base);

-- Une ligne ecartee est consignee, jamais perdue : un ISIN introuvable ou une
-- valeur absente sont des informations sur la source, pas des non-evenements.
CREATE TABLE IF NOT EXISTS rejet_cotation (
    id         INTEGER PRIMARY KEY,
    import_id  INTEGER NOT NULL REFERENCES import_cotation(id),
    isin       TEXT,
    date_visee TEXT,
    motif      TEXT NOT NULL,
    detail     TEXT
);

-- Une ligne par tentative de collecte, aboutie ou non : un echec repete sur un
-- support est une information, pas un vide a ignorer.
CREATE TABLE IF NOT EXISTS collecte (
    id       INTEGER PRIMARY KEY,
    isin     TEXT NOT NULL,
    source   TEXT NOT NULL,
    symbole  TEXT,
    tente_le TEXT NOT NULL,
    statut   TEXT NOT NULL,             -- obtenu / vide / erreur
    points   INTEGER,
    debut    TEXT,
    fin      TEXT,
    devise   TEXT,
    detail   TEXT
);

-- La serie de reference d'un support : une seule convention, la plus fournie.
--
-- Departager par la densite et non par la convention preferee, parce qu'une
-- serie de sept releves ponctuels ne sert ni trajectoire, ni volatilite, ni
-- perte maximale -- la preferer a un historique quotidien les supprimerait.
-- A egalite de points, l'ajustee l'emporte : elle tient compte des dividendes
-- reellement encaisses, qu'une serie brute ignore.
DROP VIEW IF EXISTS v_serie;
CREATE VIEW v_serie AS
WITH densite AS (
    SELECT isin, base, COUNT(*) AS points,
           ROW_NUMBER() OVER (PARTITION BY isin
                              ORDER BY COUNT(*) DESC, base = 'ajustee' DESC) AS rang
    FROM valeur_liquidative
    GROUP BY isin, base
)
SELECT v.isin, v.date, v.valeur, v.devise, v.base, v.moment, v.source, d.points
FROM valeur_liquidative v
JOIN densite d ON d.isin = v.isin AND d.base = v.base AND d.rang = 1;
