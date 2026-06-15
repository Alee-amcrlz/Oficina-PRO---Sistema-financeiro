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


def company_payload(stamp, owner_password):
    return {
        "companyName": f"Oficina Senha {stamp}",
        "document": f"22.222.222/0001-{stamp[-2:]}",
        "phone": "11999990000",
        "plan": "profissional",
        "billingCycle": "monthly",
        "status": "trial",
        "ownerName": f"Dono Senha {stamp}",
        "ownerUsername": f"senha_{stamp}",
        "ownerEmail": f"dono.senha.{stamp}@oficinapro.local",
        "ownerPhone": "11999990000",
        "ownerPassword": owner_password,
    }


def main():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    master = login(MASTER_LOGIN, MASTER_PASSWORD)

    status, data = call(
        "/platform/companies",
        "POST",
        token=master["token"],
        payload=company_payload(f"curta{stamp}", "curta1"),
    )
    expect(status == 400 and "12" in (data or {}).get("error", ""), "master não cria oficina com senha curta", data)

    owner_password = "SenhaPolicy@123"
    status, company = call(
        "/platform/companies",
        "POST",
        token=master["token"],
        payload=company_payload(stamp, owner_password),
    )
    expect(status == 201, "master cria oficina com senha forte", company)

    tenant = login(f"dono.senha.{stamp}@oficinapro.local", owner_password)
    status, data = call(
        "/users",
        "POST",
        token=tenant["token"],
        payload={
            "name": f"Usuario Senha {stamp}",
            "username": f"user_senha_{stamp}",
            "email": f"user.senha.{stamp}@oficinapro.local",
            "phone": "11977770000",
            "role": "analista",
            "accessLevel": "analista",
            "password": "curta1",
        },
    )
    expect(status == 400 and "12" in (data or {}).get("error", ""), "tenant não cria usuário com senha curta", data)

    print("\nSmoke de política de senha concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
