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
- `MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS`: janela máxima aceita para timestamp de webhook assinado.
- `MARKETING_SITE_URL`: URL opcional do site de divulgação autorizado a enviar leads públicos.

## Estado atual

O sistema já possui:

- Configuração por ambiente via `.env`.
- Hash de senha com PBKDF2 e migração automática de hashes legados no login.
- Política mínima de 12 caracteres para senhas novas de oficinas e usuários.
- Sessões persistidas no banco com hash do token.
- Revogação de sessões em troca de senha, bloqueio e exclusão de usuário.
- Headers HTTP de segurança com CSP, bloqueio de iframe externo e HSTS em produção HTTPS.
- Auditoria de tentativas de login com IP, user-agent, motivo e bloqueio temporário por excesso de falhas.
- Usuário administrador inicial configurável por ambiente.
- Primeira camada de runtime PostgreSQL via `DATABASE_URL`.
- Isolamento multiempresa por `companyId` nas rotas principais.
- Planos comerciais e bloqueio de recursos por plano.
- Painel Master com auditoria.
- Painel Master sem exposição de totais financeiros operacionais das oficinas.
- Fluxo operacional com clientes, veículos, orçamento e OS.
- Solicitação de contratação/alteração de plano pelo cliente com rastreio no Painel Master.
- Entrada segura de webhook Mercado Pago com validação HMAC e registro idempotente dos eventos.
- Conciliação inicial para ativar assinatura apenas quando o webhook/preapproval vier aprovado ou autorizado.
- Runner de migrações SQL pendentes com `python scripts/apply_migrations.py`.
- Integração pública para site de divulgação listar planos e enviar leads sem acionar cobrança.

## Próxima fronteira técnica

O próximo passo externo é criar o staging no Render a partir de `render.yaml`, preencher os segredos e validar a URL pública com os smokes.

Depois do staging online, use `docs/OPERACAO_SAAS.md` como rotina de monitoramento, backup, suporte e incidentes.

Para preparar o futuro site de divulgação, use `docs/SITE_DIVULGACAO.md`. Essa integração deve permanecer com `BILLING_PROVIDER=manual` em staging para não gerar cobrança.

Antes de criar ou promover qualquer ambiente online, rode:

```powershell
python scripts/release_check.py
```

Esse comando junta preflight, travas de runtime, sintaxe, schema, governança de migrações, fila de migrações, exportação SQLite e dry-run do pacote de importação para PostgreSQL.

Se o Node.js não estiver no `PATH`, defina `NODE_BIN` apontando para o executável antes de rodar o release check.

Para gerar valores fortes antes de preencher o painel do provedor:

```powershell
python scripts/generate_deploy_secrets.py --admin-email "admin@seudominio.com" --admin-username "admin_oficina_pro" --public-url "https://oficina-pro-staging.onrender.com"
```

Para staging com sandbox Mercado Pago, use `--mercadopago`; o script mantém `APP_ENV=staging`, muda `BILLING_PROVIDER=mercadopago` e imprime o campo para preencher o token de teste.

Para produção, use `--production`; o script muda `APP_ENV` para `production` e exige Mercado Pago como provedor de cobrança.

## Checklist de staging

- Configurar `APP_ENV=staging`.
- Configurar `HOST=0.0.0.0`.
- Configurar `DEFAULT_ADMIN_EMAIL` com e-mail administrativo real.
- Configurar `DEFAULT_ADMIN_USERNAME` com usuário administrativo exclusivo, diferente de `master`.
- Configurar `DEFAULT_ADMIN_PASSWORD` com senha forte e exclusiva.
- Gerar `DEFAULT_ADMIN_PASSWORD` e `MERCADOPAGO_WEBHOOK_SECRET` com `python scripts/generate_deploy_secrets.py`.
- Para Render, usar `render.yaml` como blueprint de staging com PostgreSQL gerenciado e preencher os segredos solicitados no painel.
- O blueprint roda `python scripts/preflight.py && python scripts/validate_migrations.py && python scripts/apply_migrations.py` antes de cada deploy.
- Manter `autoDeployTrigger: "off"` no primeiro staging para revisar cada deploy manualmente.
- Confirmar que `DATABASE_URL` foi preenchido automaticamente pelo banco Render Postgres.
- Confirmar `BILLING_PROVIDER=manual` para staging sem cobrança real, ou `mercadopago` para sandbox de pagamento.
- Se já houver site de divulgação em teste, configurar `MARKETING_SITE_URL` com a URL pública dele.
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
- Seguir a rotina operacional de `docs/OPERACAO_SAAS.md`.

## Checklist de produção

- Migrar para PostgreSQL gerenciado.
- Configurar `DATABASE_URL` com PostgreSQL gerenciado antes de liberar `APP_ENV=production`.
- Ensaiar migrações/importação com `scripts/apply_migrations.py` e `scripts/import_jsonl_to_postgres.py`.
- Criar rotina de backup e restauração.
- Manter backup gerenciado do PostgreSQL e exportação lógica periódica com `python scripts/export_postgres_jsonl.py`.
- Configurar Mercado Pago em produção.
- Gerar os segredos de produção com `python scripts/generate_deploy_secrets.py --production`.
- Ativar webhook em `{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago`.
- Confirmar `BILLING_PROVIDER=mercadopago`, `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET` e `PUBLIC_APP_URL=https://...`.
- Ativar domínio próprio e HTTPS.
- Rodar teste de isolamento multiempresa.
- Rodar teste de restauração de backup.
- Seguir a rotina operacional de `docs/OPERACAO_SAAS.md`.
