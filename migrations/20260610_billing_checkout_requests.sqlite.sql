BEGIN;

CREATE TABLE IF NOT EXISTS billing_checkout_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    companyId INTEGER NOT NULL,
    subscriptionId INTEGER,
    plan TEXT NOT NULL,
    billingCycle TEXT NOT NULL DEFAULT 'monthly',
    provider TEXT NOT NULL,
    providerCheckoutId TEXT,
    initPoint TEXT,
    sandboxInitPoint TEXT,
    amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created',
    requestPayload TEXT NOT NULL DEFAULT '{}',
    responsePayload TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    createdAt TEXT,
    updatedAt TEXT,
    FOREIGN KEY (companyId) REFERENCES companies(id),
    FOREIGN KEY (subscriptionId) REFERENCES subscriptions(id)
);

CREATE INDEX IF NOT EXISTS idx_billing_checkout_company ON billing_checkout_requests(companyId);
CREATE INDEX IF NOT EXISTS idx_billing_checkout_status ON billing_checkout_requests(status);
CREATE INDEX IF NOT EXISTS idx_billing_checkout_created ON billing_checkout_requests(createdAt);

INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
VALUES ('20260610_billing_checkout_requests', datetime('now'));

COMMIT;
