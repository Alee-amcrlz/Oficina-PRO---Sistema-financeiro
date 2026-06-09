# Migrações

O projeto ainda mantém criação automática de schema em `server.py` para preservar a homologação local.

A partir desta etapa, o banco registra a versão:

- `20260609_web_saas_baseline`
- `20260609_db_sessions`

O arquivo `20260609_web_saas_baseline.sqlite.sql` é um snapshot auditável do schema SQLite atual.

O arquivo `20260609_web_saas_baseline.postgres.sql` é a baseline inicial planejada para PostgreSQL gerenciado.

Use `python scripts/validate_schema.py` para conferir se o banco ativo tem as tabelas e colunas críticas.

Antes de produção comercial, o próximo passo é transformar o schema atual em migrações SQL separadas para PostgreSQL.

## Regra

- Não editar dados de produção manualmente.
- Toda alteração estrutural deve ganhar uma nova versão.
- Antes de aplicar em produção, aplicar em staging e testar restauração de backup.
