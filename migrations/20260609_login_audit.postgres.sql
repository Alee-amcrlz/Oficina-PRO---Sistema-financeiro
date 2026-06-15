-- Audit login attempts and support brute-force protection in PostgreSQL.
-- Version: 20260609_login_audit

BEGIN;

CREATE TABLE IF NOT EXISTS login_audit (
    id BIGSERIAL PRIMARY KEY,
    login TEXT NOT NULL,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT,
    ipAddress TEXT,
    userAgent TEXT,
    createdAt NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_audit_login_created ON login_audit(login, createdAt);
CREATE INDEX IF NOT EXISTS idx_login_audit_created ON login_audit(createdAt);

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260609_login_audit', now()::text)
ON CONFLICT (version) DO NOTHING;

COMMIT;
