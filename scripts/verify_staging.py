from urllib import request, error
import json
import os
import subprocess
import sys


def normalize_base_url(raw_url):
    value = str(raw_url or "").strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    if not value.endswith("/api"):
        value = f"{value}/api"
    return value


def call_json(base_url, path):
    try:
        with request.urlopen(f"{base_url}{path}", timeout=15) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            return response.status, data
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else {}


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[ERRO] Configure {name}.")
        return None
    return value


def require_checkout_webhook_secret():
    value = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
    if not value:
        print(
            "[ERRO] Configure MERCADOPAGO_WEBHOOK_SECRET para validar checkout/webhook no staging. "
            "Use o mesmo segredo configurado no ambiente online."
        )
        return None
    if len(value) < 32:
        print("[ERRO] MERCADOPAGO_WEBHOOK_SECRET precisa ter pelo menos 32 caracteres.")
        return None
    return value


def run_script(script, env):
    cmd = [sys.executable, str(script)]
    print(f"[INFO] Rodando {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, text=True)
    return result.returncode


def main():
    staging_url = require_env("STAGING_BASE_URL")
    master_login = require_env("SMOKE_MASTER_LOGIN")
    master_password = require_env("SMOKE_MASTER_PASSWORD")
    webhook_secret = require_checkout_webhook_secret()
    if not all([staging_url, master_login, master_password, webhook_secret]):
        return 1

    base_url = normalize_base_url(staging_url)
    status, data = call_json(base_url, "/health")
    if status != 200 or not data.get("ok"):
        print(f"[ERRO] Health check falhou em {base_url}: {status} {data}")
        return 1
    print(f"[OK] Health check público em {base_url}")

    status, data = call_json(base_url, "/ready")
    if status != 200 or not data.get("ok"):
        print(f"[ERRO] Readiness check falhou em {base_url}: {status} {data}")
        return 1
    print("[OK] Readiness check público")

    env = os.environ.copy()
    env["SMOKE_BASE_URL"] = base_url
    env["SMOKE_MASTER_LOGIN"] = master_login
    env["SMOKE_MASTER_PASSWORD"] = master_password
    env["PUBLIC_APP_URL"] = base_url[:-4] if base_url.endswith("/api") else base_url
    env["MERCADOPAGO_WEBHOOK_SECRET"] = webhook_secret
    env["ORIGIN_GUARD_SKIP_WEBHOOK"] = "1"
    env.pop("SMOKE_TENANT_LOGIN", None)
    env.pop("SMOKE_TENANT_PASSWORD", None)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    smoke_api = os.path.join(root, "scripts", "smoke_api.py")
    smoke_origin_guard = os.path.join(root, "scripts", "smoke_origin_guard.py")
    smoke_multiempresa = os.path.join(root, "scripts", "smoke_multiempresa.py")
    smoke_password_policy = os.path.join(root, "scripts", "smoke_password_policy.py")
    smoke_session_revocation = os.path.join(root, "scripts", "smoke_session_revocation.py")
    smoke_billing_checkout = os.path.join(root, "scripts", "smoke_billing_checkout.py")
    smoke_billing_webhook = os.path.join(root, "scripts", "smoke_billing_webhook.py")

    for script in (
        smoke_api,
        smoke_origin_guard,
        smoke_multiempresa,
        smoke_password_policy,
        smoke_session_revocation,
        smoke_billing_checkout,
        smoke_billing_webhook,
    ):
        code = run_script(script, env)
        if code != 0:
            return code

    print("\n[OK] Staging público validado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
