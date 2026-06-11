from urllib import error, request
import hashlib
import hmac
import json
import os
import time


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "https://oficina-pro-staging.example.com").rstrip("/")
WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "segredo-ci-com-mais-de-32-caracteres")


def post_json(path, payload, headers=None):
    req = request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
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


def mercadopago_headers(resource_id):
    request_id = f"origin-smoke-{int(time.time())}"
    timestamp = str(int(time.time()))
    template = f"id:{resource_id.lower()};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), template.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "x-request-id": request_id,
        "x-signature": f"ts={timestamp},v1={digest}",
    }


def expect(condition, message, details=None):
    if not condition:
        suffix = "" if details is None else f": {details}"
        raise AssertionError(f"{message}{suffix}")
    print(f"[OK] {message}")


def main():
    status, data = post_json(
        "/auth/login",
        {"login": "nao.existe@oficinapro.local", "password": "errada"},
        headers={"Origin": "https://evil.example.com"},
    )
    expect(status == 403, "origem externa é bloqueada em escrita", data)

    status, data = post_json(
        "/auth/login",
        {"login": "nao.existe@oficinapro.local", "password": "errada"},
        headers={"Origin": PUBLIC_APP_URL},
    )
    expect(status == 401, "origem pública correta chega ao fluxo normal de login", data)

    resource_id = f"origin-payment-{int(time.time())}"
    payload = {
        "id": f"origin-event-{resource_id}",
        "type": "payment",
        "action": "payment.updated",
        "status": "pending",
        "data": {"id": resource_id},
    }
    status, data = post_json(
        f"/billing/webhooks/mercadopago?data.id={resource_id}&type=payment",
        payload,
        headers=mercadopago_headers(resource_id),
    )
    expect(status == 202, "webhook assinado continua liberado sem Origin", data)

    print("\nSmoke de proteção de origem concluído.")
    return 0


if __name__ == "__main__":
    main()
