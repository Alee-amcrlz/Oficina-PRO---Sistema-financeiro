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
- O servidor bloqueia `DATABASE_URL` no runtime atual para não fingir PostgreSQL enquanto ainda executa SQLite.
- O servidor bloqueia `APP_ENV=production` até o runtime PostgreSQL real ser implementado e validado.
- A camada SQL ainda usa comandos compatíveis com SQLite.
- Existe baseline PostgreSQL em `migrations/20260609_web_saas_baseline.postgres.sql`.
- Exporte dados de homologação com `python scripts/export_sqlite_jsonl.py`.
- Aplique a baseline em banco PostgreSQL vazio com `python scripts/apply_postgres_baseline.py`.
- Importe uma exportação SQLite JSONL com `python scripts/import_jsonl_to_postgres.py`.

## Ensaio de Migração

1. Criar um banco PostgreSQL vazio em staging.
2. Instalar dependência local apenas para o ensaio: `python -m pip install "psycopg[binary]"`.
3. Configurar `DATABASE_URL` apontando para esse banco.
4. Rodar `python scripts/apply_postgres_baseline.py`.
5. Rodar `python scripts/export_sqlite_jsonl.py`.
6. Validar o pacote exportado com `python scripts/import_jsonl_to_postgres.py --dry-run --export-dir exports/sqlite-export-AAAAMMDD-HHMMSS`.
7. Rodar `python scripts/import_jsonl_to_postgres.py --export-dir exports/sqlite-export-AAAAMMDD-HHMMSS`.
8. Conferir contagens exibidas pelo importador.
9. Rodar smoke tests quando o runtime PostgreSQL do servidor estiver pronto.

Use `--truncate` somente em banco de staging descartável:

```powershell
python scripts/import_jsonl_to_postgres.py --truncate
```

## Decisão

Não vender para clientes reais antes desta migração.

O próximo deploy recomendado é **staging online**, com SQLite em disco persistente, dados fictícios e backup manual/automático.
