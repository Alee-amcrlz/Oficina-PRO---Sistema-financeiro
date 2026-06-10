from pathlib import Path
from datetime import datetime
import argparse
import os
import shutil
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups"


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_db_path(raw_path):
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def latest_backup():
    candidates = sorted(BACKUP_DIR.glob("*.db"), key=lambda path: path.stat().st_mtime)
    return candidates[-1] if candidates else None


def integrity_check(path):
    if not path.exists():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if result != "ok":
        raise RuntimeError(f"Integridade SQLite inválida em {path}: {result}")


def parse_args():
    parser = argparse.ArgumentParser(description="Restaura um backup SQLite do Oficina Pro.")
    parser.add_argument("--backup", help="Arquivo de backup .db a restaurar.")
    parser.add_argument("--latest", action="store_true", help="Usa o backup mais recente em backups/.")
    parser.add_argument("--target", help="Destino da restauração. Padrão: SQLITE_PATH/oficina.db.")
    parser.add_argument("--no-safety-backup", action="store_true", help="Não cria cópia de segurança do destino atual.")
    return parser.parse_args()


def main():
    load_env_file(ROOT / ".env")
    args = parse_args()

    if args.latest:
        backup_path = latest_backup()
        if backup_path is None:
            print("[ERRO] Nenhum backup encontrado em backups/.")
            return 1
    elif args.backup:
        backup_path = resolve_db_path(args.backup)
    else:
        print("[ERRO] Informe --backup ou --latest.")
        return 1

    target_path = resolve_db_path(args.target or os.environ.get("SQLITE_PATH", ROOT / "oficina.db"))
    backup_path = backup_path.resolve()
    target_path = target_path.resolve()

    integrity_check(backup_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and not args.no_safety_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety_path = target_path.with_name(f"{target_path.stem}-before-restore-{stamp}{target_path.suffix}")
        shutil.copy2(target_path, safety_path)
        print(f"[OK] Backup de segurança criado: {safety_path}")

    shutil.copy2(backup_path, target_path)
    integrity_check(target_path)
    print(f"[OK] Backup restaurado em: {target_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
