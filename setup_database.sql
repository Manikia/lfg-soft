-- ============================================================
-- LFG Tool — Database Setup
-- Run this in Supabase SQL Editor before starting the server
-- ============================================================

-- Enable pgcrypto for email encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Listings table
-- Stores active "looking for game" posts
CREATE TABLE IF NOT EXISTS listings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    riot_id TEXT NOT NULL,                         -- GameName#TAG (stored encrypted)
    region TEXT NOT NULL,                          -- e.g. NA1, EUW1, KR
    rank TEXT NOT NULL,                            -- e.g. "GOLD II"
    tier TEXT NOT NULL,                            -- e.g. "GOLD"
    winrate FLOAT NOT NULL DEFAULT 0,              -- e.g. 54.2
    total_games INT NOT NULL DEFAULT 0,            -- ranked games played
    role TEXT NOT NULL DEFAULT 'Fill',             -- Top/Jungle/Mid/ADC/Support/Fill
    notes TEXT DEFAULT '',                         -- optional message to potential teammates
    email TEXT NOT NULL,                           -- contact email (stored encrypted)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '60 minutes',
    fulfilled BOOLEAN DEFAULT FALSE
);

-- Requests table
-- Stores pending/approved/denied match requests
CREATE TABLE IF NOT EXISTS requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    requester_riot_id TEXT NOT NULL,               -- GameName#TAG of person sending request
    requester_rank TEXT NOT NULL,
    requester_role TEXT NOT NULL,
    requester_winrate FLOAT NOT NULL DEFAULT 0,
    requester_notes TEXT DEFAULT '',
    requester_email TEXT NOT NULL,                 -- for sending approval/denial notification
    target_listing_id UUID REFERENCES listings(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',        -- pending | approved | denied
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast browse queries
CREATE INDEX IF NOT EXISTS idx_listings_region ON listings(region);
CREATE INDEX IF NOT EXISTS idx_listings_expires ON listings(expires_at);
CREATE INDEX IF NOT EXISTS idx_listings_fulfilled ON listings(fulfilled);
CREATE INDEX IF NOT EXISTS idx_requests_target ON requests(target_listing_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);

-- Auto-cleanup: Supabase Edge Function (or cron job) to delete expired listings
-- You can also call the /cleanup endpoint manually or via a scheduler
-- Run this in Supabase SQL Editor to create a pg_cron job if you have it enabled:
-- SELECT cron.schedule('cleanup-expired-listings', '*/15 * * * *', $$
--     DELETE FROM listings WHERE expires_at < NOW() AND fulfilled = FALSE;
-- $$);
