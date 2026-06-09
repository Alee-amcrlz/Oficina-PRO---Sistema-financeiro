-- Oficina Pro Web SaaS baseline schema for PostgreSQL
-- Version: 20260609_web_saas_baseline

BEGIN;

CREATE TABLE IF NOT EXISTS companies (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    document TEXT,
    phone TEXT,
    ownerUserId BIGINT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    appliedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    isPlatformAdmin BOOLEAN NOT NULL DEFAULT FALSE,
    name TEXT NOT NULL,
    username TEXT,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    passwordHash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    accessLevel TEXT NOT NULL DEFAULT 'analista',
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
    ON users(lower(username))
    WHERE username IS NOT NULL AND btrim(username) <> '';
CREATE INDEX IF NOT EXISTS idx_users_company ON users(companyId);

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

CREATE TABLE IF NOT EXISTS budgets (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    userId BIGINT NOT NULL REFERENCES users(id),
    clientName TEXT NOT NULL,
    clientEmail TEXT,
    clientPhone TEXT,
    clientZip TEXT,
    clientStreet TEXT,
    clientNumber TEXT,
    clientAddress TEXT,
    clientDistrict TEXT,
    clientState TEXT,
    vehicleBrand TEXT,
    vehicleModel TEXT,
    vehicleYear TEXT,
    vehicle TEXT,
    plate TEXT,
    vehicleColor TEXT,
    vehicleKm TEXT,
    parts JSONB NOT NULL DEFAULT '[]'::jsonb,
    labor JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT,
    laborValue NUMERIC NOT NULL DEFAULT 0,
    partsValue NUMERIC NOT NULL DEFAULT 0,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pendente',
    approvedAt TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_budgets_company ON budgets(companyId);
CREATE INDEX IF NOT EXISTS idx_budgets_user ON budgets(userId);
CREATE INDEX IF NOT EXISTS idx_budgets_status ON budgets(status);
CREATE INDEX IF NOT EXISTS idx_budgets_created ON budgets(createdAt);
CREATE INDEX IF NOT EXISTS idx_budgets_approved ON budgets(approvedAt);

CREATE TABLE IF NOT EXISTS customers (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    zip TEXT,
    street TEXT,
    number TEXT,
    district TEXT,
    state TEXT,
    notes TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_customers_company ON customers(companyId);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

CREATE TABLE IF NOT EXISTS vehicles (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    customerId BIGINT REFERENCES customers(id),
    brand TEXT,
    model TEXT,
    year TEXT,
    plate TEXT,
    color TEXT,
    km TEXT,
    notes TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_vehicles_company ON vehicles(companyId);
CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(customerId);
CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate);

CREATE TABLE IF NOT EXISTS service_orders (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    budgetId BIGINT REFERENCES budgets(id),
    customerId BIGINT REFERENCES customers(id),
    vehicleId BIGINT REFERENCES vehicles(id),
    number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aberta',
    priority TEXT NOT NULL DEFAULT 'normal',
    entryDate TEXT,
    expectedDeliveryDate TEXT,
    completedAt TEXT,
    problemDescription TEXT,
    serviceDescription TEXT,
    internalNotes TEXT,
    parts JSONB NOT NULL DEFAULT '[]'::jsonb,
    labor JSONB NOT NULL DEFAULT '[]'::jsonb,
    totalAmount NUMERIC NOT NULL DEFAULT 0,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_service_orders_company ON service_orders(companyId);
CREATE INDEX IF NOT EXISTS idx_service_orders_budget ON service_orders(budgetId);
CREATE INDEX IF NOT EXISTS idx_service_orders_status ON service_orders(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_service_orders_number_company ON service_orders(companyId, number);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parts_inventory (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    brand TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    costPrice NUMERIC NOT NULL DEFAULT 0,
    salePrice NUMERIC NOT NULL DEFAULT 0,
    stockQuantity INTEGER NOT NULL DEFAULT 0,
    serialNumber TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_parts_inventory_company ON parts_inventory(companyId);
CREATE INDEX IF NOT EXISTS idx_parts_inventory_code ON parts_inventory(code);
CREATE INDEX IF NOT EXISTS idx_parts_inventory_description ON parts_inventory(description);

CREATE TABLE IF NOT EXISTS suppliers (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    cnpj TEXT NOT NULL UNIQUE,
    corporateName TEXT NOT NULL,
    tradeName TEXT NOT NULL,
    phone TEXT NOT NULL,
    sellerName TEXT NOT NULL,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_suppliers_company ON suppliers(companyId);
CREATE INDEX IF NOT EXISTS idx_suppliers_cnpj ON suppliers(cnpj);
CREATE INDEX IF NOT EXISTS idx_suppliers_trade_name ON suppliers(tradeName);
CREATE INDEX IF NOT EXISTS idx_suppliers_corporate_name ON suppliers(corporateName);

CREATE TABLE IF NOT EXISTS accounts_payable (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT REFERENCES companies(id),
    description TEXT NOT NULL,
    entryDate TEXT NOT NULL,
    competenceDate TEXT NOT NULL,
    category TEXT NOT NULL,
    invoiceNumber TEXT,
    supplierId BIGINT REFERENCES suppliers(id),
    supplierCnpj TEXT NOT NULL,
    supplierName TEXT NOT NULL,
    amount NUMERIC NOT NULL DEFAULT 0,
    notes TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_accounts_payable_company ON accounts_payable(companyId);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_created ON accounts_payable(createdAt);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_due ON accounts_payable(competenceDate);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_supplier ON accounts_payable(supplierName);

CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT NOT NULL REFERENCES companies(id),
    plan TEXT NOT NULL DEFAULT 'trial',
    status TEXT NOT NULL DEFAULT 'trial',
    billingCycle TEXT NOT NULL DEFAULT 'monthly',
    provider TEXT,
    providerCustomerId TEXT,
    providerSubscriptionId TEXT,
    currentPeriodStart TEXT,
    currentPeriodEnd TEXT,
    trialEndsAt TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_company ON subscriptions(companyId);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    companyId BIGINT NOT NULL REFERENCES companies(id),
    subscriptionId BIGINT REFERENCES subscriptions(id),
    provider TEXT,
    providerPaymentId TEXT,
    amount NUMERIC NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    paidAt TEXT,
    createdAt TEXT,
    updatedAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_payments_company ON payments(companyId);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

CREATE TABLE IF NOT EXISTS platform_audit_log (
    id BIGSERIAL PRIMARY KEY,
    actorUserId BIGINT REFERENCES users(id),
    actorEmail TEXT,
    action TEXT NOT NULL,
    targetType TEXT NOT NULL,
    targetId BIGINT,
    targetCompanyId BIGINT REFERENCES companies(id),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    createdAt TEXT
);

CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON platform_audit_log(createdAt);
CREATE INDEX IF NOT EXISTS idx_platform_audit_company ON platform_audit_log(targetCompanyId);

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260609_web_saas_baseline', now()::text)
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260609_db_sessions', now()::text)
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, appliedAt)
VALUES ('20260609_login_audit', now()::text)
ON CONFLICT (version) DO NOTHING;

COMMIT;
