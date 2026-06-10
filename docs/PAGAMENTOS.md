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

Em `staging`, `BILLING_PROVIDER=manual` é aceito para testes sem cobrança real.

Em `production`, o preflight e `/api/ready` exigem:

- `BILLING_PROVIDER=mercadopago`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `PUBLIC_APP_URL` com HTTPS

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

## Webhook Mercado Pago

Configure no Mercado Pago a URL:

```text
{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago
```

O endpoint valida `x-signature` e `x-request-id` com HMAC SHA-256 usando `MERCADOPAGO_WEBHOOK_SECRET`, registra o payload em `billing_webhook_events` e trata reenvios como duplicados idempotentes.

Nesta etapa, o checkout e o webhook já estão rastreados, mas o webhook ainda não altera `subscriptions` e `payments` automaticamente. A conciliação automática deve ser ligada depois que a API do Mercado Pago for consultada para confirmar o status final do pagamento/assinatura.

## Próxima Integração

Antes de vender para clientes reais:

- Testar checkout/preapproval no sandbox do Mercado Pago.
- Conectar os eventos recebidos no webhook às solicitações em `billing_checkout_requests`.
- Atualizar `subscriptions` e `payments` automaticamente a partir dos eventos do provedor.
- Rodar testes com sandbox do Mercado Pago.
