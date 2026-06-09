-- Audit login attempts and support brute-force protection in SQLite.
-- Version: 20260609_login_audit

CREATE TABLE IF NOT EXISTS login_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    ipAddress TEXT,
    userAgent TEXT,
    createdAt REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_audit_login_created ON login_audit(login, createdAt);
CREATE INDEX IF NOT EXISTS idx_login_audit_created ON login_audit(createdAt);

INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
VALUES ('20260609_login_audit', datetime('now'));
