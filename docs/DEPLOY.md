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

## Estado atual

O sistema já possui:

- Configuração por ambiente via `.env`.
- Hash de senha com PBKDF2 e migração automática de hashes legados no login.
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
- Configurar volume persistente para `SQLITE_PATH`.
- Para simular staging local, usar `docker compose up --build`.
- Rodar backup manual com `python scripts/backup_sqlite.py` antes de testes destrutivos.
- Validar schema com `python scripts/validate_schema.py`.
- Rodar smoke test com `python scripts/smoke_api.py`.
- Ativar HTTPS na plataforma.
- Usar dados fictícios.
- Testar login, multiempresa, planos, orçamento, OS, financeiro e estoque.

## Checklist de produção

- Migrar para PostgreSQL gerenciado.
- Criar rotina de backup e restauração.
- Configurar Mercado Pago em produção.
- Ativar webhook de assinatura.
- Ativar domínio próprio e HTTPS.
- Rodar teste de isolamento multiempresa.
- Rodar teste de restauração de backup.
