# Operacao SaaS

Este guia define como operar o Oficina Pro depois que o staging online estiver criado.

## Objetivo

Manter a plataforma verificavel, recuperavel e segura sem acessar dados operacionais das oficinas fora de necessidade real de suporte.

## Rotina Diaria

- Conferir `/api/health` para confirmar que o processo responde.
- Conferir `/api/ready` para validar banco, schema, migracoes, origem publica e configuracao minima.
- Abrir o Painel Master e revisar:
  - total de oficinas cadastradas;
  - status das assinaturas;
  - contratacoes recentes;
  - pagamentos SaaS;
  - auditoria master.
- Verificar no provedor de hospedagem se houve restart, erro de deploy ou consumo anormal de CPU/memoria.
- Verificar no provedor PostgreSQL se backup gerenciado esta ativo.

## Rotina Antes de Deploy

1. Confirmar GitHub Actions verde na branch.
2. Rodar `python scripts/release_check.py` localmente.
3. Conferir `python scripts/apply_migrations.py --dry-run`.
4. Gerar ou revisar segredos com `python scripts/generate_deploy_secrets.py`.
5. Criar backup gerenciado ou snapshot do banco no provedor.
6. Aplicar deploy primeiro em `staging`.
7. Rodar `python scripts/verify_staging.py` contra a URL publica.
8. Testar login, criacao de oficina, isolamento multiempresa, assinatura, orcamento, OS e financeiro.

## Rotina de Backup

O backup principal em nuvem deve ser o backup gerenciado do PostgreSQL.

Complemento recomendado:

```powershell
python scripts/export_postgres_jsonl.py
```

Tratar o diretorio exportado como segredo. Ele contem dados de oficinas, assinaturas, pagamentos, auditoria, checkout e webhooks. Nao enviar para GitHub nem compartilhar por canais abertos.

## Restauracao

- Restaurar primeiro em staging.
- Validar `/api/ready`.
- Rodar smoke tests de multiempresa e checkout.
- Conferir contagens e dados essenciais no Painel Master.
- Promover para producao somente depois de confirmar que staging esta consistente.

## Monitoramento de Assinaturas

No Painel Master, acompanhar:

- oficinas em `trial`;
- oficinas `active`;
- oficinas `past_due`, `canceled` ou status inesperado;
- tentativas de checkout com `provider_error`;
- webhooks sem confirmacao segura;
- pagamentos SaaS duplicados ou ausentes.

Eventos Mercado Pago aprovados/autorizados devem ativar a assinatura somente quando a confirmacao for segura. Reenvios de webhook nao devem duplicar pagamento.

## Politica de Suporte e Privacidade

O Painel Master nao deve exibir faturamento operacional das oficinas por padrao.

Acesso a valores operacionais da oficina deve ser tratado como suporte excepcional:

- abrir um motivo claro de atendimento;
- acessar apenas o necessario para corrigir relatorio ou duvida do cliente;
- registrar a acao em auditoria;
- evitar exportar dados da oficina;
- nunca usar dados reais em prints, videos, testes ou demonstracoes publicas.

## Incidentes

Em caso de falha de login, webhook, cobranca, banco ou vazamento suspeito:

1. Pausar deploys automaticos.
2. Conferir logs do provedor e `/api/ready`.
3. Revogar ou trocar segredos afetados.
4. Confirmar integridade de `schema_migrations`.
5. Validar backups antes de qualquer restauracao.
6. Registrar o ocorrido no Obsidian e no historico tecnico do projeto.

## Promocao Para Producao

Producao so deve ser liberada quando:

- staging estiver online e validado;
- GitHub Actions estiver verde;
- `APP_ENV=production` usar PostgreSQL gerenciado;
- `BILLING_PROVIDER=mercadopago` estiver configurado;
- `PUBLIC_APP_URL` estiver em HTTPS;
- webhook Mercado Pago estiver ativo;
- rotina de backup e restauracao tiver sido testada;
- credenciais padrao locais nao existirem no ambiente.
