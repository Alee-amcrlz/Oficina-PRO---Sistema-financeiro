# Pagamentos e Assinaturas

O Oficina Pro já possui planos, assinaturas e registro de pagamentos no Painel Master.

## Estado Atual

- Planos comerciais em `PLAN_CATALOG`.
- Ciclos mensal, trimestral e anual.
- Tabelas `subscriptions` e `payments`.
- Tabela `billing_webhook_events` para registrar notificações assinadas do provedor.
- Painel Master para alterar assinatura e registrar pagamento.
- Auditoria para criação/alteração de assinatura e registro de pagamento.
- Bloqueio de escrita quando assinatura não está `trial` ou `active`.
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

## Webhook Mercado Pago

Configure no Mercado Pago a URL:

```text
{PUBLIC_APP_URL}/api/billing/webhooks/mercadopago
```

O endpoint valida `x-signature` e `x-request-id` com HMAC SHA-256 usando `MERCADOPAGO_WEBHOOK_SECRET`, registra o payload em `billing_webhook_events` e trata reenvios como duplicados idempotentes.

Nesta etapa, o webhook ainda não altera `subscriptions` e `payments` automaticamente. A conciliação automática deve ser ligada depois que o fluxo de checkout/preapproval gravar os IDs reais do provedor e a API do Mercado Pago for consultada para confirmar o status final do pagamento/assinatura.

## Próxima Integração

Antes de vender para clientes reais:

- Criar checkout/preapproval no Mercado Pago.
- Conectar os eventos recebidos no webhook aos registros locais.
- Atualizar `subscriptions` e `payments` automaticamente a partir dos eventos do provedor.
- Rodar testes com sandbox do Mercado Pago.
