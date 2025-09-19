-- Migration: Add betting odds columns to games table
-- Run this on your local PostgreSQL database

-- Add point_spread column (nullable, REAL type)
ALTER TABLE games ADD COLUMN IF NOT EXISTS point_spread REAL;

-- Add favorite_team column (nullable, text type)
ALTER TABLE games ADD COLUMN IF NOT EXISTS favorite_team VARCHAR(10);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_games_point_spread ON games (point_spread);
CREATE INDEX IF NOT EXISTS idx_games_favorite_team ON games (favorite_team);

-- Show table structure to verify
\d+ games;