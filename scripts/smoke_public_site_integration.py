from urllib import request, error
import json
import os
import sys
import time


BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:4173/api").rstrip("/")
MASTER_LOGIN = os.environ.get("SMOKE_MASTER_LOGIN", "master@oficina.local")
MASTER_PASSWORD = os.environ.get("SMOKE_MASTER_PASSWORD", "Master@123")
ORIGIN = os.environ.get("SMOKE_MARKETING_ORIGIN", "https://site.oficinapro.example.com")


def call(path, method="GET", token="", payload=None, origin=""):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin
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


def main():
    status, data = call("/public/plans")
    plans = data.get("plans", []) if data else []
    codes = {plan.get("code") for plan in plans}
    expect(status == 200 and {"essencial", "profissional", "premium"} <= codes, "catalogo publico lista planos comerciais", data)
    expect("trial" not in codes and "homologacao" not in codes, "catalogo publico nao expoe planos internos", data)

    stamp = int(time.time())
    payload = {
        "name": f"Lead Site {stamp}",
        "email": f"lead.site.{stamp}@oficinapro.local",
        "phone": "11999999999",
        "companyName": "Oficina Lead Site",
        "plan": "profissional",
        "billingCycle": "yearly",
        "source": "site-divulgacao-smoke",
        "message": "Quero conhecer o sistema.",
    }
    status, data = call("/public/leads", "POST", payload=payload, origin=ORIGIN)
    lead_id = (data or {}).get("lead", {}).get("id")
    expect(status == 201 and lead_id, "site envia lead sem iniciar cobranca", data)

    invalid_payload = {**payload, "email": "email-invalido"}
    status, data = call("/public/leads", "POST", payload=invalid_payload, origin=ORIGIN)
    expect(status == 400, "lead invalido e recusado", data)

    honeypot_payload = {**payload, "email": f"bot.{stamp}@oficinapro.local", "website": "https://spam.example.com"}
    status, data = call("/public/leads", "POST", payload=honeypot_payload, origin=ORIGIN)
    expect(status == 202 and data.get("ok"), "honeypot ignora bot sem erro publico", data)

    master = login(MASTER_LOGIN, MASTER_PASSWORD)
    status, leads = call("/platform/marketing-leads?limit=20", token=master["token"])
    expect(status == 200 and any(item.get("id") == lead_id for item in leads), "Painel Master consulta leads do site", leads)

    print("\nSmoke de integracao com site publico concluido.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
