from datetime import datetime
from urllib import error, request
import json
import os
import sys


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
MASTER_LOGIN = os.environ.get("SMOKE_MASTER_LOGIN", "master@oficina.local")
MASTER_PASSWORD = os.environ.get("SMOKE_MASTER_PASSWORD", "Master@123")


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


def main():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    owner_email = f"dono.checkout.{stamp}@oficinapro.local"
    owner_password = "Teste@12345"
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
