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
- O servidor possui uma primeira camada de runtime PostgreSQL quando `DATABASE_URL` está configurado.
- `APP_ENV=production` exige `DATABASE_URL` com PostgreSQL gerenciado.
- A camada de compatibilidade traduz placeholders e alguns trechos SQLite usados pelas rotas atuais.
- O CI sobe um PostgreSQL real e roda smoke API/multiempresa com `DATABASE_URL`.
- O CI também valida checkout de assinatura e entrada de webhook Mercado Pago em PostgreSQL.
- `/api/ready` valida conexão, tabelas, colunas críticas e migrações aplicadas.
- `/api/ready` também valida configuração mínima de cobrança em produção.
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
9. Subir o servidor com `DATABASE_URL` e rodar smoke tests contra o PostgreSQL de staging.
10. Rodar `python scripts/smoke_billing_checkout.py`.
11. Rodar `python scripts/smoke_billing_webhook.py` com `MERCADOPAGO_WEBHOOK_SECRET` configurado.

Use `--truncate` somente em banco de staging descartável:

```powershell
python scripts/import_jsonl_to_postgres.py --truncate
```

## Decisão

Não vender para clientes reais antes desta migração.

O próximo deploy recomendado é **staging online com PostgreSQL gerenciado**. Depois de criar a URL pública, configure `STAGING_BASE_URL`, `SMOKE_MASTER_LOGIN` e `SMOKE_MASTER_PASSWORD`, então rode `python scripts/verify_staging.py`.
