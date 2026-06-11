# Deploy do Oficina Pro

Este documento descreve o caminho seguro para publicar o Oficina Pro como Web SaaS.

## Ambientes

- `local`: desenvolvimento no computador.
- `staging`: homologação online com dados fictícios.
- `production`: produção com clientes reais.

## Variáveis

Copie `.env.example` para `.env` no ambiente local. Em nuvem, configure as mesmas variáveis no painel da plataforma.

Variáveis principais:

- `APP_ENV`: `local`, `staging` ou `production`.
- `HOST`: use `0.0.0.0` em deploy.
- `PORT`: porta exposta pela plataforma.
- `SQLITE_PATH`: caminho do SQLite enquanto estivermos em homologação.
- `SESSION_TTL_SECONDS`: duração da sessão.
- `PASSWORD_HASH_ITERATIONS`: custo do PBKDF2.
- `MIN_USER_PASSWORD_LENGTH`: tamanho mínimo para senhas novas de oficinas e usuários; mantenha 12+ em staging/produção.
- `LOGIN_MAX_ATTEMPTS`: quantidade de falhas permitidas na janela de segurança.
- `LOGIN_WINDOW_SECONDS`: janela usada para contar falhas de login.
- `LOGIN_LOCK_SECONDS`: tempo de bloqueio temporário após excesso de falhas.
- `DEFAULT_ADMIN_NAME`: nome do administrador inicial.
- `DEFAULT_ADMIN_USERNAME`: usuário curto do administrador inicial; em staging/produção não pode ser `master`.
- `DEFAULT_ADMIN_EMAIL`: e-mail do administrador inicial.
- `DEFAULT_ADMIN_PASSWORD`: senha do administrador inicial; em staging/produção deve ter 12+ caracteres e não pode ser a padrão local.
- `BILLING_PROVIDER`: `manual` em homologação ou `mercadopago` em produção.
- `PUBLIC_APP_URL`: URL pública do sistema; obrigatória em staging/produção e usada para validar origem de escritas no navegador.
- `MERCADOPAGO_ACCESS_TOKEN`: token do Mercado Pago.
- `MERCADOPAGO_WEBHOOK_SECRET`: segredo usado para validar webhook.

## Estado atual

O sistema já possui:

- Configuração por ambiente via `.env`.
- Hash de senha com PBKDF2 e migração automática de hashes legados no login.
- Política mínima de 12 caracteres para senhas novas de oficinas e usuários.
- Sessões persistidas no banco com hash do token.
- Auditoria de tentativas de login com IP, user-agent, motivo e bloqueio temporário por excesso de falhas.
- Usuário administrador inicial configurável por ambiente.
- Primeira camada de runtime PostgreSQL via `DATABASE_URL`.
- Isolamento multiempresa por `companyId` nas rotas principais.
- Planos comerciais e bloqueio de recursos por plano.
- Painel Master com auditoria.
- Fluxo operacional com clientes, veículos, orçamento e OS.
- Solicitação de contratação/alteração de plano pelo cliente com rastreio no Painel Master.
- Entrada segura de webhook Mercado Pago com validação HMAC e registro idempotente dos eventos.
- Conciliação inicial para ativar assinatura apenas quando o webhook/preapproval vier aprovado ou autorizado.

## Próxima fronteira técnica

O próximo passo externo é criar o staging no Render a partir de `render.yaml`, preencher os segredos e validar a URL pública com os smokes.

Antes de criar ou promover qualquer ambiente online, rode:

```powershell
python scripts/release_check.py
```

Esse comando junta preflight, travas de runtime, sintaxe, schema, governança de migrações, exportação SQLite e dry-run do pacote de importação para PostgreSQL.

Se o Node.js não estiver no `PATH`, defina `NODE_BIN` apontando para o executável antes de rodar o release check.

## Checklist de staging

- Configurar `APP_ENV=staging`.
- Configurar `HOST=0.0.0.0`.
- Configurar `DEFAULT_ADMIN_EMAIL` com e-mail administrativo real.
- Configurar `DEFAULT_ADMIN_USERNAME` com usuário administrativo exclusivo, diferente de `master`.
- Configurar `DEFAULT_ADMIN_PASSWORD` com senha forte e exclusiva.
- Para Render, usar `render.yaml` como blueprint de staging com PostgreSQL gerenciado e preencher os segredos solicitados no painel.
- O blueprint roda `python scripts/preflight.py && python scripts/validate_migrations.py` antes de cada deploy.
- Manter `autoDeployTrigger: "off"` no primeiro staging para revisar cada deploy manualmente.
- Confirmar que `DATABASE_URL` foi preenchido automaticamente pelo banco Render Postgres.
- Confirmar `BILLING_PROVIDER=manual` para staging sem cobrança real, ou `mercadopago` para sandbox de pagamento.
- Se configurar `MERCADOPAGO_WEBHOOK_SECRET`, usar segredo aleatório com pelo menos 32 caracteres.
- Se usar sandbox Mercado Pago, configurar webhook para `{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago`.
- Testar contratação pelo painel **Minha assinatura** e conferir a solicitação em **Contratações recentes** no Painel Master.
- Confirmar no sandbox que eventos sem status aprovado/autorizado não liberam escrita.
- Conferir no GitHub Actions o job `postgres-runtime` antes de promover staging/produção.
- Rodar `python scripts/release_check.py` localmente antes de acionar o deploy manual.
- Conferir `/api/ready` retornando `ok=true` na URL pública.
- Confirmar que POST/PUT/DELETE vindos de outro domínio são bloqueados; `python scripts/verify_staging.py` já testa esse bloqueio com `scripts/smoke_origin_guard.py`.
- Rodar verificação pública:

```powershell
$env:STAGING_BASE_URL="https://oficina-pro-staging.onrender.com"
$env:SMOKE_MASTER_LOGIN="admin@seudominio.com"
$env:SMOKE_MASTER_PASSWORD="senha-forte-do-staging"
$env:MERCADOPAGO_WEBHOOK_SECRET="mesmo-segredo-configurado-no-staging-com-32-caracteres"
python scripts/verify_staging.py
```

- Testar bloqueio temporário de login com credenciais inválidas em usuário fictício.
- Ativar HTTPS na plataforma.
- Usar dados fictícios.
- Testar login, multiempresa, planos, orçamento, OS, financeiro e estoque.

## Checklist de produção

- Migrar para PostgreSQL gerenciado.
- Configurar `DATABASE_URL` com PostgreSQL gerenciado antes de liberar `APP_ENV=production`.
- Ensaiar baseline/importação com `scripts/apply_postgres_baseline.py` e `scripts/import_jsonl_to_postgres.py`.
- Criar rotina de backup e restauração.
- Manter backup gerenciado do PostgreSQL e exportação lógica periódica com `python scripts/export_postgres_jsonl.py`.
- Configurar Mercado Pago em produção.
- Ativar webhook em `{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago`.
- Confirmar `BILLING_PROVIDER=mercadopago`, `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET` e `PUBLIC_APP_URL=https://...`.
- Ativar domínio próprio e HTTPS.
- Rodar teste de isolamento multiempresa.
- Rodar teste de restauração de backup.
