BEGIN;

CREATE TABLE IF NOT EXISTS billing_webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    eventId TEXT,
    eventType TEXT,
    action TEXT,
    resourceId TEXT,
    requestId TEXT,
    signatureTs TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    receivedAt TEXT,
    processedAt TEXT,
    status TEXT NOT NULL DEFAULT 'received',
    error TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_webhook_provider_event
    ON billing_webhook_events(provider, eventId)
    WHERE eventId IS NOT NULL AND trim(eventId) <> '';

CREATE INDEX IF NOT EXISTS idx_billing_webhook_received ON billing_webhook_events(receivedAt);

INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
VALUES ('20260610_billing_webhooks', datetime('now'));

COMMIT;
