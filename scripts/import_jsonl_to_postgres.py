from pathlib import Path
import argparse
import json
import os
import sys


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports"

TABLES = [
    "companies",
    "users",
    "budgets",
    "customers",
    "vehicles",
    "service_orders",
    "app_settings",
    "parts_inventory",
    "suppliers",
    "accounts_payable",
    "subscriptions",
    "payments",
    "platform_audit_log",
    "schema_migrations",
]


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
        from psycopg.types.json import Jsonb  # type: ignore
    except ImportError:
        print("[ERRO] Instale psycopg para importar: python -m pip install \"psycopg[binary]\"")
        return None, None
    return psycopg, Jsonb


def latest_export_dir():
    candidates = sorted(
        [path for path in EXPORT_DIR.glob("sqlite-export-*") if path.is_dir()],
        key=lambda path: path.name,
    )
    return candidates[-1] if candidates else None


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pg_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def table_columns(cur, table):
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return {name: data_type for name, data_type in cur.fetchall()}


def adapt_value(value, data_type, jsonb_adapter):
    if value is None:
        return None
    if data_type == "boolean":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "sim"}
        return bool(value)
    if data_type in {"json", "jsonb"}:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        return jsonb_adapter(value)
    return value


def upsert_rows(cur, table, rows, jsonb_adapter):
    columns_by_type = table_columns(cur, table)
    if not columns_by_type:
        raise RuntimeError(f"Tabela ausente no PostgreSQL: {table}")
    columns = [column for column in rows[0].keys() if column in columns_by_type]
    if not columns:
        return 0

    quoted_table = pg_identifier(table)
    quoted_columns = ", ".join(pg_identifier(column) for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    if "id" in columns:
        update_columns = [column for column in columns if column != "id"]
        if update_columns:
            updates = ", ".join(
                f"{pg_identifier(column)} = EXCLUDED.{pg_identifier(column)}" for column in update_columns
            )
            conflict = f"ON CONFLICT (id) DO UPDATE SET {updates}"
        else:
            conflict = "ON CONFLICT (id) DO NOTHING"
    elif table == "schema_migrations" and "version" in columns:
        update_columns = [column for column in columns if column != "version"]
        updates = ", ".join(
            f"{pg_identifier(column)} = EXCLUDED.{pg_identifier(column)}" for column in update_columns
        )
        conflict = f"ON CONFLICT (version) DO UPDATE SET {updates}" if updates else "ON CONFLICT (version) DO NOTHING"
    else:
        conflict = ""

    sql = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders}) {conflict}"
    for row in rows:
        values = [
            adapt_value(row.get(column), columns_by_type[column], jsonb_adapter)
            for column in columns
        ]
        cur.execute(sql, values)
    return len(rows)


def reset_sequence(cur, table):
    cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
    sequence = cur.fetchone()[0]
    if not sequence:
        return
    cur.execute(
        f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {pg_identifier(table)}), 1), (SELECT MAX(id) IS NOT NULL FROM {pg_identifier(table)}))",
        (sequence,),
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Importa uma exportação JSONL do SQLite para PostgreSQL.")
    parser.add_argument("--export-dir", help="Diretório sqlite-export-* gerado por export_sqlite_jsonl.py.")
    parser.add_argument("--truncate", action="store_true", help="Limpa tabelas de destino antes da importação.")
    parser.add_argument("--dry-run", action="store_true", help="Valida a exportação sem conectar ao PostgreSQL.")
    return parser.parse_args()


def main():
    load_env_file(ROOT / ".env")
    args = parse_args()

    export_dir = Path(args.export_dir) if args.export_dir else latest_export_dir()
    if not export_dir or not export_dir.exists():
        print("[ERRO] Exportação não encontrada. Rode python scripts/export_sqlite_jsonl.py primeiro.")
        return 1

    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"[ERRO] Manifesto ausente: {manifest_path}")
        return 1

    if args.dry_run:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for table in TABLES:
            rows = read_jsonl(export_dir / f"{table}.jsonl")
            expected = manifest.get("tables", {}).get(table, {}).get("rows")
            if expected is not None and expected != len(rows):
                print(f"[ERRO] {table}: manifesto={expected}, arquivo={len(rows)}")
                return 1
            print(f"[OK] {table}: {len(rows)} linhas prontas")
        print("[OK] Dry-run de importação PostgreSQL concluído.")
        return 0

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERRO] DATABASE_URL não configurado.")
        return 1

    psycopg, jsonb_adapter = require_psycopg()
    if psycopg is None:
        return 1

    imported = {}
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            if args.truncate:
                quoted = ", ".join(pg_identifier(table) for table in reversed(TABLES) if table != "schema_migrations")
                cur.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")

            for table in TABLES:
                rows = read_jsonl(export_dir / f"{table}.jsonl")
                if not rows:
                    imported[table] = 0
                    continue
                imported[table] = upsert_rows(cur, table, rows, jsonb_adapter)

            for table in TABLES:
                if table != "schema_migrations":
                    reset_sequence(cur, table)
        conn.commit()

    for table, count in imported.items():
        print(f"[OK] {table}: {count} linhas")
    print("[OK] Importação PostgreSQL concluída.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
