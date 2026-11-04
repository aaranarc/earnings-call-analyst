-- Shared request budget for stateless API instances. No browser access policies.
CREATE SCHEMA IF NOT EXISTS quantrag;
CREATE TABLE IF NOT EXISTS quantrag.api_daily_usage (
    day date PRIMARY KEY,
    requests integer NOT NULL CHECK (requests >= 0)
);
ALTER TABLE quantrag.api_daily_usage ENABLE ROW LEVEL SECURITY;
