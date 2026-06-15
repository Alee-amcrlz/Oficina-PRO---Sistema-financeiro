from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_preflight(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "preflight.py")],
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
    insecure = run_preflight(
        {
            "APP_ENV": "staging",
            "HOST": "0.0.0.0",
            "PUBLIC_APP_URL": "",
            "DATABASE_URL": "",
            "DEFAULT_ADMIN_USERNAME": "master",
            "DEFAULT_ADMIN_EMAIL": "master@oficina.local",
            "DEFAULT_ADMIN_PASSWORD": "Master@123",
            "MIN_USER_PASSWORD_LENGTH": "6",
            "MERCADOPAGO_WEBHOOK_SECRET": "curto",
            "MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS": "30",
        }
    )
    expect(insecure.returncode != 0, "preflight recusa credenciais online inseguras", insecure.stdout)
    expect("DEFAULT_ADMIN_USERNAME" in insecure.stdout, "preflight aponta usuário admin padrão", insecure.stdout)
    expect("MERCADOPAGO_WEBHOOK_SECRET" in insecure.stdout, "preflight aponta webhook secret curto", insecure.stdout)
    expect("MIN_USER_PASSWORD_LENGTH" in insecure.stdout, "preflight aponta política de senha fraca", insecure.stdout)
    expect("MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS" in insecure.stdout, "preflight aponta janela curta de webhook", insecure.stdout)

    secure = run_preflight(
        {
            "APP_ENV": "staging",
            "HOST": "0.0.0.0",
            "PUBLIC_APP_URL": "https://oficina-pro-staging.example.com",
            "DATABASE_URL": "",
            "DEFAULT_ADMIN_USERNAME": "admin_staging",
            "DEFAULT_ADMIN_EMAIL": "admin.staging@oficinapro.local",
            "DEFAULT_ADMIN_PASSWORD": "SenhaForte@12345",
            "MIN_USER_PASSWORD_LENGTH": "12",
            "MERCADOPAGO_WEBHOOK_SECRET": "segredo-ci-com-mais-de-32-caracteres",
            "MERCADOPAGO_WEBHOOK_MAX_SKEW_SECONDS": "600",
            "BILLING_PROVIDER": "manual",
        }
    )
    expect(secure.returncode == 0, "preflight aceita staging manual com credenciais fortes", secure.stdout)

    print("\nSmoke de segurança do preflight concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
