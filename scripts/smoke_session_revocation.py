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


def create_company(master_token, stamp, owner_password):
    owner_email = f"dono.sessao.{stamp}@oficinapro.local"
    payload = {
        "companyName": f"Oficina Sessao {stamp}",
        "document": f"33.333.333/0001-{stamp[-2:]}",
        "phone": "11999990000",
        "plan": "profissional",
        "billingCycle": "monthly",
        "status": "trial",
        "ownerName": f"Dono Sessao {stamp}",
        "ownerUsername": f"sessao_{stamp}",
        "ownerEmail": owner_email,
        "ownerPhone": "11999990000",
        "ownerPassword": owner_password,
    }
    status, data = call("/platform/companies", "POST", token=master_token, payload=payload)
    expect(status == 201, "master cria oficina para revogação de sessão", data)
    return owner_email


def main():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    owner_password = "SessaoForte@123"
    new_password = "SessaoNova@1234"
    master = login(MASTER_LOGIN, MASTER_PASSWORD)
    owner_email = create_company(master["token"], stamp, owner_password)

    tenant = login(owner_email, owner_password)
    status, users = call("/users", token=tenant["token"])
    expect(status == 200 and users, "tenant acessa usuários antes da troca de senha", users)
    owner = next((item for item in users if item.get("email") == owner_email), None)
    expect(owner is not None, "tenant localiza próprio usuário", users)

    updated_owner = {**owner, "password": new_password}
    status, data = call(f"/users/{owner['id']}", "PUT", token=tenant["token"], payload=updated_owner)
    expect(status == 200, "tenant troca a própria senha", data)

    status, data = call("/users", token=tenant["token"])
    expect(status == 401, "token antigo é revogado após troca de senha", data)

    tenant = login(owner_email, new_password)
    status, data = call("/users", token=tenant["token"])
    expect(status == 200, "nova sessão funciona após troca de senha", data)

    status, data = call(f"/users/{owner['id']}", "PUT", token=tenant["token"], payload={**owner, "blocked": True})
    expect(status == 200, "tenant bloqueia usuário de teste", data)

    status, data = call("/users", token=tenant["token"])
    expect(status == 401, "token é revogado após bloqueio", data)

    print("\nSmoke de revogação de sessão concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
