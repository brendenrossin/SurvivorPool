-- Survivor Pool Database Schema

-- people playing
CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    display_name TEXT UNIQUE NOT NULL
);

-- raw picks as typed in the sheet (one row per player-week)
CREATE TABLE picks (
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
CREATE TABLE games (
    game_id TEXT PRIMARY KEY,   -- provider-native id or concat season/week/home/away
    season INT NOT NULL,
    week INT NOT NULL,
    kickoff TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    status TEXT NOT NULL,       -- 'pre','in','final'
    home_score INT,
    away_score INT,
    winner_abbr TEXT            -- null until final
);

-- results of picks evaluated against final winners
CREATE TABLE pick_results (
    pick_id INT PRIMARY KEY REFERENCES picks(pick_id) ON DELETE CASCADE,
    game_id TEXT REFERENCES games(game_id),
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,  -- e.g., duplicate-team violation
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    survived BOOLEAN                         -- null until game final; true/false afterwards
);

-- to prevent duplicate-team picks across the season
CREATE UNIQUE INDEX IF NOT EXISTS uniq_player_team_season
    ON picks(player_id, season, team_abbr)
    WHERE team_abbr IS NOT NULL;

-- metadata table for tracking job runs
CREATE TABLE job_meta (
    job_name TEXT PRIMARY KEY,
    last_success_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    status TEXT,
    message TEXT
);

-- indexes for performance
CREATE INDEX idx_picks_season_week ON picks(season, week);
CREATE INDEX idx_games_season_week ON games(season, week);
CREATE INDEX idx_games_status ON games(status);
CREATE INDEX idx_pick_results_survived ON pick_results(survived);