-- Persist authenticated sessions in SQLite.
-- Version: 20260609_db_sessions

CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tokenHash TEXT NOT NULL UNIQUE,
    userId INTEGER NOT NULL,
    expiresAt REAL NOT NULL,
    createdAt REAL NOT NULL,
    lastSeenAt REAL NOT NULL,
    FOREIGN KEY (userId) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(userId);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expiresAt);

INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
VALUES ('20260609_db_sessions', datetime('now'));
