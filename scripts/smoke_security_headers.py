from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_headers(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.run(
        [
            PYTHON,
            "-c",
            (
                "import json, server; "
                "print(json.dumps(server.security_headers(), sort_keys=True))"
            ),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def expect(condition, message, details=""):
    if not condition:
        raise AssertionError(f"{message}: {details}")
    print(f"[OK] {message}")


def main():
    local = run_headers({"APP_ENV": "local", "PUBLIC_APP_URL": "http://127.0.0.1:4173"})
    expect(local.returncode == 0, "headers carregam em ambiente local", local.stdout)
    expect("Strict-Transport-Security" not in local.stdout, "HSTS não é enviado em local", local.stdout)
    expect("Content-Security-Policy" in local.stdout, "CSP é enviada em local", local.stdout)
    expect("Cross-Origin-Opener-Policy" in local.stdout, "COOP é enviado em local", local.stdout)

    production = run_headers({"APP_ENV": "production", "PUBLIC_APP_URL": "https://oficina-pro.example.com"})
    expect(production.returncode == 0, "headers carregam em produção", production.stdout)
    expect("Strict-Transport-Security" in production.stdout, "HSTS é enviado em produção HTTPS", production.stdout)
    expect("frame-ancestors" in production.stdout, "CSP bloqueia embed externo", production.stdout)

    print("\nSmoke de headers de segurança concluído.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)
