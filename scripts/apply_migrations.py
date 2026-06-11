from pathlib import Path
import os
import re
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"
MIGRATION_FILE_RE = re.compile(r"^(.+)\.(sqlite|postgres)\.sql$")


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def collect_migrations(dialect):
    migrations = []
    for path in sorted(MIGRATIONS_DIR.glob(f"*.{dialect}.sql")):
        match = MIGRATION_FILE_RE.match(path.name)
        if not match:
            continue
        version, file_dialect = match.groups()
        if file_dialect == dialect:
            migrations.append((version, path))
    return migrations


def require_psycopg():
    try:
        import psycopg  # type: ignore
    except ImportError:
        print('[ERRO] DATABASE_URL exige psycopg: python -m pip install "psycopg[binary]"')
        return None
    return psycopg


def split_sql_statements(sql):
    statements = []
    for raw_statement in sql.split(";"):
        statement = raw_statement.strip()
        if not statement:
            continue
        meaningful_lines = [
            line
            for line in statement.splitlines()
            if line.strip() and not line.lstrip().startswith("--")
        ]
        if not meaningful_lines:
            continue
        normalized = " ".join(line.strip() for line in meaningful_lines).upper()
        if normalized in {"BEGIN", "COMMIT"}:
            continue
        statements.append(statement)
    return statements


def sqlite_schema_migrations(conn):
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if not exists:
        return set()
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def postgres_schema_migrations(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name = 'schema_migrations'
            )
            """
        )
        exists = cur.fetchone()[0]
        if not exists:
            return set()
        cur.execute('SELECT "version" FROM schema_migrations')
        return {row[0] for row in cur.fetchall()}


def apply_sqlite(sqlite_path, dry_run):
    migrations = collect_migrations("sqlite")
    conn = sqlite3.connect(sqlite_path)
    try:
        applied = sqlite_schema_migrations(conn)
        pending = [(version, path) for version, path in migrations if version not in applied]
        if dry_run:
            print_pending("SQLite", pending)
            return 0
        for version, path in pending:
            conn.executescript(path.read_text(encoding="utf-8"))
            print(f"[OK] Migracao SQLite aplicada: {version}")
        if not pending:
            print("[OK] SQLite sem migracoes pendentes.")
        return 0
    finally:
        conn.close()


def apply_postgres(database_url, dry_run):
    psycopg = require_psycopg()
    if psycopg is None:
        return 1

    migrations = collect_migrations("postgres")
    with psycopg.connect(database_url) as conn:
        applied = postgres_schema_migrations(conn)
        pending = [(version, path) for version, path in migrations if version not in applied]
        if dry_run:
            print_pending("PostgreSQL", pending)
            return 0
        with conn.cursor() as cur:
            for version, path in pending:
                for statement in split_sql_statements(path.read_text(encoding="utf-8")):
                    cur.execute(statement)
                conn.commit()
                print(f"[OK] Migracao PostgreSQL aplicada: {version}")
        if not pending:
            print("[OK] PostgreSQL sem migracoes pendentes.")
    return 0


def print_pending(label, pending):
    if not pending:
        print(f"[OK] {label} sem migracoes pendentes.")
        return
    versions = ", ".join(version for version, _ in pending)
    print(f"[OK] {label} migracoes pendentes: {versions}")


def main():
    load_env_file(ROOT / ".env")
    dry_run = "--dry-run" in sys.argv[1:]
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        return apply_postgres(database_url, dry_run)

    sqlite_path = Path(os.environ.get("SQLITE_PATH", ROOT / "oficina.db"))
    if not sqlite_path.is_absolute():
        sqlite_path = ROOT / sqlite_path
    return apply_sqlite(sqlite_path, dry_run)


if __name__ == "__main__":
    sys.exit(main())
