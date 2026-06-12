SQLITE_MIGRATION_TABLES = [
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
]

SQLITE_MIGRATION_EXCLUDED_TABLES = {
    "user_sessions": "Sessoes ativas nao migram para reduzir risco de reaproveitamento de token.",
    "login_audit": "Auditoria de login pode conter IP/user-agent e nao deve ser carregada entre ambientes.",
    "billing_checkout_requests": "Tentativas de checkout sao trilha operacional do ambiente.",
    "billing_webhook_events": "Eventos de webhook sao trilha operacional do ambiente.",
    "marketing_leads": "Leads do site sao trilha comercial do ambiente e nao devem ser carregados entre homologacao e producao.",
}

POSTGRES_LOGICAL_EXPORT_TABLES = [
    "companies",
    "users",
    "login_audit",
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
    "billing_checkout_requests",
    "billing_webhook_events",
    "marketing_leads",
    "platform_audit_log",
    "schema_migrations",
]

POSTGRES_LOGICAL_EXPORT_EXCLUDED_TABLES = {
    "user_sessions": "Sessoes ativas nao entram em backup logico para reduzir risco de reaproveitamento de token.",
}
