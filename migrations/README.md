# Migrações

O projeto ainda mantém criação automática de schema em `server.py` para preservar a homologação local.

A partir desta etapa, o banco registra a versão:

- `20260609_web_saas_baseline`
- `20260609_db_sessions`
- `20260609_login_audit`
- `20260610_billing_webhooks`
- `20260610_billing_checkout_requests`

O arquivo `20260609_web_saas_baseline.sqlite.sql` é um snapshot auditável do schema SQLite atual.

O arquivo `20260609_web_saas_baseline.postgres.sql` é a baseline inicial planejada para PostgreSQL gerenciado.

As migrações incrementais atuais adicionam sessões persistidas no banco, auditoria de login, solicitações de checkout de assinatura e registro idempotente de webhooks de cobrança.

Use `python scripts/validate_migrations.py` para conferir se os arquivos SQL versionados estão alinhados com `server.py` e `scripts/validate_schema.py`.

Use `python scripts/apply_migrations.py` para aplicar somente migrações pendentes no SQLite local ou no PostgreSQL configurado em `DATABASE_URL`.

Use `python scripts/validate_schema.py` para conferir se o banco ativo tem as tabelas e colunas críticas.

Antes de produção comercial, toda alteração nova de schema deve continuar entrando como migração SQL versionada para SQLite e PostgreSQL.

## Regra

- Não editar dados de produção manualmente.
- Toda alteração estrutural deve ganhar uma nova versão.
- Toda nova versão deve ter arquivos `.sqlite.sql` e `.postgres.sql`.
- Atualizar `REQUIRED_SCHEMA_MIGRATIONS` em `server.py` e `REQUIRED_MIGRATIONS` em `scripts/validate_schema.py`.
- Rodar `python scripts/validate_migrations.py` antes de commit/push.
- Rodar `python scripts/apply_migrations.py --dry-run` para conferir pendências antes de deploy.
- Antes de aplicar em produção, aplicar em staging e testar restauração de backup.
