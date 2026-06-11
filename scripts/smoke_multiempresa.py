from urllib import request, error
from datetime import datetime
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


def login(login_name, password):
    status, data = call("/auth/login", "POST", payload={"login": login_name, "password": password})
    if status != 200:
        raise RuntimeError(f"Login falhou para {login_name}: {status} {data}")
    return data


def expect(condition, message, details=None):
    if not condition:
        suffix = "" if details is None else f": {details}"
        raise AssertionError(f"{message}{suffix}")
    print(f"[OK] {message}")


def create_company(master_token, suffix, owner_password):
    owner_email = f"dono.isolamento.{suffix}@oficinapro.local"
    payload = {
        "name": f"Oficina Isolamento {suffix}",
        "document": f"00.000.000/0001-{suffix[-2:]}",
        "phone": "11999990000",
        "ownerName": f"Dono Isolamento {suffix}",
        "ownerUsername": f"isolamento_{suffix}",
        "ownerEmail": owner_email,
        "ownerPhone": "11999990000",
        "ownerPassword": owner_password,
        "plan": "profissional",
        "status": "trial",
        "billingCycle": "monthly",
    }
    status, data = call("/platform/companies", "POST", token=master_token, payload=payload)
    expect(status == 201, f"master cria oficina {suffix}")
    return owner_email, data


def create_customer(token, suffix):
    payload = {
        "name": f"Cliente Isolamento {suffix}",
        "email": f"cliente.{suffix}@example.com",
        "phone": "11888880000",
        "notes": "Criado pelo smoke multiempresa.",
    }
    status, data = call("/customers", "POST", token=token, payload=payload)
    expect(status == 201, f"tenant {suffix} cria cliente")
    return data


def create_budget(tenant, suffix):
    payload = {
        "userId": tenant["user"]["id"],
        "clientName": f"Cliente Isolamento {suffix}",
        "clientEmail": f"cliente.{suffix}@example.com",
        "clientPhone": "11888880000",
        "vehicleBrand": "Volkswagen",
        "vehicleModel": f"Teste {suffix}",
        "vehicleYear": "2020",
        "plate": f"ISO{suffix[-4:]}",
        "parts": [{"description": f"Peça {suffix}", "quantity": 1, "unitValue": 100}],
        "labor": [{"description": f"Mão de obra {suffix}", "value": 200}],
        "description": f"Orçamento de isolamento {suffix}",
        "laborValue": 200,
        "partsValue": 100,
        "notes": "Criado pelo smoke multiempresa.",
        "status": "pendente",
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    status, data = call("/budgets", "POST", token=tenant["token"], payload=payload)
    expect(status == 201, f"tenant {suffix} cria orçamento", data)
    return data


def assert_visible_only(token, own_suffix, other_suffix):
    status, customers = call("/customers", token=token)
    expect(status == 200, f"tenant {own_suffix} lista clientes")
    customer_names = {item.get("name") for item in customers}
    expect(f"Cliente Isolamento {own_suffix}" in customer_names, f"tenant {own_suffix} vê o próprio cliente")
    expect(f"Cliente Isolamento {other_suffix}" not in customer_names, f"tenant {own_suffix} não vê cliente de outra oficina")

    status, budgets = call("/budgets", token=token)
    expect(status == 200, f"tenant {own_suffix} lista orçamentos")
    budget_descriptions = {item.get("description") for item in budgets}
    expect(f"Orçamento de isolamento {own_suffix}" in budget_descriptions, f"tenant {own_suffix} vê o próprio orçamento")
    expect(f"Orçamento de isolamento {other_suffix}" not in budget_descriptions, f"tenant {own_suffix} não vê orçamento de outra oficina")

    status, _ = call("/platform/companies", token=token)
    expect(status == 403, f"tenant {own_suffix} não acessa painel master")


def main():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix_a = f"a{stamp}"
    suffix_b = f"b{stamp}"
    owner_password = "Teste@123456"

    master = login(MASTER_LOGIN, MASTER_PASSWORD)
    owner_a, _ = create_company(master["token"], suffix_a, owner_password)
    owner_b, _ = create_company(master["token"], suffix_b, owner_password)

    tenant_a = login(owner_a, owner_password)
    tenant_b = login(owner_b, owner_password)

    create_customer(tenant_a["token"], suffix_a)
    create_customer(tenant_b["token"], suffix_b)
    create_budget(tenant_a, suffix_a)
    create_budget(tenant_b, suffix_b)

    assert_visible_only(tenant_a["token"], suffix_a, suffix_b)
    assert_visible_only(tenant_b["token"], suffix_b, suffix_a)

    print("\nSmoke multiempresa concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
