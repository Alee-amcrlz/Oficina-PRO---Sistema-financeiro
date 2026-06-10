# Pagamentos e Assinaturas

O Oficina Pro já possui planos, assinaturas e registro de pagamentos no Painel Master.

## Estado Atual

- Planos comerciais em `PLAN_CATALOG`.
- Ciclos mensal, trimestral e anual.
- Tabelas `subscriptions` e `payments`.
- Painel Master para alterar assinatura e registrar pagamento.
- Auditoria para criação/alteração de assinatura e registro de pagamento.
- Bloqueio de escrita quando assinatura não está `trial` ou `active`.

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

## Próxima Integração

Antes de vender para clientes reais:

- Criar checkout/preapproval no Mercado Pago.
- Criar webhook autenticado por `MERCADOPAGO_WEBHOOK_SECRET`.
- Atualizar `subscriptions` e `payments` automaticamente a partir dos eventos do provedor.
- Rodar testes com sandbox do Mercado Pago.
