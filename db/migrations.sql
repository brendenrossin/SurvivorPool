-- Survivor Pool Database Schema

-- people playing
CREATE TABLE IF NOT EXISTS players (
    player_id SERIAL PRIMARY KEY,
    display_name TEXT UNIQUE NOT NULL
);

-- raw picks as typed in the sheet (one row per player-week)
CREATE TABLE IF NOT EXISTS picks (
    pick_id SERIAL PRIMARY KEY,
    player_id INT REFERENCES players(player_id),
    season INT NOT NULL,
    week INT NOT NULL,
    team_abbr TEXT,             -- e.g., 'BUF'
    source TEXT NOT NULL DEFAULT 'google_sheets',  -- provenance
    picked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(player_id, season, week)
);

-- canonical NFL games
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,   -- provider-native id or concat season/week/home/away
    season INT NOT NULL,
    week INT NOT NULL,
    kickoff TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    status TEXT NOT NULL,       -- 'pre','in','final'
    home_score INT,
    away_score INT,
    winner_abbr TEXT,           -- null until final
    -- Odds, added later. These lived only in init_db_railway.py's ALTER
    -- statements, so a fresh database built from this file alone was missing
    -- them while api/models.py declared them. Declared here so this file is
    -- the whole schema; the ALTERs remain for databases created before it.
    point_spread REAL,
    favorite_team VARCHAR(50)
);

-- results of picks evaluated against final winners
CREATE TABLE IF NOT EXISTS pick_results (
    pick_id INT PRIMARY KEY REFERENCES picks(pick_id) ON DELETE CASCADE,
    game_id TEXT REFERENCES games(game_id),
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    survived BOOLEAN
);

-- to prevent duplicate-team picks across the season
CREATE UNIQUE INDEX IF NOT EXISTS uniq_player_team_season
    ON picks(player_id, season, team_abbr)
    WHERE team_abbr IS NOT NULL;

-- metadata table for tracking job runs
CREATE TABLE IF NOT EXISTS job_meta (
    job_name TEXT PRIMARY KEY,
    last_success_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    status TEXT,
    message TEXT
);

-- indexes for performance
CREATE INDEX IF NOT EXISTS idx_picks_season_week ON picks(season, week);
CREATE INDEX IF NOT EXISTS idx_games_season_week ON games(season, week);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_pick_results_survived ON pick_results(survived);
CREATE INDEX IF NOT EXISTS idx_games_point_spread ON games(point_spread);
CREATE INDEX IF NOT EXISTS idx_games_favorite_team ON games(favorite_team);

-- GroupMe chat history, source of the recap bot's voice corpus
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    sender_id TEXT,
    sender_name TEXT,
    sender_type TEXT,
    text TEXT,
    favorite_count INT NOT NULL DEFAULT 0,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

-- Corpus reads are one shape: most-liked human messages before a cutoff.
-- A partial index over the fixed predicates serves the filter AND the sort from
-- a single scan; the two single-column indexes this replaced served neither
-- fully, and sender_type != 'bot' is an inequality a plain btree cannot seek on.
-- Must stay identical to ChatMessage.__table_args__ in api/models.py.
DROP INDEX IF EXISTS idx_chat_messages_created_at;
DROP INDEX IF EXISTS idx_chat_messages_favorites;
CREATE INDEX IF NOT EXISTS idx_chat_messages_corpus
    ON chat_messages (favorite_count DESC, created_at)
    WHERE is_system = false AND sender_type != 'bot';
