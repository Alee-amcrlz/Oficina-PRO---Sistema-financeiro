from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "migrations" / "20260609_web_saas_baseline.postgres.sql"


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_psycopg():
    try:
        import psycopg  # type: ignore
    except ImportError:
        print("[ERRO] Instale psycopg para preparar PostgreSQL: python -m pip install \"psycopg[binary]\"")
        return None
    return psycopg


def main():
    load_env_file(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERRO] DATABASE_URL não configurado.")
        return 1
    if not BASELINE.exists():
        print(f"[ERRO] Baseline não encontrada: {BASELINE}")
        return 1

    psycopg = require_psycopg()
    if psycopg is None:
        return 1

    sql = BASELINE.read_text(encoding="utf-8")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("[OK] Baseline PostgreSQL aplicada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
