# Migração Para PostgreSQL

O Oficina Pro ainda executa com SQLite para preservar a homologação local.

Para produção comercial SaaS, o banco recomendado é PostgreSQL gerenciado.

## Por Que Migrar

- SQLite não é ideal para múltiplos clientes simultâneos em produção.
- PostgreSQL oferece concorrência, backup gerenciado, métricas e restauração mais robusta.
- Webhooks de pagamento, auditoria e multiempresa precisam de persistência forte.

## Caminho Recomendado

1. Criar banco PostgreSQL em ambiente de staging.
2. Converter o schema atual para migrações SQL versionadas.
3. Criar script de exportação do SQLite.
4. Criar script de importação para PostgreSQL.
5. Rodar smoke tests de multiempresa.
6. Repetir em produção somente depois de backup validado.

## Estado Atual

- O schema atual registra a baseline `20260609_web_saas_baseline`.
- O `.env` já prevê `DATABASE_URL`.
- O servidor bloqueia `APP_ENV=production` sem `DATABASE_URL`.
- A camada SQL ainda usa comandos compatíveis com SQLite.
- Existe baseline PostgreSQL em `migrations/20260609_web_saas_baseline.postgres.sql`.
- Exporte dados de homologação com `python scripts/export_sqlite_jsonl.py`.

## Decisão

Não vender para clientes reais antes desta migração.

O próximo deploy recomendado é **staging online**, com SQLite em disco persistente, dados fictícios e backup manual/automático.
