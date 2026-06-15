# Deploy gratuito: Neon + Render

Este guia publica o Oficina Pro como staging/demo online usando Neon PostgreSQL Free e Render Free Web Service.

## Objetivo

- Colocar o sistema no ar para homologação.
- Usar PostgreSQL real desde o começo.
- Evitar SQLite em filesystem efêmero.
- Não ativar cobrança real.
- Manter caminho simples para upgrade pago depois.

## Contas necessárias

- Neon: https://console.neon.tech/signup
- Render: https://dashboard.render.com/register

Não compartilhe senha das contas no repositório. Sempre que possível, configure segredos diretamente nos painéis.

## 1. Criar banco no Neon

1. Criar projeto no Neon.
2. Criar banco PostgreSQL para staging.
3. Copiar a connection string do banco.
4. Usar a connection string como `DATABASE_URL` no Render.

O banco gratuito é suficiente para homologação inicial. Para produção, fazer upgrade no próprio Neon ou migrar para outro PostgreSQL pago com `pg_dump` e troca de `DATABASE_URL`.

## 2. Criar Web Service no Render

1. Criar novo Blueprint ou Web Service conectado ao GitHub.
2. Selecionar o repositório do Oficina Pro.
3. Usar branch `codex/oficina-pro-v1.1`.
4. Usar o arquivo `render.free.yaml`.
5. Manter deploy manual no primeiro ambiente.

## 3. Variáveis obrigatórias no Render

Gerar segredos fortes:

```powershell
python scripts/generate_deploy_secrets.py --admin-email "admin@seudominio.com" --admin-username "admin_oficina_pro" --public-url "https://sua-url-render.onrender.com"
```

Configurar no Render:

```text
APP_ENV=staging
HOST=0.0.0.0
PORT=10000
DATABASE_URL=postgresql://...
PUBLIC_APP_URL=https://sua-url-render.onrender.com
DEFAULT_ADMIN_USERNAME=admin_oficina_pro
DEFAULT_ADMIN_EMAIL=admin@seudominio.com
DEFAULT_ADMIN_PASSWORD=senha-gerada
BILLING_PROVIDER=manual
MERCADOPAGO_WEBHOOK_SECRET=segredo-gerado
MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS=600
```

## 4. Primeiro deploy

O deploy executa:

```text
python scripts/preflight.py
python scripts/validate_migrations.py
python scripts/apply_migrations.py
```

Depois do deploy, validar:

```text
https://sua-url-render.onrender.com/api/health
https://sua-url-render.onrender.com/api/ready
```

## 5. Verificação pública

No computador local:

```powershell
$env:STAGING_BASE_URL="https://sua-url-render.onrender.com"
$env:SMOKE_MASTER_LOGIN="admin@seudominio.com"
$env:SMOKE_MASTER_PASSWORD="senha-gerada"
$env:MERCADOPAGO_WEBHOOK_SECRET="mesmo-segredo-configurado-no-render"
python scripts/verify_staging.py
```

## 6. Upgrade futuro

### Neon Free para Neon pago

Impacto baixo:

- manter PostgreSQL;
- manter schema;
- manter aplicação;
- fazer upgrade do plano;
- validar `DATABASE_URL` se o Neon gerar nova string;
- rodar `scripts/verify_staging.py`.

### Neon para outro PostgreSQL pago

Impacto médio:

- exportar com `pg_dump`;
- restaurar no novo provedor;
- trocar `DATABASE_URL`;
- rodar migrações pendentes;
- rodar `scripts/verify_staging.py`;
- planejar janela curta de manutenção.

## Observações de segurança

- Não usar dados reais de clientes no plano gratuito.
- Não ativar `BILLING_PROVIDER=mercadopago` no primeiro staging.
- Não salvar tokens do Mercado Pago no GitHub.
- Usar HTTPS público do Render.
- Tratar staging como ambiente descartável até validarmos backup e restauração.
