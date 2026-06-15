from datetime import datetime
from urllib import error, request
import hashlib
import hmac
import json
import os
import sys
import time


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
MASTER_LOGIN = os.environ.get("SMOKE_MASTER_LOGIN", "master@oficina.local")
MASTER_PASSWORD = os.environ.get("SMOKE_MASTER_PASSWORD", "Master@123")
WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "smoke-webhook-secret")


def call(path, method="GET", token="", payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return response.status, json.loads(data) if data else None
    except error.HTTPError as exc:
        data = exc.read().decode("utf-8")
        return exc.code, json.loads(data) if data else None


def expect(condition, message, details=None):
    if not condition:
        suffix = "" if details is None else f": {details}"
        raise AssertionError(f"{message}{suffix}")
    print(f"[OK] {message}")


def login(login_name, password):
    status, data = call("/auth/login", "POST", payload={"login": login_name, "password": password})
    expect(status == 200, f"login {login_name}", data)
    return data


def mercadopago_headers(resource_id):
    request_id = f"checkout-webhook-{int(time.time())}"
    timestamp = str(int(time.time()))
    template = f"id:{resource_id.lower()};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), template.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "x-request-id": request_id,
        "x-signature": f"ts={timestamp},v1={digest}",
    }


def main():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    owner_email = f"dono.checkout.{stamp}@oficinapro.local"
    owner_password = "Teste@123456"
    master = login(MASTER_LOGIN, MASTER_PASSWORD)

    status, company = call(
        "/platform/companies",
        "POST",
        token=master["token"],
        payload={
            "companyName": f"Oficina Checkout {stamp}",
            "document": f"11.111.111/0001-{stamp[-2:]}",
            "phone": "11999990000",
            "plan": "trial",
            "billingCycle": "monthly",
            "status": "trial",
            "ownerName": f"Dono Checkout {stamp}",
            "ownerUsername": f"checkout_{stamp}",
            "ownerEmail": owner_email,
            "ownerPhone": "11999990000",
            "ownerPassword": owner_password,
        },
    )
    expect(status == 201, "master cria oficina para checkout", company)

    tenant = login(owner_email, owner_password)
    status, data = call(
        "/subscription/checkout",
        "POST",
        token=tenant["token"],
        payload={"plan": "profissional", "billingCycle": "yearly"},
    )
    expect(status == 201, "tenant inicia contratação", data)
    checkout = data.get("checkout") or {}
    expect(checkout.get("status") == "manual_pending", "checkout fica pendente manual em homologação", checkout)
    expect(float(checkout.get("amount") or 0) > 0, "checkout registra valor comercial", checkout)

    status, subscription = call("/subscription/current", token=tenant["token"])
    expect(status == 200 and subscription.get("status") == "trial", "checkout ainda não ativa assinatura sem confirmação", subscription)

    provider_id = f"smoke-preapproval-{stamp}"
    webhook_payload = {
        "id": f"smoke-checkout-event-{stamp}",
        "type": "preapproval",
        "action": "updated",
        "status": "authorized",
        "payment_id": f"smoke-payment-{stamp}",
        "date_approved": datetime.now().strftime("%Y-%m-%d"),
        "external_reference": f"company:{company['id']}:plan:profissional:cycle:yearly",
        "auto_recurring": {"transaction_amount": checkout.get("amount")},
        "data": {"id": provider_id},
    }
    status, data = call(
        f"/billing/webhooks/mercadopago?data.id={provider_id}&type=preapproval",
        "POST",
        payload=webhook_payload,
    )
    expect(status == 401, "webhook sem headers Mercado Pago é recusado", data)

    body = json.dumps(webhook_payload).encode("utf-8")
    headers = {"Content-Type": "application/json", **mercadopago_headers(provider_id)}
    req = request.Request(
        f"{BASE_URL}/billing/webhooks/mercadopago?data.id={provider_id}&type=preapproval",
        data=body,
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8") or "{}")
        status = response.status
    expect(status == 202 and data.get("processing", {}).get("status") == "processed", "webhook aprovado processa contratação", data)
    payment_id = data.get("processing", {}).get("paymentId")
    expect(payment_id, "webhook aprovado registra pagamento", data)

    duplicate_headers = {"Content-Type": "application/json", **mercadopago_headers(provider_id)}
    duplicate_req = request.Request(
        f"{BASE_URL}/billing/webhooks/mercadopago?data.id={provider_id}&type=preapproval",
        data=body,
        headers=duplicate_headers,
        method="POST",
    )
    with request.urlopen(duplicate_req, timeout=10) as response:
        duplicate_data = json.loads(response.read().decode("utf-8") or "{}")
        duplicate_status = response.status
    expect(
        duplicate_status == 202
        and duplicate_data.get("duplicate")
        and duplicate_data.get("processing", {}).get("status") == "duplicate",
        "reenvio do webhook não reprocessa pagamento",
        duplicate_data,
    )

    status, subscription = call("/subscription/current", token=tenant["token"])
    expect(
        status == 200
        and subscription.get("status") == "active"
        and subscription.get("plan", {}).get("code") == "profissional"
        and subscription.get("plan", {}).get("billingCycle") == "yearly",
        "assinatura ativa após confirmação do webhook",
        subscription,
    )

    status, payments = call("/platform/payments", token=master["token"])
    matching_payments = [item for item in payments if item.get("providerPaymentId") == f"smoke-payment-{stamp}"]
    expect(status == 200 and len(matching_payments) == 1, "pagamento aparece uma única vez no painel master", payments)

    status, data = call(
        "/subscription/checkout",
        "POST",
        token=tenant["token"],
        payload={"plan": "trial", "billingCycle": "monthly"},
    )
    expect(status == 400, "checkout recusa plano não comercial", data)

    status, requests = call("/platform/checkout-requests?limit=10", token=master["token"])
    expect(status == 200 and any(item.get("id") == checkout.get("id") for item in requests), "master monitora contratação")

    print("\nSmoke checkout de assinatura concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
