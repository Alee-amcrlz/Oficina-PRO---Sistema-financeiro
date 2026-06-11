import sys

from data_tables import (
    POSTGRES_LOGICAL_EXPORT_EXCLUDED_TABLES,
    POSTGRES_LOGICAL_EXPORT_TABLES,
    SQLITE_MIGRATION_EXCLUDED_TABLES,
    SQLITE_MIGRATION_TABLES,
)


REQUIRED_SQLITE_MIGRATION_TABLES = {
    "companies",
    "users",
    "budgets",
    "customers",
    "vehicles",
    "service_orders",
    "app_settings",
    "parts_inventory",
    "suppliers",
    "accounts_payable",
    "subscriptions",
    "payments",
    "platform_audit_log",
    "schema_migrations",
}

REQUIRED_SQLITE_EXCLUSIONS = {
    "user_sessions",
    "login_audit",
    "billing_checkout_requests",
    "billing_webhook_events",
}

REQUIRED_POSTGRES_LOGICAL_TABLES = REQUIRED_SQLITE_MIGRATION_TABLES | {
    "login_audit",
    "billing_checkout_requests",
    "billing_webhook_events",
}


def no_duplicates(items):
    return len(items) == len(set(items))


def main():
    failures = []
    sqlite_tables = set(SQLITE_MIGRATION_TABLES)
    sqlite_exclusions = set(SQLITE_MIGRATION_EXCLUDED_TABLES)
    postgres_tables = set(POSTGRES_LOGICAL_EXPORT_TABLES)
    postgres_exclusions = set(POSTGRES_LOGICAL_EXPORT_EXCLUDED_TABLES)

    if not no_duplicates(SQLITE_MIGRATION_TABLES):
        failures.append("SQLITE_MIGRATION_TABLES contem duplicidade.")
    if not no_duplicates(POSTGRES_LOGICAL_EXPORT_TABLES):
        failures.append("POSTGRES_LOGICAL_EXPORT_TABLES contem duplicidade.")
    if sqlite_tables != REQUIRED_SQLITE_MIGRATION_TABLES:
        failures.append(f"Pacote SQLite divergente: {sorted(sqlite_tables ^ REQUIRED_SQLITE_MIGRATION_TABLES)}")
    if sqlite_exclusions != REQUIRED_SQLITE_EXCLUSIONS:
        failures.append(f"Exclusoes SQLite divergentes: {sorted(sqlite_exclusions ^ REQUIRED_SQLITE_EXCLUSIONS)}")
    if sqlite_tables & sqlite_exclusions:
        failures.append(f"Tabelas SQLite exportadas e excluidas ao mesmo tempo: {sorted(sqlite_tables & sqlite_exclusions)}")
    if postgres_tables != REQUIRED_POSTGRES_LOGICAL_TABLES:
        failures.append(f"Backup logico PostgreSQL divergente: {sorted(postgres_tables ^ REQUIRED_POSTGRES_LOGICAL_TABLES)}")
    if postgres_exclusions != {"user_sessions"}:
        failures.append(f"Exclusoes PostgreSQL divergentes: {sorted(postgres_exclusions)}")
    if postgres_tables & postgres_exclusions:
        failures.append(f"Tabelas PostgreSQL exportadas e excluidas ao mesmo tempo: {sorted(postgres_tables & postgres_exclusions)}")
    if not sqlite_tables <= postgres_tables:
        failures.append(f"Backup PostgreSQL nao cobre migracao SQLite: {sorted(sqlite_tables - postgres_tables)}")
    for table, reason in {**SQLITE_MIGRATION_EXCLUDED_TABLES, **POSTGRES_LOGICAL_EXPORT_EXCLUDED_TABLES}.items():
        if not str(reason).strip():
            failures.append(f"Exclusao sem justificativa: {table}")

    if failures:
        for failure in failures:
            print(f"[ERRO] {failure}")
        print("\nPolitica de tabelas invalida.")
        return 1

    print("[OK] Politica de exportacao/importacao validada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
