from urllib import error, request
import hashlib
import hmac
import json
import os
import time


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "smoke-webhook-secret")


def post_json(path, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body or "{}")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body or "{}")


def mercadopago_headers(resource_id, request_id, timestamp, secret=SECRET):
    template = f"id:{resource_id.lower()};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode("utf-8"), template.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "x-request-id": request_id,
        "x-signature": f"ts={timestamp},v1={digest}",
    }


def main():
    resource_id = f"smoke-payment-{int(time.time())}"
    request_id = f"smoke-request-{int(time.time())}"
    timestamp = str(int(time.time()))
    payload = {
        "id": f"smoke-event-{resource_id}",
        "type": "payment",
        "action": "payment.updated",
        "data": {"id": resource_id},
    }
    path = f"/billing/webhooks/mercadopago?data.id={resource_id}&type=payment"

    status, body = post_json(path, payload, mercadopago_headers(resource_id, request_id, timestamp))
    if status != 202 or not body.get("received") or body.get("duplicate"):
        raise SystemExit(f"Webhook válido falhou: HTTP {status} {body}")

    status, body = post_json(path, payload, mercadopago_headers(resource_id, request_id, timestamp))
    if status != 202 or not body.get("duplicate"):
        raise SystemExit(f"Webhook duplicado falhou: HTTP {status} {body}")

    bad_headers = mercadopago_headers(resource_id, request_id, timestamp, secret="wrong-secret")
    status, body = post_json(path, {**payload, "id": payload["id"] + "-invalid"}, bad_headers)
    if status != 401:
        raise SystemExit(f"Webhook inválido não foi recusado: HTTP {status} {body}")

    old_resource_id = f"smoke-payment-old-{int(time.time())}"
    old_request_id = f"smoke-request-old-{int(time.time())}"
    old_timestamp = str(int(time.time()) - 3600)
    old_payload = {
        "id": f"smoke-event-{old_resource_id}",
        "type": "payment",
        "action": "payment.updated",
        "data": {"id": old_resource_id},
    }
    old_path = f"/billing/webhooks/mercadopago?data.id={old_resource_id}&type=payment"
    status, body = post_json(
        old_path,
        old_payload,
        mercadopago_headers(old_resource_id, old_request_id, old_timestamp),
    )
    if status != 401:
        raise SystemExit(f"Webhook com timestamp antigo não foi recusado: HTTP {status} {body}")

    print("[OK] Smoke webhook Mercado Pago validado.")


if __name__ == "__main__":
    main()
