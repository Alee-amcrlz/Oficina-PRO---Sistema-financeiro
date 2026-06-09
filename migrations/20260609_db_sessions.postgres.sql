-- Persist authenticated sessions in PostgreSQL.
-- Version: 20260609_db_sessions

BEGIN;

CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    tokenHash TEXT NOT NULL UNIQUE,
    userId BIGINT NOT NULL REFERENCES users(id),
    expiresAt NUMERIC NOT NULL,
    createdAt NUMERIC NOT NULL,
    lastSeenAt NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(userId);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expiresAt);

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260609_db_sessions', now()::text)
ON CONFLICT (version) DO NOTHING;

COMMIT;
