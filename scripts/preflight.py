from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fail(message, failures):
    failures.append(message)
    print(f"[ERRO] {message}")


def warn(message):
    print(f"[AVISO] {message}")


def ok(message):
    print(f"[OK] {message}")


def main():
    load_env_file(ROOT / ".env")
    env = os.environ.get("APP_ENV", "local").lower()
    host = os.environ.get("HOST", "127.0.0.1")
    database_url = os.environ.get("DATABASE_URL", "")
    sqlite_path = os.environ.get("SQLITE_PATH", "oficina.db")
    default_admin_email = os.environ.get("DEFAULT_ADMIN_EMAIL", "master@oficina.local").strip().lower()
    default_admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Master@123")
    billing_provider = os.environ.get("BILLING_PROVIDER", "manual").strip().lower()
    mercadopago_access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "").strip()
    mercadopago_webhook_secret = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
    public_app_url = os.environ.get("PUBLIC_APP_URL", "").strip()
    failures = []

    ok(f"APP_ENV={env}")

    if env in {"staging", "production"} and host in {"127.0.0.1", "localhost"}:
        fail("HOST precisa ser 0.0.0.0 em ambiente online.", failures)
    else:
        ok(f"HOST={host}")

    if database_url:
        try:
            import psycopg  # type: ignore  # noqa: F401
        except ImportError:
            fail('DATABASE_URL exige a dependência "psycopg[binary]".', failures)
        else:
            ok("DATABASE_URL configurado para PostgreSQL.")
    elif env == "production":
        fail("APP_ENV=production exige DATABASE_URL com PostgreSQL gerenciado.", failures)
    else:
        warn(f"Sem DATABASE_URL. Usando SQLite em {sqlite_path}. Adequado apenas para local/staging controlado.")

    if env in {"staging", "production"}:
        if default_admin_email == "master@oficina.local":
            fail("DEFAULT_ADMIN_EMAIL precisa ser alterado em ambiente online.", failures)
        if default_admin_password == "Master@123":
            fail("DEFAULT_ADMIN_PASSWORD precisa ser alterada em ambiente online.", failures)
        if len(default_admin_password) < 12:
            fail("DEFAULT_ADMIN_PASSWORD precisa ter pelo menos 12 caracteres em ambiente online.", failures)

    if billing_provider not in {"manual", "mercadopago"}:
        fail("BILLING_PROVIDER precisa ser manual ou mercadopago.", failures)
    elif billing_provider == "manual" and env == "staging":
        warn("BILLING_PROVIDER=manual em staging. Adequado apenas para homologação sem cobrança real.")
    else:
        ok(f"BILLING_PROVIDER={billing_provider}")

    if env == "production":
        if billing_provider != "mercadopago":
            fail("Produção exige BILLING_PROVIDER=mercadopago.", failures)
        if not mercadopago_access_token:
            fail("Produção exige MERCADOPAGO_ACCESS_TOKEN.", failures)
        if not mercadopago_webhook_secret:
            fail("Produção exige MERCADOPAGO_WEBHOOK_SECRET.", failures)
        if not public_app_url.startswith("https://"):
            fail("Produção exige PUBLIC_APP_URL com HTTPS.", failures)

    iterations = int(os.environ.get("PASSWORD_HASH_ITERATIONS", "260000"))
    if iterations < 260000:
        fail("PASSWORD_HASH_ITERATIONS abaixo do mínimo recomendado.", failures)
    else:
        ok("PASSWORD_HASH_ITERATIONS adequado.")

    if failures:
        print("\nPreflight reprovado.")
        return 1
    print("\nPreflight aprovado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
