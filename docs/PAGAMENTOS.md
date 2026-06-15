# Pagamentos e Assinaturas

O Oficina Pro já possui planos, assinaturas e registro de pagamentos no Painel Master.

## Estado Atual

- Planos comerciais em `PLAN_CATALOG`.
- Ciclos mensal, trimestral e anual.
- Tabelas `subscriptions` e `payments`.
- Tabela `billing_checkout_requests` para rastrear tentativas de contratação/alteração de plano.
- Tabela `billing_webhook_events` para registrar notificações assinadas do provedor.
- Painel Master para alterar assinatura e registrar pagamento.
- Auditoria para criação/alteração de assinatura e registro de pagamento.
- Bloqueio de escrita quando assinatura não está `trial` ou `active`.
- Endpoint autenticado `POST /api/subscription/checkout` para a oficina iniciar contratação.
- Endpoint seguro para webhook Mercado Pago em `/api/billing/webhooks/mercadopago`.

## Provedores

`BILLING_PROVIDER` define o modo de cobrança:

- `manual`: homologação, cobrança fora do sistema e registro manual no Painel Master.
- `mercadopago`: produção com Mercado Pago.

## Variáveis

- `BILLING_PROVIDER`
- `PUBLIC_APP_URL`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS`

Em `staging`, `BILLING_PROVIDER=manual` é aceito para testes sem cobrança real.

Em `production`, o preflight e `/api/ready` exigem:

- `BILLING_PROVIDER=mercadopago`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `PUBLIC_APP_URL` com HTTPS

## O que é necessário no Mercado Pago

Para ativar recebimentos recorrentes reais, será necessário:

- Conta vendedor Mercado Pago verificada.
- Uma aplicação criada em **Suas integrações** no painel de desenvolvedor.
- `Access Token` da aplicação para o ambiente desejado.
- URL pública HTTPS do Oficina Pro em `PUBLIC_APP_URL`.
- Webhook configurado no Mercado Pago apontando para `{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago`.
- Assinatura secreta do webhook configurada em `MERCADOPAGO_WEBHOOK_SECRET`.
- `BILLING_PROVIDER=mercadopago` somente quando o ambiente for usar checkout real ou sandbox controlado.

Nunca salvar `MERCADOPAGO_ACCESS_TOKEN` ou `MERCADOPAGO_WEBHOOK_SECRET` no GitHub. Esses valores devem ficar apenas nas variáveis de ambiente do provedor de nuvem.

## Configuração recomendada por ambiente

### Homologação sem cobrança

```text
BILLING_PROVIDER=manual
PUBLIC_APP_URL=https://url-do-staging
MERCADOPAGO_WEBHOOK_SECRET=segredo-com-32-ou-mais-caracteres
MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS=600
```

Nesse modo, o sistema registra solicitações de contratação no Painel Master, mas não envia o cliente para cobrança.

### Sandbox Mercado Pago

```text
BILLING_PROVIDER=mercadopago
PUBLIC_APP_URL=https://url-do-staging
MERCADOPAGO_ACCESS_TOKEN=token-de-teste-do-mercado-pago
MERCADOPAGO_WEBHOOK_SECRET=segredo-do-webhook-ou-segredo-forte-equivalente
MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS=600
```

Usar somente com dados fictícios. O cliente será direcionado para o checkout do Mercado Pago e o webhook validado poderá ativar a assinatura.

### Produção

```text
APP_ENV=production
BILLING_PROVIDER=mercadopago
PUBLIC_APP_URL=https://app.oficinapro.com.br
MERCADOPAGO_ACCESS_TOKEN=token-de-producao-do-mercado-pago
MERCADOPAGO_WEBHOOK_SECRET=segredo-do-webhook-de-producao
MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS=600
```

Produção exige PostgreSQL, HTTPS, segredos fortes, credenciais administrativas não padrão e Mercado Pago ativo.

## Contratação

O cliente inicia a contratação pelo painel **Minha assinatura**. A solicitação grava:

- oficina;
- assinatura atual;
- plano e ciclo desejados;
- valor comercial;
- provedor;
- status;
- payload enviado e resposta do provedor, quando houver.

Em `manual`, usado para homologação, a solicitação fica como `manual_pending` e aparece no Painel Master para acompanhamento.

Em `mercadopago`, o backend cria uma assinatura recorrente via endpoint de preapproval do Mercado Pago e retorna a URL de checkout para o cliente. Se o provedor falhar, a tentativa fica registrada como `provider_error`.

O payload enviado ao Mercado Pago usa o modelo de assinatura sem plano associado e com pagamento pendente. O sistema envia `status=pending`, `external_reference`, `payer_email`, `back_url` e `auto_recurring` com frequência mensal, trimestral ou anual.

## Webhook Mercado Pago

Configure no Mercado Pago a URL:

```text
{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago
```

O endpoint valida `x-signature` e `x-request-id` com HMAC SHA-256 usando `MERCADOPAGO_WEBHOOK_SECRET`, registra o payload em `billing_webhook_events` e trata reenvios como duplicados idempotentes.

Também valida a idade do timestamp da assinatura. Por padrão, `MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS=600`; em staging/produção o valor não pode ser menor que 60 segundos.

Quando o evento possui status aprovado/autorizado, ou quando a consulta ao Mercado Pago confirma esse status, o backend localiza a solicitação em `billing_checkout_requests`, marca a contratação como concluída, atualiza a assinatura para `active` e registra um pagamento `paid` quando houver ID/valor confiável. Eventos sem confirmação segura ficam como `skipped` ou `error` e não liberam acesso.

O registro de pagamento é idempotente por `provider` + `providerPaymentId`; reenvios do webhook não duplicam a cobrança no Painel Master.

## Próxima Integração

Antes de vender para clientes reais:

- Testar checkout/preapproval no sandbox do Mercado Pago.
- Validar o mapeamento completo dos eventos reais do Mercado Pago no sandbox.
- Conferir se todos os eventos reais de pagamento aprovado retornam `providerPaymentId` e valor antes da produção comercial.
- Rodar testes com sandbox do Mercado Pago.
- Para validar staging com `scripts/verify_staging.py`, configure localmente `MERCADOPAGO_WEBHOOK_SECRET` com o mesmo segredo do ambiente online.
