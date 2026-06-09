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
    failures = []

    ok(f"APP_ENV={env}")

    if env in {"staging", "production"} and host in {"127.0.0.1", "localhost"}:
        fail("HOST precisa ser 0.0.0.0 em ambiente online.", failures)
    else:
        ok(f"HOST={host}")

    if env == "production" and not database_url:
        fail("Produção precisa de DATABASE_URL apontando para banco gerenciado.", failures)
    elif not database_url:
        warn(f"Sem DATABASE_URL. Usando SQLite em {sqlite_path}. Adequado apenas para local/staging controlado.")
    else:
        ok("DATABASE_URL configurado.")

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
