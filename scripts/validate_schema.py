from pathlib import Path
import os
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_COLUMNS = {
    "companies": {"id", "name", "ownerUserId", "createdAt", "updatedAt"},
    "users": {"id", "companyId", "isPlatformAdmin", "email", "passwordHash", "role", "accessLevel", "blocked"},
    "user_sessions": {"id", "tokenHash", "userId", "expiresAt", "createdAt", "lastSeenAt"},
    "login_audit": {"id", "login", "success", "reason", "ipAddress", "userAgent", "createdAt"},
    "budgets": {"id", "companyId", "userId", "clientName", "parts", "labor", "status", "approvedAt"},
    "customers": {"id", "companyId", "name", "email", "phone"},
    "vehicles": {"id", "companyId", "customerId", "plate", "brand", "model"},
    "service_orders": {"id", "companyId", "budgetId", "customerId", "vehicleId", "number", "status", "parts", "labor", "totalAmount"},
    "parts_inventory": {"id", "companyId", "code", "description", "stockQuantity"},
    "suppliers": {"id", "companyId", "cnpj", "corporateName", "tradeName"},
    "accounts_payable": {"id", "companyId", "description", "supplierName", "amount"},
    "subscriptions": {"id", "companyId", "plan", "status", "billingCycle", "currentPeriodEnd"},
    "payments": {"id", "companyId", "subscriptionId", "provider", "amount", "status"},
    "billing_checkout_requests": {"id", "companyId", "subscriptionId", "plan", "billingCycle", "provider", "amount", "status"},
    "billing_webhook_events": {"id", "provider", "eventId", "eventType", "action", "resourceId", "requestId", "payload", "receivedAt"},
    "platform_audit_log": {"id", "actorUserId", "action", "targetCompanyId", "details", "createdAt"},
    "marketing_leads": {"id", "name", "email", "plan", "billingCycle", "status", "createdAt"},
    "schema_migrations": {"version", "appliedAt"},
}

REQUIRED_MIGRATIONS = {
    "20260609_web_saas_baseline",
    "20260609_db_sessions",
    "20260609_login_audit",
    "20260610_billing_webhooks",
    "20260610_billing_checkout_requests",
    "20260612_marketing_leads",
}


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env_file(ROOT / ".env")
    db_path = Path(os.environ.get("SQLITE_PATH", ROOT / "oficina.db"))
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    if not db_path.exists():
        print(f"[ERRO] Banco não encontrado: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    failures = []

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    for table, expected_columns in REQUIRED_COLUMNS.items():
        if table not in tables:
            failures.append(f"Tabela ausente: {table}")
            continue
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        missing = expected_columns - columns
        if missing:
            failures.append(f"Colunas ausentes em {table}: {', '.join(sorted(missing))}")

    if "schema_migrations" in tables:
        migrations = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        missing_migrations = REQUIRED_MIGRATIONS - migrations
        if missing_migrations:
            failures.append(f"Migrações ausentes: {', '.join(sorted(missing_migrations))}")

    if failures:
        for failure in failures:
            print(f"[ERRO] {failure}")
        print("\nSchema inválido.")
        return 1

    print("[OK] Schema validado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
