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

Quando o evento possui status aprovado/autorizado, ou quando a consulta ao Mercado Pago confirma esse status, o backend localiza a solicitação em `billing_checkout_requests`, marca a contratação como concluída e atualiza a assinatura para `active`. Eventos sem confirmação segura ficam como `skipped` ou `error` e não liberam acesso.

## Próxima Integração

Antes de vender para clientes reais:

- Testar checkout/preapproval no sandbox do Mercado Pago.
- Validar o mapeamento completo dos eventos reais do Mercado Pago no sandbox.
- Registrar `payments` automaticamente quando o evento real de pagamento aprovado trouxer ID e valor confirmados.
- Rodar testes com sandbox do Mercado Pago.
