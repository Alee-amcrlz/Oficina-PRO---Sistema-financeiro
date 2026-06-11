from pathlib import Path
import os
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

PYTHON_FILES = [
    "server.py",
    "scripts/preflight.py",
    "scripts/backup_sqlite.py",
    "scripts/restore_sqlite_backup.py",
    "scripts/smoke_api.py",
    "scripts/smoke_multiempresa.py",
    "scripts/smoke_billing_checkout.py",
    "scripts/smoke_billing_webhook.py",
    "scripts/smoke_preflight_security.py",
    "scripts/smoke_runtime_config.py",
    "scripts/smoke_security_headers.py",
    "scripts/smoke_origin_guard.py",
    "scripts/smoke_password_policy.py",
    "scripts/smoke_session_revocation.py",
    "scripts/verify_staging.py",
    "scripts/validate_schema.py",
    "scripts/validate_migrations.py",
    "scripts/release_check.py",
    "scripts/export_sqlite_jsonl.py",
    "scripts/export_postgres_jsonl.py",
    "scripts/apply_postgres_baseline.py",
    "scripts/import_jsonl_to_postgres.py",
]


def run_step(name, command):
    print(f"\n== {name} ==", flush=True)
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        print(f"[ERRO] {name} falhou.", flush=True)
        return False
    print(f"[OK] {name}", flush=True)
    return True


def main():
    node_bin = os.environ.get("NODE_BIN", "").strip() or shutil.which("node")
    steps = [
        ("Sintaxe Python", [PYTHON, "-m", "py_compile", *PYTHON_FILES]),
        ("Preflight", [PYTHON, "scripts/preflight.py"]),
        ("Smoke seguranca preflight", [PYTHON, "scripts/smoke_preflight_security.py"]),
        ("Smoke configuracao runtime", [PYTHON, "scripts/smoke_runtime_config.py"]),
        ("Smoke headers seguranca", [PYTHON, "scripts/smoke_security_headers.py"]),
        ("Governanca de migracoes", [PYTHON, "scripts/validate_migrations.py"]),
        ("Schema SQLite", [PYTHON, "scripts/validate_schema.py"]),
        ("Exportacao SQLite JSONL", [PYTHON, "scripts/export_sqlite_jsonl.py"]),
        ("Dry-run importacao PostgreSQL", [PYTHON, "scripts/import_jsonl_to_postgres.py", "--dry-run"]),
    ]

    if node_bin:
        steps.insert(1, ("Sintaxe JavaScript", [node_bin, "--check", "app.js"]))
    else:
        print("[AVISO] Node.js nao encontrado no PATH; pulando sintaxe JavaScript local.")

    for name, command in steps:
        if not run_step(name, command):
            return 1

    print("\n[OK] Release check concluido. Pacote pronto para tentativa de deploy/staging.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
