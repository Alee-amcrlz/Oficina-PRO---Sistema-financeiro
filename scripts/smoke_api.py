from urllib import request, error
import json
import os
import sys


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
MASTER_LOGIN = os.environ.get("SMOKE_MASTER_LOGIN", "master@oficina.local")
MASTER_PASSWORD = os.environ.get("SMOKE_MASTER_PASSWORD", "Master@123")
TENANT_LOGIN = os.environ.get("SMOKE_TENANT_LOGIN", "")
TENANT_PASSWORD = os.environ.get("SMOKE_TENANT_PASSWORD", "")


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


def login(login_name, password):
    status, data = call("/auth/login", "POST", payload={"login": login_name, "password": password})
    if status != 200:
        raise RuntimeError(f"Login falhou para {login_name}: {status} {data}")
    return data


def expect(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"[OK] {message}")


def main():
    status, data = call("/health")
    expect(status == 200 and data.get("ok"), "health ok")

    status, data = call("/plans")
    expect(status == 200 and len(data.get("plans", [])) >= 3, "catálogo de planos disponível")

    master = login(MASTER_LOGIN, MASTER_PASSWORD)
    status, data = call("/platform/companies", token=master["token"])
    expect(status == 200 and isinstance(data, list), "master acessa painel da plataforma")

    if TENANT_LOGIN and TENANT_PASSWORD:
        tenant = login(TENANT_LOGIN, TENANT_PASSWORD)
        status, _ = call("/platform/companies", token=tenant["token"])
        expect(status == 403, "tenant não acessa painel master")

        for path in ("/budgets", "/customers", "/vehicles", "/service-orders", "/subscription/current"):
            status, _ = call(path, token=tenant["token"])
            expect(status == 200, f"tenant acessa {path}")
    else:
        print("[AVISO] Defina SMOKE_TENANT_LOGIN e SMOKE_TENANT_PASSWORD para testar isolamento de tenant.")

    print("\nSmoke tests concluídos.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
