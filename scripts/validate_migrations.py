from pathlib import Path
import ast
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"
SERVER_FILE = ROOT / "server.py"
SCHEMA_VALIDATOR_FILE = ROOT / "scripts" / "validate_schema.py"
APPLY_MIGRATIONS_FILE = ROOT / "scripts" / "apply_migrations.py"
BASELINE_VERSION = "20260609_web_saas_baseline"
MIGRATION_FILE_RE = re.compile(r"^(.+)\.(sqlite|postgres)\.sql$")


def load_literal_set(path, variable_name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == variable_name:
                value = ast.literal_eval(node.value)
                return set(value)
    raise RuntimeError(f"Variavel {variable_name} nao encontrada em {path}")


def load_literal_list(path, variable_name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == variable_name:
                value = ast.literal_eval(node.value)
                return list(value)
    raise RuntimeError(f"Variavel {variable_name} nao encontrada em {path}")


def collect_migration_files():
    files_by_version = {}
    invalid_names = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = MIGRATION_FILE_RE.match(path.name)
        if not match:
            invalid_names.append(path.name)
            continue
        version, dialect = match.groups()
        files_by_version.setdefault(version, {})[dialect] = path
    return files_by_version, invalid_names


def main():
    failures = []
    server_versions = load_literal_set(SERVER_FILE, "REQUIRED_SCHEMA_MIGRATIONS")
    validator_versions = load_literal_set(SCHEMA_VALIDATOR_FILE, "REQUIRED_MIGRATIONS")
    runner_order = load_literal_list(APPLY_MIGRATIONS_FILE, "MIGRATION_ORDER")

    if server_versions != validator_versions:
        failures.append(
            "Listas de migracoes divergentes entre server.py e scripts/validate_schema.py: "
            f"server={sorted(server_versions)} validator={sorted(validator_versions)}"
        )
    if set(runner_order) != server_versions:
        failures.append(
            "Ordem de migracoes divergente em scripts/apply_migrations.py: "
            f"runner={runner_order} esperadas={sorted(server_versions)}"
        )
    if len(runner_order) != len(set(runner_order)):
        failures.append("MIGRATION_ORDER contem duplicidade.")
    if runner_order and runner_order[0] != BASELINE_VERSION:
        failures.append("MIGRATION_ORDER precisa iniciar pela baseline.")

    files_by_version, invalid_names = collect_migration_files()
    for name in invalid_names:
        failures.append(f"Arquivo SQL com nome fora do padrao: {name}")

    expected_versions = server_versions
    file_versions = set(files_by_version)
    for version in sorted(expected_versions):
        dialects = files_by_version.get(version, {})
        for dialect in ("sqlite", "postgres"):
            if dialect not in dialects:
                failures.append(f"Migracao {version} sem arquivo {dialect}")

    for version in sorted(file_versions - expected_versions):
        failures.append(f"Arquivo de migracao sem registro esperado: {version}")

    for version in sorted(expected_versions - {BASELINE_VERSION}):
        for dialect, path in files_by_version.get(version, {}).items():
            text = path.read_text(encoding="utf-8").lower()
            if version.lower() not in text:
                failures.append(f"{path.name} nao menciona a propria versao")
            if "schema_migrations" not in text:
                failures.append(f"{path.name} nao registra schema_migrations")
            if path.stat().st_size == 0:
                failures.append(f"{path.name} esta vazio")

    if failures:
        for failure in failures:
            print(f"[ERRO] {failure}")
        print("\nMigracoes invalidas.")
        return 1

    print(f"[OK] {len(expected_versions)} migracoes validadas em SQLite e PostgreSQL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
