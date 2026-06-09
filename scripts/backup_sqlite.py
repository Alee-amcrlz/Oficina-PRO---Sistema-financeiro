from datetime import datetime
from pathlib import Path
import os
import shutil
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


def main():
    load_env_file(ROOT / ".env")
    db_path = Path(os.environ.get("SQLITE_PATH", ROOT / "oficina.db"))
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    if not db_path.exists():
        print(f"Banco não encontrado: {db_path}")
        return 1

    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"{db_path.stem}-{stamp}{db_path.suffix}"
    shutil.copy2(db_path, target)
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
