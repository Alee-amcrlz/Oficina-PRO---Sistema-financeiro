BEGIN;

CREATE TABLE IF NOT EXISTS marketing_leads (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    companyName TEXT,
    plan TEXT NOT NULL,
    billingCycle TEXT NOT NULL DEFAULT 'monthly',
    source TEXT,
    message TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    ipAddress TEXT,
    userAgent TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_marketing_leads_created ON marketing_leads(createdAt);
CREATE INDEX IF NOT EXISTS idx_marketing_leads_email ON marketing_leads(email);
CREATE INDEX IF NOT EXISTS idx_marketing_leads_status ON marketing_leads(status);

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260612_marketing_leads', now()::text)
ON CONFLICT (version) DO NOTHING;

COMMIT;
