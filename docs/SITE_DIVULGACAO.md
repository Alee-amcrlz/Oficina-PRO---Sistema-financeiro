# Integracao com Site de Divulgacao

Este documento prepara a conexao entre o futuro site publico do Oficina Pro e o sistema SaaS.

Nada aqui ativa cobranca real. Em staging, mantenha `BILLING_PROVIDER=manual`.

## Objetivo

O site de divulgacao podera:

- listar planos comerciais;
- enviar leads interessados;
- direcionar o cliente para login ou para contato comercial;
- manter pagamentos reais desligados ate a liberacao de producao.

## Paginas no projeto

- `site.html`: pagina publica de divulgacao do Oficina Pro.
- `assinar.html`: pagina para o cliente escolher plano e registrar interesse.
- `site.css`: identidade visual, layout responsivo e animacoes leves.
- `site.js`: carregamento dinamico de planos e envio de leads.

URLs locais:

```text
http://127.0.0.1:4173/site.html
http://127.0.0.1:4173/assinar.html
```

## Variaveis

No ambiente do app SaaS:

- `PUBLIC_APP_URL`: URL publica do app.
- `MARKETING_SITE_URL`: URL publica do site de divulgacao autorizado a enviar leads.
- `BILLING_PROVIDER=manual`: modo recomendado para staging sem cobranca.

Exemplo:

```powershell
PUBLIC_APP_URL=https://oficina-pro-staging.onrender.com
MARKETING_SITE_URL=https://oficinapro.com.br
BILLING_PROVIDER=manual
```

## Endpoints Publicos

### Listar planos

```http
GET /api/public/plans
```

Retorna apenas planos comerciais:

- `essencial`
- `profissional`
- `premium`

Planos internos como `trial` e `homologacao` nao aparecem nesse endpoint.

### Enviar lead

```http
POST /api/public/leads
Content-Type: application/json
Origin: {MARKETING_SITE_URL}
```

Payload recomendado:

```json
{
  "name": "Nome do interessado",
  "email": "cliente@empresa.com",
  "phone": "11999999999",
  "companyName": "Oficina Exemplo",
  "plan": "profissional",
  "billingCycle": "yearly",
  "source": "site-divulgacao",
  "message": "Quero conhecer o Oficina Pro",
  "website": ""
}
```

O campo `website` e um honeypot. No formulario real, ele deve existir mas ficar oculto para humanos. Se vier preenchido, o backend ignora como provavel bot.

Resposta esperada:

```json
{
  "ok": true,
  "lead": {
    "id": 1,
    "status": "new"
  }
}
```

## Seguranca

- Em ambiente online, `POST /api/public/leads` aceita origem apenas de `PUBLIC_APP_URL` ou `MARKETING_SITE_URL`.
- O endpoint nao cria oficina, usuario, assinatura nem pagamento.
- O endpoint nao chama Mercado Pago.
- Leads ficam disponiveis para o Painel Master em `GET /api/platform/marketing-leads`.
- Dados de leads entram no backup logico PostgreSQL, mas nao entram no pacote de migracao SQLite para evitar levar teste de homologacao para producao.

## Fluxo Comercial Sem Cobranca

1. Visitante abre o site de divulgacao.
2. Site consulta `GET /api/public/plans`.
3. Visitante escolhe plano e envia formulario.
4. Site envia `POST /api/public/leads`.
5. Painel Master acompanha o lead.
6. Nossa equipe cria a oficina manualmente no Painel Master quando fizer sentido.
7. Pagamento real fica desligado enquanto `BILLING_PROVIDER=manual`.

## Quando Ativar Cobranca

Somente em producao:

- `APP_ENV=production`
- `BILLING_PROVIDER=mercadopago`
- `PUBLIC_APP_URL` com HTTPS
- `MERCADOPAGO_ACCESS_TOKEN` configurado
- `MERCADOPAGO_WEBHOOK_SECRET` configurado
- webhook Mercado Pago apontando para `{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago`
