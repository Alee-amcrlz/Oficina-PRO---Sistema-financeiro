from datetime import datetime
from pathlib import Path
import json
import os
import sqlite3
import sys

from data_tables import SQLITE_MIGRATION_TABLES


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports"
TABLES = SQLITE_MIGRATION_TABLES


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env_file(ROOT / ".env")
    db_path = Path(os.environ.get("SQLITE_PATH", ROOT / "oficina.db"))
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    if not db_path.exists():
        print(f"Banco não encontrado: {db_path}")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = EXPORT_DIR / f"sqlite-export-{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    manifest = {
        "source": str(db_path),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "tables": {},
    }

    existing_tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }

    for table in TABLES:
        if table not in existing_tables:
            manifest["tables"][table] = {"exists": False, "rows": 0}
            continue

        path = target_dir / f"{table}.jsonl"
        count = 0
        with path.open("w", encoding="utf-8") as handle:
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall():
                handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
                count += 1
        manifest["tables"][table] = {"exists": True, "rows": count, "file": path.name}

    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(target_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
