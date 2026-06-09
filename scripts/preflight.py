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
    failures = []

    ok(f"APP_ENV={env}")

    if env in {"staging", "production"} and host in {"127.0.0.1", "localhost"}:
        fail("HOST precisa ser 0.0.0.0 em ambiente online.", failures)
    else:
        ok(f"HOST={host}")

    if database_url:
        fail("DATABASE_URL foi configurado, mas o runtime atual ainda usa SQLite.", failures)
    elif env == "production":
        fail("APP_ENV=production esta bloqueado ate o runtime PostgreSQL ser implementado e validado.", failures)
    else:
        warn(f"Sem DATABASE_URL. Usando SQLite em {sqlite_path}. Adequado apenas para local/staging controlado.")

    if env in {"staging", "production"}:
        if default_admin_email == "master@oficina.local":
            fail("DEFAULT_ADMIN_EMAIL precisa ser alterado em ambiente online.", failures)
        if default_admin_password == "Master@123":
            fail("DEFAULT_ADMIN_PASSWORD precisa ser alterada em ambiente online.", failures)
        if len(default_admin_password) < 12:
            fail("DEFAULT_ADMIN_PASSWORD precisa ter pelo menos 12 caracteres em ambiente online.", failures)

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
