# Migrações

O projeto ainda mantém criação automática de schema em `server.py` para preservar a homologação local.

A partir desta etapa, o banco registra a versão:

- `20260609_web_saas_baseline`

Antes de produção comercial, o próximo passo é transformar o schema atual em migrações SQL separadas para PostgreSQL.

## Regra

- Não editar dados de produção manualmente.
- Toda alteração estrutural deve ganhar uma nova versão.
- Antes de aplicar em produção, aplicar em staging e testar restauração de backup.
