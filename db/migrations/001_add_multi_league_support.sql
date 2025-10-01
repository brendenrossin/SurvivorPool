-- Migration 001: Add Multi-League Support
-- This migration adds league support while maintaining backward compatibility
-- with existing single-league data

-- ============================================================================
-- STEP 1: Create leagues table
-- ============================================================================
CREATE TABLE IF NOT EXISTS leagues (
    league_id SERIAL PRIMARY KEY,
    league_name VARCHAR(255) NOT NULL,
    league_slug VARCHAR(100) UNIQUE NOT NULL,  -- URL-safe identifier (e.g., 'rossin-family-2025')
    pick_source VARCHAR(50) NOT NULL DEFAULT 'google_sheets',  -- 'google_sheets' or 'in_app'
    google_sheet_id VARCHAR(255),  -- NULL if pick_source='in_app'
    season INT NOT NULL,
    commissioner_email VARCHAR(255),  -- Who created/manages this league
    invite_code VARCHAR(50) UNIQUE,  -- Unique code for players to join
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb,  -- League-specific settings (entry fee, rules, etc.)

    -- Constraints
    CONSTRAINT valid_pick_source CHECK (pick_source IN ('google_sheets', 'in_app')),
    CONSTRAINT sheet_id_required CHECK (
        (pick_source = 'google_sheets' AND google_sheet_id IS NOT NULL) OR
        (pick_source = 'in_app')
    )
);

-- Create index for fast league lookup by slug
CREATE INDEX IF NOT EXISTS idx_leagues_slug ON leagues(league_slug);
CREATE INDEX IF NOT EXISTS idx_leagues_invite_code ON leagues(invite_code);

-- ============================================================================
-- STEP 2: Add league_id to existing tables (nullable for backward compatibility)
-- ============================================================================

-- Add league_id to players table
ALTER TABLE players ADD COLUMN IF NOT EXISTS league_id INT REFERENCES leagues(league_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_players_league_id ON players(league_id);

-- Add league_id to picks table
ALTER TABLE picks ADD COLUMN IF NOT EXISTS league_id INT REFERENCES leagues(league_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_picks_league_id ON picks(league_id);

-- Note: games table is shared across all leagues (NFL games don't belong to a specific league)
-- So we don't add league_id to games

-- ============================================================================
-- STEP 3: Create default league for existing data
-- ============================================================================

-- Insert default league (will be updated by migration script with real values)
INSERT INTO leagues (
    league_id,
    league_name,
    league_slug,
    pick_source,
    google_sheet_id,
    season,
    commissioner_email,
    invite_code,
    settings
) VALUES (
    1,
    'Rossin Family Survivor Pool 2025',  -- Default name (can be updated)
    'rossin-family-2025',
    'google_sheets',
    NULL,  -- Will be set by migration script from env var
    2025,
    NULL,  -- Will be set by migration script
    'ROSSIN2025',  -- Default invite code
    '{
        "entry_fee": null,
        "rules": "Standard NFL Survivor Pool rules",
        "created_from_migration": true
    }'::jsonb
) ON CONFLICT (league_id) DO NOTHING;

-- Set the sequence to start from 2 (since we manually inserted league_id=1)
SELECT setval('leagues_league_id_seq', 1, true);

-- ============================================================================
-- STEP 4: Migrate existing data to default league
-- ============================================================================

-- Update all existing players to belong to league 1
UPDATE players SET league_id = 1 WHERE league_id IS NULL;

-- Update all existing picks to belong to league 1
UPDATE picks SET league_id = 1 WHERE league_id IS NULL;

-- ============================================================================
-- STEP 5: Make league_id NOT NULL after migration (enforce data integrity)
-- ============================================================================

-- Now that all existing data has league_id, make it required
ALTER TABLE players ALTER COLUMN league_id SET NOT NULL;
ALTER TABLE picks ALTER COLUMN league_id SET NOT NULL;

-- ============================================================================
-- STEP 6: Create users table for in-app authentication
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),  -- NULL if using magic links/OAuth
    auth_provider VARCHAR(50) DEFAULT 'email',  -- 'email', 'google', 'magic_link'
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,

    CONSTRAINT valid_auth_provider CHECK (auth_provider IN ('email', 'google', 'magic_link'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================================
-- STEP 7: Create user_players junction table (one user can have players in multiple leagues)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_players (
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    player_id INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (user_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_user_players_user_id ON user_players(user_id);
CREATE INDEX IF NOT EXISTS idx_user_players_player_id ON user_players(player_id);

-- ============================================================================
-- STEP 8: Create league_commissioners table (track who can manage each league)
-- ============================================================================

CREATE TABLE IF NOT EXISTS league_commissioners (
    league_id INT NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'commissioner',  -- 'commissioner' or 'admin'
    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (league_id, user_id),
    CONSTRAINT valid_role CHECK (role IN ('commissioner', 'admin'))
);

CREATE INDEX IF NOT EXISTS idx_league_commissioners_league_id ON league_commissioners(league_id);
CREATE INDEX IF NOT EXISTS idx_league_commissioners_user_id ON league_commissioners(user_id);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Verify migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 001 completed successfully!';
    RAISE NOTICE 'Created tables: leagues, users, user_players, league_commissioners';
    RAISE NOTICE 'Added league_id to: players, picks';
    RAISE NOTICE 'Migrated existing data to league_id=1';
END $$;
