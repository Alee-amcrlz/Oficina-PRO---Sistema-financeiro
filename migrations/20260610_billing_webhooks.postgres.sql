BEGIN;

CREATE TABLE IF NOT EXISTS billing_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    eventId TEXT,
    eventType TEXT,
    action TEXT,
    resourceId TEXT,
    requestId TEXT,
    signatureTs TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    receivedAt TEXT,
    processedAt TEXT,
    status TEXT NOT NULL DEFAULT 'received',
    error TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_webhook_provider_event
    ON billing_webhook_events(provider, eventId)
    WHERE eventId IS NOT NULL AND btrim(eventId) <> '';

CREATE INDEX IF NOT EXISTS idx_billing_webhook_received ON billing_webhook_events(receivedAt);

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260610_billing_webhooks', now()::text)
ON CONFLICT (version) DO NOTHING;

COMMIT;
