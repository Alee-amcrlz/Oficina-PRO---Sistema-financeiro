from datetime import datetime
from urllib import error, request
import json
import os
import sys


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
MASTER_LOGIN = os.environ.get("SMOKE_MASTER_LOGIN", "master@oficina.local")
MASTER_PASSWORD = os.environ.get("SMOKE_MASTER_PASSWORD", "Master@123")

FORBIDDEN_OPERATIONAL_FIELDS = {
    "approvedBudgetTotal",
    "approvedBudgetValue",
    "budgetRevenue",
    "cashflowTotal",
    "grossRevenue",
    "laborTotal",
    "operationalRevenue",
    "partsTotal",
    "revenue",
    "revenueTotal",
    "serviceOrderTotal",
    "totalAmount",
    "totalRevenue",
}


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
    owner_email = f"dono.privacidade.{stamp}@oficinapro.local"
    owner_password = "Privacidade@123"
    master = login(MASTER_LOGIN, MASTER_PASSWORD)

    status, company = call(
        "/platform/companies",
        "POST",
        token=master["token"],
        payload={
            "companyName": f"Oficina Privacidade {stamp}",
            "document": f"44.444.444/0001-{stamp[-2:]}",
            "phone": "11999990000",
            "plan": "profissional",
            "billingCycle": "monthly",
            "status": "trial",
            "ownerName": f"Dono Privacidade {stamp}",
            "ownerUsername": f"privacidade_{stamp}",
            "ownerEmail": owner_email,
            "ownerPhone": "11999990000",
            "ownerPassword": owner_password,
        },
    )
    expect(status == 201, "master cria oficina para teste de privacidade", company)

    tenant = login(owner_email, owner_password)
    status, budget = call(
        "/budgets",
        "POST",
        token=tenant["token"],
        payload={
            "userId": tenant["user"]["id"],
            "clientName": f"Cliente Privacidade {stamp}",
            "clientEmail": f"cliente.privacidade.{stamp}@example.com",
            "clientPhone": "11988880000",
            "vehicleBrand": "Fiat",
            "vehicleModel": f"Privacidade {stamp}",
            "vehicleYear": "2021",
            "plate": f"PRI{stamp[-4:]}",
            "parts": [{"description": "Peça sensível", "quantity": 2, "unitValue": 500}],
            "labor": [{"description": "Mão de obra sensível", "value": 750}],
            "description": f"Orçamento privacidade {stamp}",
            "laborValue": 750,
            "partsValue": 1000,
            "status": "aprovado",
            "approvedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    expect(status == 201, "tenant cria orçamento com valor operacional", budget)

    status, companies = call("/platform/companies", token=master["token"])
    expect(status == 200 and isinstance(companies, list), "master consulta empresas", companies)
    target = next((item for item in companies if item.get("id") == company.get("id")), None)
    expect(target is not None, "empresa aparece no Painel Master", companies)

    leaked_fields = sorted(FORBIDDEN_OPERATIONAL_FIELDS & set(target))
    expect(not leaked_fields, "Painel Master não expõe totais financeiros operacionais", leaked_fields)
    expect(target.get("approvedBudgetCount") is not None, "Painel Master mantém apenas contadores operacionais", target)

    status, data = call("/platform/payments", token=tenant["token"])
    expect(status == 403, "tenant não acessa pagamentos SaaS do Painel Master", data)

    print("\nSmoke de privacidade do Painel Master concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
