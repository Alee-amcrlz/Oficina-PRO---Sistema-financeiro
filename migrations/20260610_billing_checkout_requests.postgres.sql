BEGIN;

CREATE TABLE IF NOT EXISTS billing_checkout_requests (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT NOT NULL REFERENCES companies(id),
    subscriptionId BIGINT REFERENCES subscriptions(id),
    plan TEXT NOT NULL,
    billingCycle TEXT NOT NULL DEFAULT 'monthly',
    provider TEXT NOT NULL,
    providerCheckoutId TEXT,
    initPoint TEXT,
    sandboxInitPoint TEXT,
    amount NUMERIC NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created',
    requestPayload JSONB NOT NULL DEFAULT '{}'::jsonb,
    responsePayload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_billing_checkout_company ON billing_checkout_requests(companyId);
CREATE INDEX IF NOT EXISTS idx_billing_checkout_status ON billing_checkout_requests(status);
CREATE INDEX IF NOT EXISTS idx_billing_checkout_created ON billing_checkout_requests(createdAt);

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260610_billing_checkout_requests', now()::text)
ON CONFLICT (version) DO NOTHING;

COMMIT;
