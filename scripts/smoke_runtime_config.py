from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

BASE_ENV = {
    "APP_ENV": "production",
    "HOST": "0.0.0.0",
    "PORT": "4173",
    "DATABASE_URL": "postgresql://oficina:oficina@localhost:5432/oficina_pro",
    "PUBLIC_APP_URL": "https://oficina-pro.example.com",
    "DEFAULT_ADMIN_USERNAME": "admin_prod",
    "DEFAULT_ADMIN_EMAIL": "admin.prod@oficinapro.local",
    "DEFAULT_ADMIN_PASSWORD": "SenhaForte@12345",
    "BILLING_PROVIDER": "mercadopago",
    "MERCADOPAGO_ACCESS_TOKEN": "TEST-token-runtime-config",
    "MERCADOPAGO_WEBHOOK_SECRET": "segredo-runtime-com-mais-de-32-caracteres",
    "MIN_USER_PASSWORD_LENGTH": "12",
}


def run_runtime(extra_env):
    env = os.environ.copy()
    env.update(BASE_ENV)
    env.update(extra_env)
    return subprocess.run(
        [
            PYTHON,
            "-c",
            "import server; server.validate_runtime_config(); print('[OK] runtime config valida')",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def expect(condition, message, details=""):
    if not condition:
        raise AssertionError(f"{message}: {details}")
    print(f"[OK] {message}")


def main():
    valid = run_runtime({})
    expect(valid.returncode == 0, "runtime aceita produção segura", valid.stdout)

    manual_billing = run_runtime({"BILLING_PROVIDER": "manual"})
    expect(manual_billing.returncode != 0, "runtime recusa produção com cobrança manual", manual_billing.stdout)
    expect("BILLING_PROVIDER=mercadopago" in manual_billing.stdout, "runtime explica cobrança obrigatória", manual_billing.stdout)

    default_admin = run_runtime(
        {
            "DEFAULT_ADMIN_USERNAME": "master",
            "DEFAULT_ADMIN_EMAIL": "master@oficina.local",
            "DEFAULT_ADMIN_PASSWORD": "Master@123",
        }
    )
    expect(default_admin.returncode != 0, "runtime recusa admin padrão em produção", default_admin.stdout)
    expect("DEFAULT_ADMIN_USERNAME" in default_admin.stdout, "runtime aponta usuário padrão", default_admin.stdout)

    insecure_public_url = run_runtime({"PUBLIC_APP_URL": "http://oficina-pro.example.com"})
    expect(insecure_public_url.returncode != 0, "runtime recusa produção sem HTTPS", insecure_public_url.stdout)
    expect("HTTPS" in insecure_public_url.stdout, "runtime aponta HTTPS obrigatório", insecure_public_url.stdout)

    weak_password_policy = run_runtime({"MIN_USER_PASSWORD_LENGTH": "6"})
    expect(weak_password_policy.returncode != 0, "runtime recusa política de senha fraca online", weak_password_policy.stdout)
    expect("MIN_USER_PASSWORD_LENGTH" in weak_password_policy.stdout, "runtime aponta política mínima de senha", weak_password_policy.stdout)

    staging_manual = run_runtime(
        {
            "APP_ENV": "staging",
            "DATABASE_URL": "",
            "BILLING_PROVIDER": "manual",
            "MERCADOPAGO_ACCESS_TOKEN": "",
            "MERCADOPAGO_WEBHOOK_SECRET": "",
            "PUBLIC_APP_URL": "https://oficina-pro-staging.example.com",
        }
    )
    expect(staging_manual.returncode == 0, "runtime aceita staging manual seguro", staging_manual.stdout)

    print("\nSmoke de configuração de runtime concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
