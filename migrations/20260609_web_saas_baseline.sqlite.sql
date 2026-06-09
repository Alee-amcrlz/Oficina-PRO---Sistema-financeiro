-- SQLite schema snapshot for Oficina Pro Web SaaS baseline.
-- Generated from the local homologation database. Do not edit manually without updating migrations.

-- table: accounts_payable
CREATE TABLE accounts_payable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                entryDate TEXT NOT NULL,
                competenceDate TEXT NOT NULL,
                category TEXT NOT NULL,
                invoiceNumber TEXT,
                supplierId INTEGER,
                supplierCnpj TEXT NOT NULL,
                supplierName TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                notes TEXT,
                createdAt TEXT,
                updatedAt TEXT, companyId INTEGER,
                FOREIGN KEY (supplierId) REFERENCES suppliers(id)
            );

-- table: app_settings
CREATE TABLE app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

-- table: budgets
CREATE TABLE budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId INTEGER NOT NULL,
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
                parts TEXT NOT NULL DEFAULT '[]',
                labor TEXT NOT NULL DEFAULT '[]',
                description TEXT,
                laborValue REAL NOT NULL DEFAULT 0,
                partsValue REAL NOT NULL DEFAULT 0,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'pendente',
                approvedAt TEXT,
                createdAt TEXT,
                updatedAt TEXT
            , companyId INTEGER);

-- table: companies
CREATE TABLE companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                document TEXT,
                phone TEXT,
                ownerUserId INTEGER,
                createdAt TEXT,
                updatedAt TEXT
            );

-- table: customers
CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
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

-- table: login_audit
CREATE TABLE login_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                ipAddress TEXT,
                userAgent TEXT,
                createdAt REAL NOT NULL
            );

-- table: parts_inventory
CREATE TABLE parts_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                costPrice REAL NOT NULL DEFAULT 0,
                salePrice REAL NOT NULL DEFAULT 0,
                stockQuantity INTEGER NOT NULL DEFAULT 0,
                serialNumber TEXT,
                createdAt TEXT,
                updatedAt TEXT
            , companyId INTEGER);

-- table: payments
CREATE TABLE payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER NOT NULL,
                subscriptionId INTEGER,
                provider TEXT,
                providerPaymentId TEXT,
                amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                paidAt TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (companyId) REFERENCES companies(id),
                FOREIGN KEY (subscriptionId) REFERENCES subscriptions(id)
            );

-- table: platform_audit_log
CREATE TABLE platform_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actorUserId INTEGER,
                actorEmail TEXT,
                action TEXT NOT NULL,
                targetType TEXT NOT NULL,
                targetId INTEGER,
                targetCompanyId INTEGER,
                details TEXT NOT NULL DEFAULT '{}',
                createdAt TEXT,
                FOREIGN KEY (actorUserId) REFERENCES users(id),
                FOREIGN KEY (targetCompanyId) REFERENCES companies(id)
            );

-- table: schema_migrations
CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                appliedAt TEXT NOT NULL
            );

-- table: service_orders
CREATE TABLE service_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                budgetId INTEGER,
                customerId INTEGER,
                vehicleId INTEGER,
                number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'aberta',
                priority TEXT NOT NULL DEFAULT 'normal',
                entryDate TEXT,
                expectedDeliveryDate TEXT,
                completedAt TEXT,
                problemDescription TEXT,
                serviceDescription TEXT,
                internalNotes TEXT,
                parts TEXT NOT NULL DEFAULT '[]',
                labor TEXT NOT NULL DEFAULT '[]',
                totalAmount REAL NOT NULL DEFAULT 0,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (budgetId) REFERENCES budgets(id),
                FOREIGN KEY (customerId) REFERENCES customers(id),
                FOREIGN KEY (vehicleId) REFERENCES vehicles(id)
            );

-- table: subscriptions
CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER NOT NULL,
                plan TEXT NOT NULL DEFAULT 'trial',
                status TEXT NOT NULL DEFAULT 'trial',
                provider TEXT,
                providerCustomerId TEXT,
                providerSubscriptionId TEXT,
                currentPeriodStart TEXT,
                currentPeriodEnd TEXT,
                trialEndsAt TEXT,
                createdAt TEXT,
                updatedAt TEXT, billingCycle TEXT NOT NULL DEFAULT 'monthly',
                FOREIGN KEY (companyId) REFERENCES companies(id)
            );

-- table: suppliers
CREATE TABLE suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cnpj TEXT NOT NULL UNIQUE,
                corporateName TEXT NOT NULL,
                tradeName TEXT NOT NULL,
                phone TEXT NOT NULL,
                sellerName TEXT NOT NULL,
                createdAt TEXT,
                updatedAt TEXT
            , companyId INTEGER);

-- table: user_sessions
CREATE TABLE user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tokenHash TEXT NOT NULL UNIQUE,
                userId INTEGER NOT NULL,
                expiresAt REAL NOT NULL,
                createdAt REAL NOT NULL,
                lastSeenAt REAL NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(id)
            );

