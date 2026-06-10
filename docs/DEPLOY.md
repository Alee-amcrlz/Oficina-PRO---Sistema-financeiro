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
- `LOGIN_MAX_ATTEMPTS`: quantidade de falhas permitidas na janela de segurança.
- `LOGIN_WINDOW_SECONDS`: janela usada para contar falhas de login.
- `LOGIN_LOCK_SECONDS`: tempo de bloqueio temporário após excesso de falhas.
- `DEFAULT_ADMIN_NAME`: nome do administrador inicial.
- `DEFAULT_ADMIN_USERNAME`: usuário curto do administrador inicial.
- `DEFAULT_ADMIN_EMAIL`: e-mail do administrador inicial.
- `DEFAULT_ADMIN_PASSWORD`: senha do administrador inicial.

## Estado atual

O sistema já possui:

- Configuração por ambiente via `.env`.
- Hash de senha com PBKDF2 e migração automática de hashes legados no login.
- Sessões persistidas no banco com hash do token.
- Auditoria de tentativas de login com IP, user-agent, motivo e bloqueio temporário por excesso de falhas.
- Usuário administrador inicial configurável por ambiente.
- Trava de runtime para impedir produção enquanto o servidor ainda usa SQLite.
- Isolamento multiempresa por `companyId` nas rotas principais.
- Planos comerciais e bloqueio de recursos por plano.
- Painel Master com auditoria.
- Fluxo operacional com clientes, veículos, orçamento e OS.

## Próxima fronteira técnica

Para produção comercial, migrar o banco para PostgreSQL gerenciado antes de clientes reais.

Enquanto isso, um deploy de `staging` pode usar SQLite em disco persistente apenas para testes controlados.

## Checklist de staging

- Configurar `APP_ENV=staging`.
- Configurar `HOST=0.0.0.0`.
- Configurar `DEFAULT_ADMIN_EMAIL` com e-mail administrativo real.
- Configurar `DEFAULT_ADMIN_PASSWORD` com senha forte e exclusiva.
- Configurar volume persistente para `SQLITE_PATH`.
- Para Render, usar `render.yaml` como blueprint de staging e preencher os segredos solicitados no painel.
- Manter `autoDeploy=false` no primeiro staging para revisar cada deploy manualmente.
- Para simular staging local, usar `docker compose up --build`.
- Rodar backup manual com `python scripts/backup_sqlite.py` antes de testes destrutivos.
- Testar restauração em arquivo separado com `python scripts/restore_sqlite_backup.py --latest --target restore-test.db --no-safety-backup`.
- Validar schema com `python scripts/validate_schema.py`.
- Rodar smoke test com `python scripts/smoke_api.py`.
- Rodar smoke test multiempresa com `python scripts/smoke_multiempresa.py`.
- Testar bloqueio temporário de login com credenciais inválidas em usuário fictício.
- Ativar HTTPS na plataforma.
- Usar dados fictícios.
- Testar login, multiempresa, planos, orçamento, OS, financeiro e estoque.

## Checklist de produção

- Migrar para PostgreSQL gerenciado.
- Implementar runtime PostgreSQL antes de liberar `APP_ENV=production`.
- Ensaiar baseline/importação com `scripts/apply_postgres_baseline.py` e `scripts/import_jsonl_to_postgres.py`.
- Criar rotina de backup e restauração.
- Configurar Mercado Pago em produção.
- Ativar webhook de assinatura.
- Ativar domínio próprio e HTTPS.
- Rodar teste de isolamento multiempresa.
- Rodar teste de restauração de backup.
