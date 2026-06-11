import argparse
import secrets
import string
import sys


SYMBOLS = "!@#$%*-_=+"
PASSWORD_ALPHABET = string.ascii_letters + string.digits + SYMBOLS


def secure_password(length=24):
    while True:
        value = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))
        if (
            any(ch.islower() for ch in value)
            and any(ch.isupper() for ch in value)
            and any(ch.isdigit() for ch in value)
            and any(ch in SYMBOLS for ch in value)
        ):
            return value


def token_urlsafe(length=48):
    return secrets.token_urlsafe(length)


def main():
    parser = argparse.ArgumentParser(description="Gera segredos fortes para deploy do Oficina Pro.")
    parser.add_argument("--admin-email", default="admin@seudominio.com")
    parser.add_argument("--admin-username", default="admin_oficina_pro")
    parser.add_argument("--public-url", default="https://oficina-pro-staging.onrender.com")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()

    billing_provider = "mercadopago" if args.production else "manual"
    print("APP_ENV=" + ("production" if args.production else "staging"))
    print("HOST=0.0.0.0")
    print(f"PUBLIC_APP_URL={args.public_url.rstrip('/')}")
    print(f"DEFAULT_ADMIN_USERNAME={args.admin_username}")
    print(f"DEFAULT_ADMIN_EMAIL={args.admin_email}")
    print(f"DEFAULT_ADMIN_PASSWORD={secure_password()}")
    print(f"BILLING_PROVIDER={billing_provider}")
    print(f"MERCADOPAGO_WEBHOOK_SECRET={token_urlsafe(32)}")
    if args.production:
        print("MERCADOPAGO_ACCESS_TOKEN=preencher-no-painel-mercadopago")
    return 0


if __name__ == "__main__":
    sys.exit(main())