-- table: users
CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                passwordHash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                accessLevel TEXT NOT NULL DEFAULT 'analista',
                blocked INTEGER NOT NULL DEFAULT 0,
                createdAt TEXT,
                updatedAt TEXT
            , companyId INTEGER, isPlatformAdmin INTEGER NOT NULL DEFAULT 0);

-- table: vehicles
CREATE TABLE vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                customerId INTEGER,
                brand TEXT,
                model TEXT,
                year TEXT,
                plate TEXT,
                color TEXT,
                km TEXT,
                notes TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (customerId) REFERENCES customers(id)
            );

-- index: idx_accounts_payable_company
CREATE INDEX idx_accounts_payable_company ON accounts_payable(companyId);

-- index: idx_accounts_payable_created
CREATE INDEX idx_accounts_payable_created ON accounts_payable(createdAt);

-- index: idx_accounts_payable_due
CREATE INDEX idx_accounts_payable_due ON accounts_payable(competenceDate);

-- index: idx_accounts_payable_supplier
CREATE INDEX idx_accounts_payable_supplier ON accounts_payable(supplierName COLLATE NOCASE);

-- index: idx_budgets_approved
CREATE INDEX idx_budgets_approved ON budgets(approvedAt);

-- index: idx_budgets_company
CREATE INDEX idx_budgets_company ON budgets(companyId);

-- index: idx_budgets_created
CREATE INDEX idx_budgets_created ON budgets(createdAt);

-- index: idx_budgets_status
CREATE INDEX idx_budgets_status ON budgets(status);

-- index: idx_budgets_user
CREATE INDEX idx_budgets_user ON budgets(userId);

-- index: idx_customers_company
CREATE INDEX idx_customers_company ON customers(companyId);

-- index: idx_customers_name
CREATE INDEX idx_customers_name ON customers(name COLLATE NOCASE);

-- index: idx_login_audit_created
CREATE INDEX idx_login_audit_created ON login_audit(createdAt);

-- index: idx_login_audit_login_created
CREATE INDEX idx_login_audit_login_created ON login_audit(login, createdAt);

-- index: idx_parts_inventory_code
CREATE INDEX idx_parts_inventory_code ON parts_inventory(code);

-- index: idx_parts_inventory_company
CREATE INDEX idx_parts_inventory_company ON parts_inventory(companyId);

-- index: idx_parts_inventory_description
CREATE INDEX idx_parts_inventory_description ON parts_inventory(description COLLATE NOCASE);

-- index: idx_payments_company
CREATE INDEX idx_payments_company ON payments(companyId);

-- index: idx_payments_status
CREATE INDEX idx_payments_status ON payments(status);

-- index: idx_platform_audit_company
CREATE INDEX idx_platform_audit_company ON platform_audit_log(targetCompanyId);

-- index: idx_platform_audit_created
CREATE INDEX idx_platform_audit_created ON platform_audit_log(createdAt);

-- index: idx_service_orders_budget
CREATE INDEX idx_service_orders_budget ON service_orders(budgetId);

-- index: idx_service_orders_company
CREATE INDEX idx_service_orders_company ON service_orders(companyId);

-- index: idx_service_orders_number_company
CREATE UNIQUE INDEX idx_service_orders_number_company ON service_orders(companyId, number);

-- index: idx_service_orders_status
CREATE INDEX idx_service_orders_status ON service_orders(status);

-- index: idx_subscriptions_company
CREATE INDEX idx_subscriptions_company ON subscriptions(companyId);

-- index: idx_subscriptions_status
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- index: idx_suppliers_cnpj
CREATE INDEX idx_suppliers_cnpj ON suppliers(cnpj);

-- index: idx_suppliers_company
CREATE INDEX idx_suppliers_company ON suppliers(companyId);

-- index: idx_suppliers_corporate_name
CREATE INDEX idx_suppliers_corporate_name ON suppliers(corporateName COLLATE NOCASE);

-- index: idx_suppliers_trade_name
CREATE INDEX idx_suppliers_trade_name ON suppliers(tradeName COLLATE NOCASE);

-- index: idx_user_sessions_expires
CREATE INDEX idx_user_sessions_expires ON user_sessions(expiresAt);

-- index: idx_user_sessions_user
CREATE INDEX idx_user_sessions_user ON user_sessions(userId);

-- index: idx_users_company
CREATE INDEX idx_users_company ON users(companyId);

-- index: idx_users_username
CREATE UNIQUE INDEX idx_users_username
                ON users(lower(username))
                WHERE username IS NOT NULL AND trim(username) <> '';

-- index: idx_vehicles_company
CREATE INDEX idx_vehicles_company ON vehicles(companyId);

-- index: idx_vehicles_customer
CREATE INDEX idx_vehicles_customer ON vehicles(customerId);

-- index: idx_vehicles_plate
CREATE INDEX idx_vehicles_plate ON vehicles(plate COLLATE NOCASE);
