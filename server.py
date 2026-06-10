from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib import error as url_error
from urllib import request as url_request
from decimal import Decimal
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time


ROOT = Path(__file__).resolve().parent


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT / ".env")


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


APP_ENV = os.environ.get("APP_ENV", "local").strip().lower()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = Path(os.environ.get("SQLITE_PATH", ROOT / "oficina.db"))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = env_int("PORT", 4173)
SESSION_TTL_SECONDS = env_int("SESSION_TTL_SECONDS", 8 * 60 * 60)
PASSWORD_HASH_ITERATIONS = env_int("PASSWORD_HASH_ITERATIONS", 260000)
LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_WINDOW_SECONDS = env_int("LOGIN_WINDOW_SECONDS", 15 * 60)
LOGIN_LOCK_SECONDS = env_int("LOGIN_LOCK_SECONDS", 15 * 60)
DEFAULT_ADMIN_NAME = os.environ.get("DEFAULT_ADMIN_NAME", "MASTER").strip() or "MASTER"
DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "master").strip() or "master"
DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "master@oficina.local").strip().lower()
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Master@123")
BILLING_PROVIDER = os.environ.get("BILLING_PROVIDER", "manual").strip().lower() or "manual"
MERCADOPAGO_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "").strip()
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "").strip().rstrip("/")
ONLINE_ENVS = {"staging", "production"}


def validate_runtime_config():
    failures = []
    allowed_envs = {"local", "staging", "production"}

    if APP_ENV not in allowed_envs:
        failures.append("APP_ENV deve ser local, staging ou production.")

    if APP_ENV == "production" and not DATABASE_URL:
        failures.append("APP_ENV=production exige DATABASE_URL com PostgreSQL gerenciado.")

    if BILLING_PROVIDER not in {"manual", "mercadopago"}:
        failures.append("BILLING_PROVIDER deve ser manual ou mercadopago.")

    if APP_ENV in ONLINE_ENVS and HOST in {"127.0.0.1", "localhost"}:
        failures.append("HOST precisa ser 0.0.0.0 em staging/production.")

    if APP_ENV in ONLINE_ENVS:
        if DEFAULT_ADMIN_PASSWORD == "Master@123":
            failures.append("DEFAULT_ADMIN_PASSWORD precisa ser alterada em ambiente online.")
        if len(DEFAULT_ADMIN_PASSWORD) < 12:
            failures.append("DEFAULT_ADMIN_PASSWORD precisa ter pelo menos 12 caracteres em ambiente online.")
        if DEFAULT_ADMIN_EMAIL == "master@oficina.local":
            failures.append("DEFAULT_ADMIN_EMAIL precisa ser um email administrativo real em ambiente online.")

    if APP_ENV == "production":
        if BILLING_PROVIDER != "mercadopago":
            failures.append("Produção exige BILLING_PROVIDER=mercadopago.")
        if not MERCADOPAGO_ACCESS_TOKEN:
            failures.append("Produção exige MERCADOPAGO_ACCESS_TOKEN.")
        if not MERCADOPAGO_WEBHOOK_SECRET:
            failures.append("Produção exige MERCADOPAGO_WEBHOOK_SECRET.")
        if not PUBLIC_APP_URL.startswith("https://"):
            failures.append("Produção exige PUBLIC_APP_URL com HTTPS.")

    if failures:
        raise RuntimeError("Configuracao insegura:\n- " + "\n- ".join(failures))

PLAN_CATALOG = {
    "essencial": {
        "code": "essencial",
        "name": "Essencial",
        "description": "Para oficinas pequenas que precisam organizar atendimento e orçamentos.",
        "features": ["dashboard", "budgets"],
        "limits": {"users": 1},
        "prices": {"monthly": 59.0, "quarterly": 159.0, "yearly": 549.0},
    },
    "profissional": {
        "code": "profissional",
        "name": "Profissional",
        "description": "Plano principal para oficinas que precisam de financeiro, estoque e equipe.",
        "features": ["dashboard", "budgets", "billing", "inventory", "users"],
        "limits": {"users": 5},
        "prices": {"monthly": 99.0, "quarterly": 267.0, "yearly": 949.0},
    },
    "premium": {
        "code": "premium",
        "name": "Premium",
        "description": "Para operação maior, com mais usuários, suporte prioritário e gestão avançada.",
        "features": ["dashboard", "budgets", "billing", "inventory", "users", "advanced_reports", "priority_support"],
        "limits": {"users": 15},
        "prices": {"monthly": 149.0, "quarterly": 402.0, "yearly": 1399.0},
    },
    "homologacao": {
        "code": "homologacao",
        "name": "Homologação",
        "description": "Plano interno para testes completos do ambiente local.",
        "features": ["dashboard", "budgets", "billing", "inventory", "users", "advanced_reports", "priority_support"],
        "limits": {"users": 50},
        "prices": {"monthly": 0.0, "quarterly": 0.0, "yearly": 0.0},
    },
    "trial": {
        "code": "trial",
        "name": "Teste",
        "description": "Período de avaliação com recursos profissionais.",
        "features": ["dashboard", "budgets", "billing", "inventory", "users"],
        "limits": {"users": 3},
        "prices": {"monthly": 0.0, "quarterly": 0.0, "yearly": 0.0},
    },
}

BILLING_CYCLES = {
    "monthly": "Mensal",
    "quarterly": "Trimestral",
    "yearly": "Anual",
}

ACTIVE_SUBSCRIPTION_STATUSES = {"trial", "active"}

REQUIRED_SCHEMA_COLUMNS = {
    "companies": {"id", "name", "ownerUserId", "createdAt", "updatedAt"},
    "users": {"id", "companyId", "isPlatformAdmin", "email", "passwordHash", "role", "accessLevel", "blocked"},
    "user_sessions": {"id", "tokenHash", "userId", "expiresAt", "createdAt", "lastSeenAt"},
    "login_audit": {"id", "login", "success", "reason", "ipAddress", "userAgent", "createdAt"},
    "budgets": {"id", "companyId", "userId", "clientName", "parts", "labor", "status", "approvedAt"},
    "customers": {"id", "companyId", "name", "email", "phone"},
    "vehicles": {"id", "companyId", "customerId", "plate", "brand", "model"},
    "service_orders": {"id", "companyId", "budgetId", "customerId", "vehicleId", "number", "status", "parts", "labor", "totalAmount"},
    "parts_inventory": {"id", "companyId", "code", "description", "stockQuantity"},
    "suppliers": {"id", "companyId", "cnpj", "corporateName", "tradeName"},
    "accounts_payable": {"id", "companyId", "description", "supplierName", "amount"},
    "subscriptions": {"id", "companyId", "plan", "status", "billingCycle", "currentPeriodEnd"},
    "payments": {"id", "companyId", "subscriptionId", "provider", "amount", "status"},
    "billing_checkout_requests": {"id", "companyId", "subscriptionId", "plan", "billingCycle", "provider", "amount", "status"},
    "billing_webhook_events": {"id", "provider", "eventId", "eventType", "action", "resourceId", "requestId", "payload", "receivedAt"},
    "platform_audit_log": {"id", "actorUserId", "action", "targetCompanyId", "details", "createdAt"},
    "schema_migrations": {"version", "appliedAt"},
}

REQUIRED_SCHEMA_MIGRATIONS = {
    "20260609_web_saas_baseline",
    "20260609_db_sessions",
    "20260609_login_audit",
    "20260610_billing_webhooks",
    "20260610_billing_checkout_requests",
}

DEFAULT_ACCESS_LEVELS = {
    "administrador": "Administrador",
    "financeiro": "Financeiro",
    "analista": "Analista",
}

DEFAULT_PERMISSIONS = {
    "administrador": [
        "dashboard_view",
        "budgets_view",
        "budgets_manage",
        "budgets_approve",
        "budgets_delete",
        "inventory_view",
        "inventory_manage",
        "billing_view",
        "billing_edit",
    ],
    "financeiro": ["dashboard_view", "billing_view"],
    "analista": ["dashboard_view", "budgets_view", "budgets_manage"],
}


USER_COLUMNS = [
    "companyId",
    "isPlatformAdmin",
    "name",
    "username",
    "email",
    "phone",
    "passwordHash",
    "role",
    "accessLevel",
    "blocked",
    "createdAt",
    "updatedAt",
]

BUDGET_COLUMNS = [
    "companyId",
    "userId",
    "clientName",
    "clientEmail",
    "clientPhone",
    "clientZip",
    "clientStreet",
    "clientNumber",
    "clientAddress",
    "clientDistrict",
    "clientState",
    "vehicleBrand",
    "vehicleModel",
    "vehicleYear",
    "vehicle",
    "plate",
    "vehicleColor",
    "vehicleKm",
    "parts",
    "labor",
    "description",
    "laborValue",
    "partsValue",
    "notes",
    "status",
    "approvedAt",
    "createdAt",
    "updatedAt",
]

CUSTOMER_COLUMNS = [
    "companyId",
    "name",
    "email",
    "phone",
    "zip",
    "street",
    "number",
    "district",
    "state",
    "notes",
    "createdAt",
    "updatedAt",
]

VEHICLE_COLUMNS = [
    "companyId",
    "customerId",
    "brand",
    "model",
    "year",
    "plate",
    "color",
    "km",
    "notes",
    "createdAt",
    "updatedAt",
]

SERVICE_ORDER_COLUMNS = [
    "companyId",
    "budgetId",
    "customerId",
    "vehicleId",
    "number",
    "status",
    "priority",
    "entryDate",
    "expectedDeliveryDate",
    "completedAt",
    "problemDescription",
    "serviceDescription",
    "internalNotes",
    "parts",
    "labor",
    "totalAmount",
    "createdAt",
    "updatedAt",
]

PART_COLUMNS = [
    "companyId",
    "brand",
    "code",
    "description",
    "costPrice",
    "salePrice",
    "stockQuantity",
    "serialNumber",
    "createdAt",
    "updatedAt",
]

SUPPLIER_COLUMNS = [
    "companyId",
    "cnpj",
    "corporateName",
    "tradeName",
    "phone",
    "sellerName",
    "createdAt",
    "updatedAt",
]

PAYABLE_COLUMNS = [
    "companyId",
    "description",
    "entryDate",
    "competenceDate",
    "category",
    "invoiceNumber",
    "supplierId",
    "supplierCnpj",
    "supplierName",
    "amount",
    "notes",
    "createdAt",
    "updatedAt",
]

SUBSCRIPTION_COLUMNS = [
    "companyId",
    "plan",
    "status",
    "billingCycle",
    "provider",
    "providerCustomerId",
    "providerSubscriptionId",
    "currentPeriodStart",
    "currentPeriodEnd",
    "trialEndsAt",
    "createdAt",
    "updatedAt",
]

PAYMENT_COLUMNS = [
    "companyId",
    "subscriptionId",
    "provider",
    "providerPaymentId",
    "amount",
    "status",
    "paidAt",
    "createdAt",
    "updatedAt",
]

BILLING_CHECKOUT_COLUMNS = [
    "companyId",
    "subscriptionId",
    "plan",
    "billingCycle",
    "provider",
    "providerCheckoutId",
    "initPoint",
    "sandboxInitPoint",
    "amount",
    "status",
    "requestPayload",
    "responsePayload",
    "error",
    "createdAt",
    "updatedAt",
]

BILLING_WEBHOOK_COLUMNS = [
    "provider",
    "eventId",
    "eventType",
    "action",
    "resourceId",
    "requestId",
    "signatureTs",
    "payload",
    "receivedAt",
    "processedAt",
    "status",
    "error",
]

AUDIT_COLUMNS = [
    "actorUserId",
    "actorEmail",
    "action",
    "targetType",
    "targetId",
    "targetCompanyId",
    "details",
    "createdAt",
]

SESSION_COLUMNS = [
    "tokenHash",
    "userId",
    "expiresAt",
    "createdAt",
    "lastSeenAt",
]

LOGIN_AUDIT_COLUMNS = [
    "login",
    "success",
    "reason",
    "ipAddress",
    "userAgent",
    "createdAt",
]

POSTGRES_ROW_NAME_ALIASES = {
    key.lower(): key
    for key in {
        "id",
        "companyId",
        "isPlatformAdmin",
        "ownerUserId",
        "userId",
        "customerId",
        "vehicleId",
        "budgetId",
        "subscriptionId",
        "actorUserId",
        "targetId",
        "targetCompanyId",
        "passwordHash",
        "accessLevel",
        "tokenHash",
        "expiresAt",
        "lastSeenAt",
        "appliedAt",
        "ipAddress",
        "userAgent",
        "clientName",
        "clientEmail",
        "clientPhone",
        "clientZip",
        "clientStreet",
        "clientNumber",
        "clientAddress",
        "clientDistrict",
        "clientState",
        "vehicleBrand",
        "vehicleModel",
        "vehicleYear",
        "vehicleColor",
        "vehicleKm",
        "laborValue",
        "partsValue",
        "approvedAt",
        "entryDate",
        "expectedDeliveryDate",
        "completedAt",
        "problemDescription",
        "serviceDescription",
        "internalNotes",
        "totalAmount",
        "costPrice",
        "salePrice",
        "stockQuantity",
        "serialNumber",
        "corporateName",
        "tradeName",
        "sellerName",
        "competenceDate",
        "invoiceNumber",
        "supplierId",
        "supplierCnpj",
        "supplierName",
        "billingCycle",
        "providerCustomerId",
        "providerSubscriptionId",
        "currentPeriodStart",
        "currentPeriodEnd",
        "trialEndsAt",
        "providerPaymentId",
        "providerCheckoutId",
        "initPoint",
        "sandboxInitPoint",
        "requestPayload",
        "responsePayload",
        "eventId",
        "eventType",
        "resourceId",
        "requestId",
        "signatureTs",
        "receivedAt",
        "processedAt",
        "paidAt",
        "createdAt",
        "updatedAt",
        "companyName",
        "companyDocument",
        "subscriptionPlan",
        "subscriptionStatus",
        "userCount",
        "budgetCount",
        "approvedBudgetCount",
        "lastPaymentAt",
        "targetCompanyName",
        "vehicleCount",
        "serviceOrderCount",
    }
}


class PostgresCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None

    def execute(self, sql, params=None):
        sql = normalize_postgres_sql(sql)
        wants_id = should_return_insert_id(sql)
        if wants_id:
            sql = f"{sql.rstrip().rstrip(';')} RETURNING id"
        self.cursor.execute(sql, tuple(params or ()))
        self.lastrowid = None
        if wants_id:
            row = self.cursor.fetchone()
            self.lastrowid = row[0] if row else None
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        return self._row_to_dict(row) if row is not None else None

    def fetchall(self):
        return [self._row_to_dict(row) for row in self.cursor.fetchall()]

    def _row_to_dict(self, row):
        if self.cursor.description is None:
            return row
        names = [
            POSTGRES_ROW_NAME_ALIASES.get(column.name, column.name)
            for column in self.cursor.description
        ]
        return dict(zip(names, row))


class PostgresConnection:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        cursor = PostgresCursor(self.conn.cursor())
        return cursor.execute(sql, params)

    def executescript(self, sql):
        with self.conn.cursor() as cursor:
            cursor.execute(sql)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()


def postgres_module():
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise RuntimeError('DATABASE_URL exige a dependência "psycopg[binary]".') from exc
    return psycopg


def is_integrity_error(error):
    if isinstance(error, sqlite3.IntegrityError):
        return True
    if not DATABASE_URL:
        return False
    try:
        psycopg = postgres_module()
    except RuntimeError:
        return False
    return isinstance(error, psycopg.errors.IntegrityError)


def translate_placeholders(sql):
    result = []
    in_single = False
    in_double = False
    for char in sql:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(char)
    return "".join(result)


def normalize_postgres_sql(sql):
    normalized = translate_placeholders(str(sql))
    normalized = re.sub(r"datetime\(([^)]+)\)", r"\1", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+COLLATE\s+NOCASE", "", normalized, flags=re.IGNORECASE)
    return normalized


def should_return_insert_id(sql):
    compact = " ".join(str(sql).strip().split())
    return (
        compact.upper().startswith("INSERT INTO ")
        and " RETURNING " not in compact.upper()
        and not re.search(r"\bON\s+CONFLICT\b", compact, flags=re.IGNORECASE)
        and " VALUES " in compact.upper()
    )


def connect():
    if DATABASE_URL:
        psycopg = postgres_module()
        return PostgresConnection(psycopg.connect(DATABASE_URL))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn, table):
    if DATABASE_URL:
        rows = conn.execute(
            """
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table,),
        ).fetchall()
        return {row["name"] for row in rows}
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def canonical_column_names(columns):
    return {
        POSTGRES_ROW_NAME_ALIASES.get(str(column).lower(), str(column))
        for column in columns
    }


def list_tables(conn):
    if DATABASE_URL:
        rows = conn.execute(
            """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        ).fetchall()
        return {row["name"] for row in rows}
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def readiness_report():
    checks = []
    failures = []

    def add_check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(f"{name}: {detail}")

    backend = "postgresql" if DATABASE_URL else "sqlite"
    try:
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
            add_check("database_connection", True, backend)

            tables = list_tables(conn)
            missing_tables = sorted(set(REQUIRED_SCHEMA_COLUMNS) - tables)
            add_check("required_tables", not missing_tables, ", ".join(missing_tables))

            for table, expected_columns in REQUIRED_SCHEMA_COLUMNS.items():
                if table not in tables:
                    continue
                columns = canonical_column_names(table_columns(conn, table))
                missing = sorted(expected_columns - columns)
                add_check(f"columns:{table}", not missing, ", ".join(missing))

            if "schema_migrations" in tables:
                rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
                migrations = {row["version"] for row in rows}
                missing_migrations = sorted(REQUIRED_SCHEMA_MIGRATIONS - migrations)
                add_check("schema_migrations", not missing_migrations, ", ".join(missing_migrations))
    except Exception as error:
        add_check("database_connection", False, str(error))

    online = APP_ENV in ONLINE_ENVS
    add_check("admin_email", not (online and DEFAULT_ADMIN_EMAIL == "master@oficina.local"), "default admin email")
    add_check("admin_password", not (online and DEFAULT_ADMIN_PASSWORD == "Master@123"), "default admin password")
    add_check("production_database", not (APP_ENV == "production" and not DATABASE_URL), "DATABASE_URL required")
    add_check("billing_provider", BILLING_PROVIDER in {"manual", "mercadopago"}, BILLING_PROVIDER)
    if APP_ENV == "production":
        add_check("billing_provider_production", BILLING_PROVIDER == "mercadopago", "mercadopago required")
        add_check("mercadopago_access_token", bool(MERCADOPAGO_ACCESS_TOKEN), "required")
        add_check("mercadopago_webhook_secret", bool(MERCADOPAGO_WEBHOOK_SECRET), "required")
        add_check("public_app_url", PUBLIC_APP_URL.startswith("https://"), "HTTPS required")

    return {
        "ok": not failures,
        "environment": APP_ENV,
        "databaseBackend": backend,
        "billingProvider": BILLING_PROVIDER,
        "checks": checks,
    }


def ensure_column(conn, table, column, definition):
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password, stored_hash):
    stored = str(stored_hash or "")
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = stored.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                str(password or "").encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except (ValueError, TypeError):
            return False
    legacy_digest = hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_digest, stored)


def password_needs_rehash(stored_hash):
    stored = str(stored_hash or "")
    if not stored.startswith("pbkdf2_sha256$"):
        return True
    try:
        _, iterations, _, _ = stored.split("$", 3)
        return int(iterations) < PASSWORD_HASH_ITERATIONS
    except (ValueError, TypeError):
        return True


def hash_token(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    now = time.time()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_sessions (tokenHash, userId, expiresAt, createdAt, lastSeenAt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (hash_token(token), int(user_id), now + SESSION_TTL_SECONDS, now, now),
        )
    return token


def get_session_user(token):
    token_hash = hash_token(token)
    now = time.time()
    with connect() as conn:
        session = conn.execute(
            "SELECT * FROM user_sessions WHERE tokenHash = ?",
            (token_hash,),
        ).fetchone()

    if session is None:
        return None

    if float(session["expiresAt"] or 0) < now:
        with connect() as conn:
            conn.execute("DELETE FROM user_sessions WHERE tokenHash = ?", (token_hash,))
        return None

    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                users.*,
                companies.name AS companyName,
                subscriptions.plan AS subscriptionPlan,
                subscriptions.status AS subscriptionStatus,
                subscriptions.billingCycle,
                subscriptions.currentPeriodStart,
                subscriptions.currentPeriodEnd,
                subscriptions.trialEndsAt
            FROM users
            LEFT JOIN companies ON companies.id = users.companyId
            LEFT JOIN subscriptions ON subscriptions.id = (
                SELECT id FROM subscriptions AS latest_subscriptions
                WHERE latest_subscriptions.companyId = users.companyId
                ORDER BY datetime(latest_subscriptions.createdAt) DESC, latest_subscriptions.id DESC
                LIMIT 1
            )
            WHERE users.id = ?
            """,
            (session["userId"],),
        ).fetchone()

    user = row_to_user(row)
    if not user or user.get("blocked"):
        with connect() as conn:
            conn.execute("DELETE FROM user_sessions WHERE tokenHash = ?", (token_hash,))
        return None

    with connect() as conn:
        conn.execute(
            """
            UPDATE user_sessions
            SET expiresAt = ?, lastSeenAt = ?
            WHERE tokenHash = ?
            """,
            (now + SESSION_TTL_SECONDS, now, token_hash),
        )
    return user


def delete_session(token):
    if not token:
        return
    with connect() as conn:
        conn.execute("DELETE FROM user_sessions WHERE tokenHash = ?", (hash_token(token),))


def prune_expired_sessions():
    with connect() as conn:
        conn.execute("DELETE FROM user_sessions WHERE expiresAt < ?", (time.time(),))


def is_login_locked(conn, login):
    if not login:
        return False
    now = time.time()
    since = now - LOGIN_WINDOW_SECONDS
    rows = conn.execute(
        """
        SELECT success, createdAt
        FROM login_audit
        WHERE login = ? AND createdAt >= ?
        ORDER BY createdAt DESC
        LIMIT ?
        """,
        (login, since, LOGIN_MAX_ATTEMPTS),
    ).fetchall()
    if len(rows) < LOGIN_MAX_ATTEMPTS:
        return False
    if not all(not bool(row["success"]) for row in rows):
        return False
    latest_failure = float(rows[0]["createdAt"] or 0)
    return latest_failure >= now - LOGIN_LOCK_SECONDS


def record_login_attempt(conn, login, success, reason, ip_address="", user_agent=""):
    conn.execute(
        """
        INSERT INTO login_audit (login, success, reason, ipAddress, userAgent, createdAt)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(login or "").lower().strip(),
            bool(success),
            str(reason or "").strip(),
            str(ip_address or "").strip(),
            str(user_agent or "").strip()[:500],
            time.time(),
        ),
    )


def is_platform_admin(user):
    return bool(user and user.get("isPlatformAdmin"))


def normalize_plan_code(plan):
    code = str(plan or "trial").strip().lower()
    return code if code in PLAN_CATALOG else "trial"


def normalize_billing_cycle(cycle):
    code = str(cycle or "monthly").strip().lower()
    return code if code in BILLING_CYCLES else "monthly"


def plan_payload(plan_code, billing_cycle="monthly"):
    code = normalize_plan_code(plan_code)
    cycle = normalize_billing_cycle(billing_cycle)
    plan = PLAN_CATALOG[code]
    return {
        **plan,
        "billingCycle": cycle,
        "billingCycleLabel": BILLING_CYCLES[cycle],
        "currentPrice": plan["prices"].get(cycle, 0.0),
    }


def latest_subscription_join():
    return """
        LEFT JOIN subscriptions ON subscriptions.id = (
            SELECT id FROM subscriptions AS latest_subscriptions
            WHERE latest_subscriptions.companyId = users.companyId
            ORDER BY datetime(latest_subscriptions.createdAt) DESC, latest_subscriptions.id DESC
            LIMIT 1
        )
    """


def user_plan(user):
    return plan_payload(user.get("subscriptionPlan"), user.get("billingCycle")) if user else plan_payload("trial")


def plan_has_feature(user, feature):
    if is_platform_admin(user):
        return True
    return feature in user_plan(user)["features"]


def subscription_allows_write(user):
    if is_platform_admin(user):
        return True
    return str(user.get("subscriptionStatus") or "").strip() in ACTIVE_SUBSCRIPTION_STATUSES


def subscription_block_message(user):
    status = str(user.get("subscriptionStatus") or "sem status")
    return f"Assinatura {status}. Regularize o plano para continuar alterando dados."


def load_postgres_baseline_sql():
    path = ROOT / "migrations" / "20260609_web_saas_baseline.postgres.sql"
    sql = path.read_text(encoding="utf-8")
    sql = re.sub(r"^\s*BEGIN;\s*$", "", sql, flags=re.IGNORECASE | re.MULTILINE)
    sql = re.sub(r"^\s*COMMIT;\s*$", "", sql, flags=re.IGNORECASE | re.MULTILINE)
    return sql


def init_postgres_db():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with connect() as conn:
        conn.executescript(load_postgres_baseline_sql())
        conn.execute(
            """
            INSERT INTO companies (name, createdAt)
            SELECT ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM companies)
            """,
            ("Oficina Pro Local", now),
        )
        default_company = conn.execute(
            "SELECT id FROM companies ORDER BY id LIMIT 1"
        ).fetchone()
        default_company_id = int(default_company["id"])

        master_exists = conn.execute(
            "SELECT 1 FROM users WHERE lower(email) = lower(?)",
            (DEFAULT_ADMIN_EMAIL,),
        ).fetchone()
        if not master_exists:
            conn.execute(
                """
                INSERT INTO users (
                    companyId, isPlatformAdmin, name, username, email, passwordHash,
                    role, accessLevel, blocked, createdAt
                )
                VALUES (?, ?, ?, ?, ?, ?, 'admin', 'administrador', ?, ?)
                """,
                (
                    default_company_id,
                    True,
                    DEFAULT_ADMIN_NAME,
                    DEFAULT_ADMIN_USERNAME,
                    DEFAULT_ADMIN_EMAIL,
                    hash_password(DEFAULT_ADMIN_PASSWORD),
                    False,
                    now,
                ),
            )

        conn.execute(
            """
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), ?),
                companyId = COALESCE(companyId, ?),
                isPlatformAdmin = ?
            WHERE lower(email) = lower(?)
            """,
            (DEFAULT_ADMIN_USERNAME, default_company_id, True, DEFAULT_ADMIN_EMAIL),
        )
        conn.execute(
            """
            UPDATE companies
            SET ownerUserId = COALESCE(
                ownerUserId,
                (SELECT id FROM users WHERE lower(email) = lower(?) LIMIT 1)
            )
            WHERE id = ?
            """,
            (DEFAULT_ADMIN_EMAIL, default_company_id),
        )
        conn.execute(
            """
            INSERT INTO subscriptions (companyId, plan, status, createdAt)
            SELECT id, 'homologacao', 'trial', ?
            FROM companies
            WHERE NOT EXISTS (
                SELECT 1 FROM subscriptions WHERE subscriptions.companyId = companies.id
            )
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('accessLevels', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (json.dumps(DEFAULT_ACCESS_LEVELS, ensure_ascii=False),),
        )
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('permissions', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (json.dumps(DEFAULT_PERMISSIONS, ensure_ascii=False),),
        )


def init_db():
    if DATABASE_URL:
        init_postgres_db()
        return

    with connect() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                document TEXT,
                phone TEXT,
                ownerUserId INTEGER,
                createdAt TEXT,
                updatedAt TEXT
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                appliedAt TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                isPlatformAdmin INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                username TEXT,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                passwordHash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                accessLevel TEXT NOT NULL DEFAULT 'analista',
                blocked INTEGER NOT NULL DEFAULT 0,
                createdAt TEXT,
                updatedAt TEXT
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tokenHash TEXT NOT NULL UNIQUE,
                userId INTEGER NOT NULL,
                expiresAt REAL NOT NULL,
                createdAt REAL NOT NULL,
                lastSeenAt REAL NOT NULL,
                FOREIGN KEY (userId) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(userId);
            CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expiresAt);

            CREATE TABLE IF NOT EXISTS login_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                ipAddress TEXT,
                userAgent TEXT,
                createdAt REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_login_audit_login_created ON login_audit(login, createdAt);
            CREATE INDEX IF NOT EXISTS idx_login_audit_created ON login_audit(createdAt);

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                userId INTEGER NOT NULL,
                clientName TEXT NOT NULL,
                clientEmail TEXT,
                clientPhone TEXT,
                clientZip TEXT,
                clientStreet TEXT,
                clientNumber TEXT,
                clientAddress TEXT,
                clientDistrict TEXT,
                clientState TEXT,
                vehicleBrand TEXT,
                vehicleModel TEXT,
                vehicleYear TEXT,
                vehicle TEXT,
                plate TEXT,
                vehicleColor TEXT,
                vehicleKm TEXT,
                parts TEXT NOT NULL DEFAULT '[]',
                labor TEXT NOT NULL DEFAULT '[]',
                description TEXT,
                laborValue REAL NOT NULL DEFAULT 0,
                partsValue REAL NOT NULL DEFAULT 0,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'pendente',
                approvedAt TEXT,
                createdAt TEXT,
                updatedAt TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_budgets_user ON budgets(userId);
            CREATE INDEX IF NOT EXISTS idx_budgets_status ON budgets(status);
            CREATE INDEX IF NOT EXISTS idx_budgets_created ON budgets(createdAt);
            CREATE INDEX IF NOT EXISTS idx_budgets_approved ON budgets(approvedAt);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
                ON users(lower(username))
                WHERE username IS NOT NULL AND trim(username) <> '';

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                zip TEXT,
                street TEXT,
                number TEXT,
                district TEXT,
                state TEXT,
                notes TEXT,
                createdAt TEXT,
                updatedAt TEXT
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                customerId INTEGER,
                brand TEXT,
                model TEXT,
                year TEXT,
                plate TEXT,
                color TEXT,
                km TEXT,
                notes TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (customerId) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS service_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                budgetId INTEGER,
                customerId INTEGER,
                vehicleId INTEGER,
                number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'aberta',
                priority TEXT NOT NULL DEFAULT 'normal',
                entryDate TEXT,
                expectedDeliveryDate TEXT,
                completedAt TEXT,
                problemDescription TEXT,
                serviceDescription TEXT,
                internalNotes TEXT,
                parts TEXT NOT NULL DEFAULT '[]',
                labor TEXT NOT NULL DEFAULT '[]',
                totalAmount REAL NOT NULL DEFAULT 0,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (budgetId) REFERENCES budgets(id),
                FOREIGN KEY (customerId) REFERENCES customers(id),
                FOREIGN KEY (vehicleId) REFERENCES vehicles(id)
            );

            CREATE INDEX IF NOT EXISTS idx_customers_company ON customers(companyId);
            CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_vehicles_company ON vehicles(companyId);
            CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(customerId);
            CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_service_orders_company ON service_orders(companyId);
            CREATE INDEX IF NOT EXISTS idx_service_orders_budget ON service_orders(budgetId);
            CREATE INDEX IF NOT EXISTS idx_service_orders_status ON service_orders(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_service_orders_number_company ON service_orders(companyId, number);

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS parts_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                brand TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                costPrice REAL NOT NULL DEFAULT 0,
                salePrice REAL NOT NULL DEFAULT 0,
                stockQuantity INTEGER NOT NULL DEFAULT 0,
                serialNumber TEXT,
                createdAt TEXT,
                updatedAt TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_parts_inventory_code ON parts_inventory(code);
            CREATE INDEX IF NOT EXISTS idx_parts_inventory_description ON parts_inventory(description COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                cnpj TEXT NOT NULL UNIQUE,
                corporateName TEXT NOT NULL,
                tradeName TEXT NOT NULL,
                phone TEXT NOT NULL,
                sellerName TEXT NOT NULL,
                createdAt TEXT,
                updatedAt TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_suppliers_cnpj ON suppliers(cnpj);
            CREATE INDEX IF NOT EXISTS idx_suppliers_trade_name ON suppliers(tradeName COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_suppliers_corporate_name ON suppliers(corporateName COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS accounts_payable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER,
                description TEXT NOT NULL,
                entryDate TEXT NOT NULL,
                competenceDate TEXT NOT NULL,
                category TEXT NOT NULL,
                invoiceNumber TEXT,
                supplierId INTEGER,
                supplierCnpj TEXT NOT NULL,
                supplierName TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                notes TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (supplierId) REFERENCES suppliers(id)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER NOT NULL,
                plan TEXT NOT NULL DEFAULT 'trial',
                status TEXT NOT NULL DEFAULT 'trial',
                billingCycle TEXT NOT NULL DEFAULT 'monthly',
                provider TEXT,
                providerCustomerId TEXT,
                providerSubscriptionId TEXT,
                currentPeriodStart TEXT,
                currentPeriodEnd TEXT,
                trialEndsAt TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (companyId) REFERENCES companies(id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER NOT NULL,
                subscriptionId INTEGER,
                provider TEXT,
                providerPaymentId TEXT,
                amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                paidAt TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (companyId) REFERENCES companies(id),
                FOREIGN KEY (subscriptionId) REFERENCES subscriptions(id)
            );

            CREATE TABLE IF NOT EXISTS billing_checkout_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyId INTEGER NOT NULL,
                subscriptionId INTEGER,
                plan TEXT NOT NULL,
                billingCycle TEXT NOT NULL DEFAULT 'monthly',
                provider TEXT NOT NULL,
                providerCheckoutId TEXT,
                initPoint TEXT,
                sandboxInitPoint TEXT,
                amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'created',
                requestPayload TEXT NOT NULL DEFAULT '{}',
                responsePayload TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                FOREIGN KEY (companyId) REFERENCES companies(id),
                FOREIGN KEY (subscriptionId) REFERENCES subscriptions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_billing_checkout_company ON billing_checkout_requests(companyId);
            CREATE INDEX IF NOT EXISTS idx_billing_checkout_status ON billing_checkout_requests(status);
            CREATE INDEX IF NOT EXISTS idx_billing_checkout_created ON billing_checkout_requests(createdAt);

            CREATE TABLE IF NOT EXISTS billing_webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                eventId TEXT,
                eventType TEXT,
                action TEXT,
                resourceId TEXT,
                requestId TEXT,
                signatureTs TEXT,
                payload TEXT NOT NULL DEFAULT '{}',
                receivedAt TEXT,
                processedAt TEXT,
                status TEXT NOT NULL DEFAULT 'received',
                error TEXT
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_webhook_provider_event
                ON billing_webhook_events(provider, eventId)
                WHERE eventId IS NOT NULL AND trim(eventId) <> '';
            CREATE INDEX IF NOT EXISTS idx_billing_webhook_received ON billing_webhook_events(receivedAt);

            CREATE TABLE IF NOT EXISTS platform_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actorUserId INTEGER,
                actorEmail TEXT,
                action TEXT NOT NULL,
                targetType TEXT NOT NULL,
                targetId INTEGER,
                targetCompanyId INTEGER,
                details TEXT NOT NULL DEFAULT '{}',
                createdAt TEXT,
                FOREIGN KEY (actorUserId) REFERENCES users(id),
                FOREIGN KEY (targetCompanyId) REFERENCES companies(id)
            );

            CREATE INDEX IF NOT EXISTS idx_accounts_payable_created ON accounts_payable(createdAt);
            CREATE INDEX IF NOT EXISTS idx_accounts_payable_due ON accounts_payable(competenceDate);
            CREATE INDEX IF NOT EXISTS idx_accounts_payable_supplier ON accounts_payable(supplierName COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_company ON subscriptions(companyId);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
            CREATE INDEX IF NOT EXISTS idx_payments_company ON payments(companyId);
            CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
            CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON platform_audit_log(createdAt);
            CREATE INDEX IF NOT EXISTS idx_platform_audit_company ON platform_audit_log(targetCompanyId);
            """
        )
        ensure_column(conn, "users", "companyId", "INTEGER")
        ensure_column(conn, "users", "isPlatformAdmin", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "budgets", "companyId", "INTEGER")
        ensure_column(conn, "customers", "companyId", "INTEGER")
        ensure_column(conn, "vehicles", "companyId", "INTEGER")
        ensure_column(conn, "service_orders", "companyId", "INTEGER")
        ensure_column(conn, "parts_inventory", "companyId", "INTEGER")
        ensure_column(conn, "suppliers", "companyId", "INTEGER")
        ensure_column(conn, "accounts_payable", "companyId", "INTEGER")
        ensure_column(conn, "subscriptions", "billingCycle", "TEXT NOT NULL DEFAULT 'monthly'")
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_users_company ON users(companyId);
            CREATE INDEX IF NOT EXISTS idx_budgets_company ON budgets(companyId);
            CREATE INDEX IF NOT EXISTS idx_customers_company ON customers(companyId);
            CREATE INDEX IF NOT EXISTS idx_vehicles_company ON vehicles(companyId);
            CREATE INDEX IF NOT EXISTS idx_service_orders_company ON service_orders(companyId);
            CREATE INDEX IF NOT EXISTS idx_parts_inventory_company ON parts_inventory(companyId);
            CREATE INDEX IF NOT EXISTS idx_suppliers_company ON suppliers(companyId);
            CREATE INDEX IF NOT EXISTS idx_accounts_payable_company ON accounts_payable(companyId);
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
            VALUES ('20260609_web_saas_baseline', datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
            VALUES ('20260609_db_sessions', datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
            VALUES ('20260609_login_audit', datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
            VALUES ('20260610_billing_webhooks', datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, appliedAt)
            VALUES ('20260610_billing_checkout_requests', datetime('now'))
            """
        )

        conn.execute(
            """
            INSERT INTO companies (name, createdAt)
            SELECT 'Oficina Pro Local', datetime('now')
            WHERE NOT EXISTS (SELECT 1 FROM companies)
            """
        )
        default_company = conn.execute(
            "SELECT id FROM companies ORDER BY id LIMIT 1"
        ).fetchone()
        default_company_id = int(default_company["id"])

        for table in ("users", "budgets", "parts_inventory", "suppliers", "accounts_payable"):
            conn.execute(
                f"UPDATE {table} SET companyId = ? WHERE companyId IS NULL",
                (default_company_id,),
            )

        master_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        conn.execute(
            """
            INSERT INTO users (companyId, isPlatformAdmin, name, username, email, passwordHash, role, accessLevel, blocked, createdAt)
            SELECT ?, 1, ?, ?, ?, ?, 'admin', 'administrador', 0, datetime('now')
            WHERE NOT EXISTS (
                SELECT 1 FROM users WHERE lower(email) = lower(?)
            )
            """,
            (
                default_company_id,
                DEFAULT_ADMIN_NAME,
                DEFAULT_ADMIN_USERNAME,
                DEFAULT_ADMIN_EMAIL,
                master_hash,
                DEFAULT_ADMIN_EMAIL,
            ),
        )
        conn.execute(
            """
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), ?),
                companyId = COALESCE(companyId, ?),
                isPlatformAdmin = 1
            WHERE lower(email) = lower(?)
            """,
            (DEFAULT_ADMIN_USERNAME, default_company_id, DEFAULT_ADMIN_EMAIL),
        )
        conn.execute(
            """
            UPDATE companies
            SET ownerUserId = COALESCE(
                ownerUserId,
                (SELECT id FROM users WHERE lower(email) = lower(?) LIMIT 1)
            )
            WHERE id = ?
            """,
            (DEFAULT_ADMIN_EMAIL, default_company_id),
        )
        conn.execute(
            """
            INSERT INTO subscriptions (companyId, plan, status, createdAt)
            SELECT id, 'homologacao', 'trial', datetime('now')
            FROM companies
            WHERE NOT EXISTS (
                SELECT 1 FROM subscriptions WHERE subscriptions.companyId = companies.id
            )
            """
        )
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('accessLevels', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (json.dumps({
                "administrador": "Administrador",
                "financeiro": "Financeiro",
                "analista": "Analista",
            }, ensure_ascii=False),),
        )
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('permissions', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (json.dumps({
                "administrador": [
                    "dashboard_view",
                    "budgets_view",
                    "budgets_manage",
                    "budgets_approve",
                    "budgets_delete",
                    "inventory_view",
                    "inventory_manage",
                    "billing_view",
                    "billing_edit",
                ],
                "financeiro": ["dashboard_view", "billing_view"],
                "analista": ["dashboard_view", "budgets_view", "budgets_manage"],
            }, ensure_ascii=False),),
        )


def row_to_user(row):
    if row is None:
        return None
    item = dict(row)
    item.pop("passwordHash", None)
    item["blocked"] = bool(item.get("blocked"))
    item["isPlatformAdmin"] = bool(item.get("isPlatformAdmin"))
    item["subscriptionPlan"] = normalize_plan_code(item.get("subscriptionPlan"))
    item["billingCycle"] = normalize_billing_cycle(item.get("billingCycle"))
    item["subscriptionStatus"] = item.get("subscriptionStatus") or "trial"
    item["plan"] = plan_payload(item["subscriptionPlan"], item["billingCycle"])
    return item


def parse_json_array(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "[]")
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def row_to_budget(row):
    if row is None:
        return None
    item = dict(row)
    for key in ("parts", "labor"):
        item[key] = parse_json_array(item.get(key))
    return item


def row_to_customer(row):
    return dict(row) if row is not None else None


def row_to_vehicle(row):
    return dict(row) if row is not None else None


def row_to_service_order(row):
    if row is None:
        return None
    item = dict(row)
    for key in ("parts", "labor"):
        item[key] = parse_json_array(item.get(key))
    return item


def row_to_part(row):
    return dict(row) if row is not None else None


def row_to_supplier(row):
    return dict(row) if row is not None else None


def row_to_payable(row):
    return dict(row) if row is not None else None


def row_to_subscription(row):
    return dict(row) if row is not None else None


def row_to_payment(row):
    return dict(row) if row is not None else None


def row_to_checkout_request(row):
    return dict(row) if row is not None else None


def normalize_user(payload, existing=None):
    data = {key: payload.get(key) for key in USER_COLUMNS}
    data["email"] = str(data.get("email") or "").lower().strip()
    data["username"] = str(data.get("username") or "").lower().strip() or None
    password = payload.get("password")
    if password:
        data["passwordHash"] = hash_password(password)
    elif existing:
        data["passwordHash"] = existing["passwordHash"]
    else:
        data["passwordHash"] = ""
    data["blocked"] = bool(data.get("blocked"))
    data["isPlatformAdmin"] = bool(data.get("isPlatformAdmin"))
    return data


def normalize_company(payload):
    return {
        "name": str(payload.get("companyName") or payload.get("name") or "").strip(),
        "document": str(payload.get("document") or "").strip(),
        "phone": str(payload.get("phone") or "").strip(),
    }


def normalize_budget(payload):
    data = {key: payload.get(key) for key in BUDGET_COLUMNS}
    data["userId"] = int(data.get("userId") or 0)
    data["parts"] = json.dumps(data.get("parts") or [], ensure_ascii=False)
    data["labor"] = json.dumps(data.get("labor") or [], ensure_ascii=False)
    data["laborValue"] = float(data.get("laborValue") or 0)
    data["partsValue"] = float(data.get("partsValue") or 0)
    return data


def normalize_customer(payload):
    data = {key: payload.get(key) for key in CUSTOMER_COLUMNS}
    data["name"] = str(data.get("name") or payload.get("clientName") or "").strip()
    data["email"] = str(data.get("email") or payload.get("clientEmail") or "").lower().strip()
    data["phone"] = str(data.get("phone") or payload.get("clientPhone") or "").strip()
    data["zip"] = str(data.get("zip") or payload.get("clientZip") or "").strip()
    data["street"] = str(data.get("street") or payload.get("clientStreet") or payload.get("clientAddress") or "").strip()
    data["number"] = str(data.get("number") or payload.get("clientNumber") or "").strip()
    data["district"] = str(data.get("district") or payload.get("clientDistrict") or "").strip()
    data["state"] = str(data.get("state") or payload.get("clientState") or "").upper().strip()
    data["notes"] = str(data.get("notes") or "").strip()
    return data


def normalize_vehicle(payload):
    data = {key: payload.get(key) for key in VEHICLE_COLUMNS}
    data["customerId"] = int(data.get("customerId") or 0) or None
    data["brand"] = str(data.get("brand") or payload.get("vehicleBrand") or "").strip()
    data["model"] = str(data.get("model") or payload.get("vehicleModel") or payload.get("vehicle") or "").strip()
    data["year"] = str(data.get("year") or payload.get("vehicleYear") or "").strip()
    data["plate"] = str(data.get("plate") or "").upper().replace("-", "").strip()
    data["color"] = str(data.get("color") or payload.get("vehicleColor") or "").strip()
    data["km"] = str(data.get("km") or payload.get("vehicleKm") or "").strip()
    data["notes"] = str(data.get("notes") or "").strip()
    return data


def normalize_service_order(payload):
    data = {key: payload.get(key) for key in SERVICE_ORDER_COLUMNS}
    for key in ("budgetId", "customerId", "vehicleId"):
        data[key] = int(data.get(key) or 0) or None
    data["number"] = str(data.get("number") or "").strip()
    data["status"] = str(data.get("status") or "aberta").strip()
    data["priority"] = str(data.get("priority") or "normal").strip()
    data["problemDescription"] = str(data.get("problemDescription") or "").strip()
    data["serviceDescription"] = str(data.get("serviceDescription") or "").strip()
    data["internalNotes"] = str(data.get("internalNotes") or "").strip()
    data["parts"] = json.dumps(data.get("parts") or [], ensure_ascii=False)
    data["labor"] = json.dumps(data.get("labor") or [], ensure_ascii=False)
    data["totalAmount"] = float(data.get("totalAmount") or 0)
    return data


def normalize_part(payload, existing_code=None):
    data = {key: payload.get(key) for key in PART_COLUMNS}
    data["brand"] = str(data.get("brand") or "").strip()
    data["code"] = str(data.get("code") or existing_code or "").strip()
    data["description"] = str(data.get("description") or "").strip()
    data["costPrice"] = float(data.get("costPrice") or 0)
    data["salePrice"] = float(data.get("salePrice") or 0)
    data["stockQuantity"] = int(data.get("stockQuantity") or 0)
    data["serialNumber"] = str(data.get("serialNumber") or "").strip()
    return data


def normalize_supplier(payload):
    data = {key: payload.get(key) for key in SUPPLIER_COLUMNS}
    data["cnpj"] = str(data.get("cnpj") or "").strip()
    data["corporateName"] = str(data.get("corporateName") or "").strip()
    data["tradeName"] = str(data.get("tradeName") or "").strip()
    data["phone"] = str(data.get("phone") or "").strip()
    data["sellerName"] = str(data.get("sellerName") or "").strip()
    return data


def normalize_payable(payload):
    data = {key: payload.get(key) for key in PAYABLE_COLUMNS}
    data["description"] = str(data.get("description") or "").strip()
    data["entryDate"] = str(data.get("entryDate") or "").strip()
    data["competenceDate"] = str(data.get("competenceDate") or "").strip()
    data["category"] = str(data.get("category") or "").strip()
    data["invoiceNumber"] = str(data.get("invoiceNumber") or "").strip()
    data["supplierId"] = int(data.get("supplierId") or 0) or None
    data["supplierCnpj"] = str(data.get("supplierCnpj") or "").strip()
    data["supplierName"] = str(data.get("supplierName") or "").strip()
    data["amount"] = float(data.get("amount") or 0)
    data["notes"] = str(data.get("notes") or "").strip()
    return data


def normalize_subscription(payload):
    data = {key: payload.get(key) for key in SUBSCRIPTION_COLUMNS}
    data["companyId"] = int(data.get("companyId") or 0)
    data["plan"] = normalize_plan_code(data.get("plan"))
    data["status"] = str(data.get("status") or "trial").strip()
    data["billingCycle"] = normalize_billing_cycle(data.get("billingCycle"))
    data["provider"] = str(data.get("provider") or "").strip()
    data["providerCustomerId"] = str(data.get("providerCustomerId") or "").strip()
    data["providerSubscriptionId"] = str(data.get("providerSubscriptionId") or "").strip()
    return data


def normalize_payment(payload):
    data = {key: payload.get(key) for key in PAYMENT_COLUMNS}
    data["companyId"] = int(data.get("companyId") or 0)
    data["subscriptionId"] = int(data.get("subscriptionId") or 0) or None
    data["provider"] = str(data.get("provider") or "").strip()
    data["providerPaymentId"] = str(data.get("providerPaymentId") or "").strip()
    data["amount"] = float(data.get("amount") or 0)
    data["status"] = str(data.get("status") or "pending").strip()
    return data


def normalize_checkout_plan(payload):
    plan = normalize_plan_code(payload.get("plan"))
    if plan in {"trial", "homologacao"}:
        raise ValueError("Escolha um plano comercial para contratação.")
    cycle = normalize_billing_cycle(payload.get("billingCycle"))
    plan_info = plan_payload(plan, cycle)
    amount = float(plan_info["currentPrice"] or 0)
    if amount <= 0:
        raise ValueError("Plano sem valor comercial não pode gerar cobrança.")
    return plan, cycle, plan_info, amount


def latest_company_subscription(conn, company_id):
    return conn.execute(
        """
        SELECT * FROM subscriptions
        WHERE companyId = ?
        ORDER BY datetime(createdAt) DESC, id DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()


def billing_cycle_frequency(cycle):
    return {"monthly": 1, "quarterly": 3, "yearly": 12}.get(normalize_billing_cycle(cycle), 1)


def app_return_url(path="/"):
    base = PUBLIC_APP_URL or f"http://{HOST}:{PORT}"
    return f"{base.rstrip('/')}{path}"


def mercadopago_preapproval_payload(user, plan_info):
    cycle = normalize_billing_cycle(plan_info.get("billingCycle"))
    return {
        "reason": f"Oficina Pro - {plan_info['name']} {BILLING_CYCLES[cycle]}",
        "external_reference": f"company:{user['companyId']}:plan:{plan_info['code']}:cycle:{cycle}",
        "payer_email": user.get("email") or "",
        "back_url": app_return_url("/?billing=return"),
        "auto_recurring": {
            "frequency": billing_cycle_frequency(cycle),
            "frequency_type": "months",
            "transaction_amount": float(plan_info["currentPrice"]),
            "currency_id": "BRL",
        },
    }


def mercadopago_api_post(path, payload):
    if not MERCADOPAGO_ACCESS_TOKEN:
        raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN não configurado.")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = url_request.Request(
        f"https://api.mercadopago.com{path}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with url_request.urlopen(req, timeout=20) as response:
            content = response.read().decode("utf-8")
            return json.loads(content or "{}")
    except url_error.HTTPError as exc:
        content = exc.read().decode("utf-8")
        try:
            details = json.loads(content or "{}")
        except json.JSONDecodeError:
            details = {"error": content}
        raise RuntimeError(f"Mercado Pago recusou a solicitação: HTTP {exc.code} {details}") from exc


def create_billing_checkout_request(conn, user, payload):
    plan, cycle, plan_info, amount = normalize_checkout_plan(payload)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    subscription = latest_company_subscription(conn, user["companyId"])
    subscription_id = subscription["id"] if subscription else None
    provider = "mercadopago" if BILLING_PROVIDER == "mercadopago" else "manual"
    request_payload = {}
    response_payload = {}
    provider_checkout_id = ""
    init_point = ""
    sandbox_init_point = ""
    status = "manual_pending"
    error = ""

    if provider == "mercadopago":
        request_payload = mercadopago_preapproval_payload(user, plan_info)
        try:
            response_payload = mercadopago_api_post("/preapproval", request_payload)
            provider_checkout_id = str(response_payload.get("id") or "")
            init_point = str(response_payload.get("init_point") or "")
            sandbox_init_point = str(response_payload.get("sandbox_init_point") or "")
            status = "provider_pending"
        except RuntimeError as exc:
            response_payload = {"error": str(exc)}
            status = "provider_error"
            error = str(exc)

    data = {
        "companyId": user["companyId"],
        "subscriptionId": subscription_id,
        "plan": plan,
        "billingCycle": cycle,
        "provider": provider,
        "providerCheckoutId": provider_checkout_id,
        "initPoint": init_point,
        "sandboxInitPoint": sandbox_init_point,
        "amount": amount,
        "status": status,
        "requestPayload": json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
        "responsePayload": json.dumps(response_payload, ensure_ascii=False, sort_keys=True),
        "error": error,
        "createdAt": now,
        "updatedAt": now,
    }
    columns = ", ".join(BILLING_CHECKOUT_COLUMNS)
    marks = ", ".join(["?"] * len(BILLING_CHECKOUT_COLUMNS))
    cursor = conn.execute(
        f"INSERT INTO billing_checkout_requests ({columns}) VALUES ({marks})",
        [data[column] for column in BILLING_CHECKOUT_COLUMNS],
    )
    row = conn.execute(
        "SELECT * FROM billing_checkout_requests WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return row_to_checkout_request(row), plan_info


def parse_signature_header(header):
    parts = {}
    for raw_part in str(header or "").split(","):
        if "=" not in raw_part:
            continue
        key, value = raw_part.split("=", 1)
        parts[key.strip()] = value.strip()
    return parts


def mercadopago_resource_id(payload, query):
    data_id = (query.get("data.id") or query.get("id") or [""])[0]
    if not data_id and isinstance(payload.get("data"), dict):
        data_id = payload["data"].get("id") or ""
    return str(data_id or "").strip()


def mercadopago_signature_template(resource_id, request_id, timestamp):
    parts = []
    if resource_id:
        parts.append(f"id:{resource_id.lower()}")
    if request_id:
        parts.append(f"request-id:{request_id}")
    if timestamp:
        parts.append(f"ts:{timestamp}")
    return ";".join(parts) + (";" if parts else "")


def verify_mercadopago_signature(payload, query, headers):
    if not MERCADOPAGO_WEBHOOK_SECRET:
        return False, "MERCADOPAGO_WEBHOOK_SECRET não configurado."
    signature = parse_signature_header(headers.get("x-signature", ""))
    timestamp = signature.get("ts", "")
    received_hash = signature.get("v1", "")
    request_id = str(headers.get("x-request-id", "")).strip()
    resource_id = mercadopago_resource_id(payload, query)
    if not timestamp or not received_hash or not request_id or not resource_id:
        return False, "Assinatura Mercado Pago incompleta."
    template = mercadopago_signature_template(resource_id, request_id, timestamp)
    expected_hash = hmac.new(
        MERCADOPAGO_WEBHOOK_SECRET.encode("utf-8"),
        template.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return False, "Assinatura Mercado Pago inválida."
    return True, ""


def store_billing_webhook_event(conn, provider, payload, query, headers):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    resource_id = mercadopago_resource_id(payload, query)
    event_id = str(payload.get("id") or "").strip()
    event_type = str(payload.get("type") or query.get("type", [""])[0] or "").strip()
    action = str(payload.get("action") or "").strip()
    if not event_id:
        event_id = f"{event_type}:{resource_id}:{action}".strip(":")
    request_id = str(headers.get("x-request-id", "")).strip()
    signature_ts = parse_signature_header(headers.get("x-signature", "")).get("ts", "")

    existing = None
    if event_id:
        existing = conn.execute(
            "SELECT * FROM billing_webhook_events WHERE provider = ? AND eventId = ?",
            (provider, event_id),
        ).fetchone()
    if existing:
        return dict(existing), False

    data = {
        "provider": provider,
        "eventId": event_id,
        "eventType": event_type,
        "action": action,
        "resourceId": resource_id,
        "requestId": request_id,
        "signatureTs": signature_ts,
        "payload": json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
        "receivedAt": now,
        "processedAt": None,
        "status": "received",
        "error": "",
    }
    columns = ", ".join(BILLING_WEBHOOK_COLUMNS)
    marks = ", ".join(["?"] * len(BILLING_WEBHOOK_COLUMNS))
    cursor = conn.execute(
        f"INSERT INTO billing_webhook_events ({columns}) VALUES ({marks})",
        [data[column] for column in BILLING_WEBHOOK_COLUMNS],
    )
    row = conn.execute(
        "SELECT * FROM billing_webhook_events WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row), True


def row_to_audit(row):
    if row is None:
        return None
    item = dict(row)
    try:
        item["details"] = json.loads(item.get("details") or "{}")
    except json.JSONDecodeError:
        item["details"] = {}
    return item


def log_platform_audit(conn, actor, action, target_type, target_id=None, target_company_id=None, details=None):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "actorUserId": actor.get("id") if actor else None,
        "actorEmail": actor.get("email") if actor else "",
        "action": action,
        "targetType": target_type,
        "targetId": target_id,
        "targetCompanyId": target_company_id,
        "details": json.dumps(details or {}, ensure_ascii=False),
        "createdAt": now,
    }
    columns = ", ".join(AUDIT_COLUMNS)
    marks = ", ".join(["?"] * len(AUDIT_COLUMNS))
    conn.execute(
        f"INSERT INTO platform_audit_log ({columns}) VALUES ({marks})",
        [data[column] for column in AUDIT_COLUMNS],
    )


def next_part_code(conn):
    row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'parts_inventory'").fetchone()
    next_id = int(row["seq"] or 0) + 1 if row else 1
    return f"PEC-{next_id:05d}"


def next_service_order_number(conn, company_id):
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM service_orders WHERE companyId = ?",
        (company_id,),
    ).fetchone()
    next_id = int(row["total"] or 0) + 1
    return f"OS-{next_id:05d}"


def budget_total_value(budget):
    parts = json.loads(budget["parts"] or "[]") if isinstance(budget["parts"], str) else budget.get("parts") or []
    labor = json.loads(budget["labor"] or "[]") if isinstance(budget["labor"], str) else budget.get("labor") or []
    parts_total = sum(float(item.get("quantity") or 0) * float(item.get("value") or 0) for item in parts)
    labor_total = sum(float(item.get("value") or 0) for item in labor)
    return parts_total + labor_total


def upsert_customer_from_budget(conn, budget):
    email = str(budget["clientEmail"] or "").lower().strip()
    phone = str(budget["clientPhone"] or "").strip()
    row = None
    if email:
        row = conn.execute(
            "SELECT * FROM customers WHERE companyId = ? AND lower(email) = ?",
            (budget["companyId"], email),
        ).fetchone()
    if row is None and phone:
        row = conn.execute(
            "SELECT * FROM customers WHERE companyId = ? AND phone = ?",
            (budget["companyId"], phone),
        ).fetchone()

    data = normalize_customer(dict(budget))
    data["companyId"] = budget["companyId"]
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    if row:
        data["createdAt"] = row["createdAt"]
        data["updatedAt"] = now
        assignments = ", ".join([f"{column} = ?" for column in CUSTOMER_COLUMNS])
        conn.execute(
            f"UPDATE customers SET {assignments} WHERE id = ? AND companyId = ?",
            [data[column] for column in CUSTOMER_COLUMNS] + [row["id"], budget["companyId"]],
        )
        return row["id"]

    data["createdAt"] = now
    data["updatedAt"] = now
    columns = ", ".join(CUSTOMER_COLUMNS)
    marks = ", ".join(["?"] * len(CUSTOMER_COLUMNS))
    cursor = conn.execute(
        f"INSERT INTO customers ({columns}) VALUES ({marks})",
        [data[column] for column in CUSTOMER_COLUMNS],
    )
    return cursor.lastrowid


def upsert_vehicle_from_budget(conn, budget, customer_id):
    plate = str(budget["plate"] or "").upper().replace("-", "").strip()
    row = None
    if plate:
        row = conn.execute(
            "SELECT * FROM vehicles WHERE companyId = ? AND upper(replace(plate, '-', '')) = ?",
            (budget["companyId"], plate),
        ).fetchone()

    data = normalize_vehicle(dict(budget))
    data["companyId"] = budget["companyId"]
    data["customerId"] = customer_id
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    if row:
        data["createdAt"] = row["createdAt"]
        data["updatedAt"] = now
        assignments = ", ".join([f"{column} = ?" for column in VEHICLE_COLUMNS])
        conn.execute(
            f"UPDATE vehicles SET {assignments} WHERE id = ? AND companyId = ?",
            [data[column] for column in VEHICLE_COLUMNS] + [row["id"], budget["companyId"]],
        )
        return row["id"]

    data["createdAt"] = now
    data["updatedAt"] = now
    columns = ", ".join(VEHICLE_COLUMNS)
    marks = ", ".join(["?"] * len(VEHICLE_COLUMNS))
    cursor = conn.execute(
        f"INSERT INTO vehicles ({columns}) VALUES ({marks})",
        [data[column] for column in VEHICLE_COLUMNS],
    )
    return cursor.lastrowid


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def auth_token(self):
        auth_header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return ""
        return auth_header[len(prefix):].strip()

    def require_auth(self):
        user = get_session_user(self.auth_token())
        if not user:
            self.send_json({"error": "Sessão expirada ou inválida. Faça login novamente."}, 401)
            return None
        return user

    def require_plan_feature(self, user, feature, write=False):
        if not plan_has_feature(user, feature):
            plan = user_plan(user)
            self.send_json(
                {"error": f"Recurso não disponível no plano {plan['name']}."},
                403,
            )
            return False
        if write and not subscription_allows_write(user):
            self.send_json({"error": subscription_block_message(user)}, 402)
            return False
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                self.send_json({
                    "ok": True,
                    "environment": APP_ENV,
                    "databaseBackend": "postgresql" if DATABASE_URL else "sqlite",
                })
                return

            if path == "/api/ready":
                report = readiness_report()
                self.send_json(report, 200 if report["ok"] else 503)
                return

            if path == "/api/plans":
                self.send_json({
                    "plans": list(PLAN_CATALOG.values()),
                    "billingCycles": BILLING_CYCLES,
                })
                return

            auth_user = None
            if path.startswith("/api/"):
                auth_user = self.require_auth()
                if auth_user is None:
                    return
            company_id = auth_user["companyId"] if auth_user else None

            if path == "/api/subscription/current":
                self.send_json({
                    "status": auth_user.get("subscriptionStatus"),
                    "plan": user_plan(auth_user),
                    "currentPeriodStart": auth_user.get("currentPeriodStart"),
                    "currentPeriodEnd": auth_user.get("currentPeriodEnd"),
                    "trialEndsAt": auth_user.get("trialEndsAt"),
                    "canWrite": subscription_allows_write(auth_user),
                })
                return

            if path == "/api/platform/companies":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            companies.id,
                            companies.name,
                            companies.document,
                            companies.phone,
                            companies.ownerUserId,
                            companies.createdAt,
                            companies.updatedAt,
                            subscriptions.id AS subscriptionId,
                            subscriptions.plan,
                            subscriptions.status AS subscriptionStatus,
                            subscriptions.billingCycle,
                            subscriptions.currentPeriodStart,
                            subscriptions.currentPeriodEnd,
                            subscriptions.trialEndsAt,
                            COUNT(DISTINCT users.id) AS userCount,
                            COUNT(DISTINCT budgets.id) AS budgetCount,
                            COUNT(DISTINCT CASE WHEN budgets.status = 'aprovado' THEN budgets.id END) AS approvedBudgetCount,
                            MAX(payments.paidAt) AS lastPaymentAt
                        FROM companies
                        LEFT JOIN subscriptions ON subscriptions.id = (
                            SELECT id FROM subscriptions AS latest_subscriptions
                            WHERE latest_subscriptions.companyId = companies.id
                            ORDER BY datetime(latest_subscriptions.createdAt) DESC, latest_subscriptions.id DESC
                            LIMIT 1
                        )
                        LEFT JOIN users ON users.companyId = companies.id
                        LEFT JOIN budgets ON budgets.companyId = companies.id
                        LEFT JOIN payments ON payments.companyId = companies.id
                        GROUP BY companies.id, subscriptions.id
                        ORDER BY datetime(companies.createdAt) DESC, companies.id DESC
                        """
                    ).fetchall()
                self.send_json([dict(row) for row in rows])
                return

            if path == "/api/platform/subscriptions":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            subscriptions.*,
                            companies.name AS companyName,
                            companies.document AS companyDocument
                        FROM subscriptions
                        JOIN companies ON companies.id = subscriptions.companyId
                        ORDER BY datetime(subscriptions.createdAt) DESC, subscriptions.id DESC
                        """
                    ).fetchall()
                self.send_json([row_to_subscription(row) for row in rows])
                return

            if path == "/api/platform/payments":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            payments.*,
                            companies.name AS companyName,
                            subscriptions.plan AS subscriptionPlan
                        FROM payments
                        JOIN companies ON companies.id = payments.companyId
                        LEFT JOIN subscriptions ON subscriptions.id = payments.subscriptionId
                        ORDER BY datetime(payments.createdAt) DESC, payments.id DESC
                        """
                    ).fetchall()
                self.send_json([row_to_payment(row) for row in rows])
                return

            if path == "/api/platform/checkout-requests":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                limit = int(query.get("limit", ["50"])[0] or 50)
                limit = min(max(limit, 1), 100)
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            billing_checkout_requests.*,
                            companies.name AS companyName,
                            companies.document AS companyDocument
                        FROM billing_checkout_requests
                        JOIN companies ON companies.id = billing_checkout_requests.companyId
                        ORDER BY datetime(billing_checkout_requests.createdAt) DESC, billing_checkout_requests.id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                self.send_json([row_to_checkout_request(row) for row in rows])
                return

            if path == "/api/platform/audit":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                limit = int(query.get("limit", ["30"])[0] or 30)
                limit = min(max(limit, 1), 100)
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            platform_audit_log.*,
                            companies.name AS targetCompanyName
                        FROM platform_audit_log
                        LEFT JOIN companies ON companies.id = platform_audit_log.targetCompanyId
                        ORDER BY datetime(platform_audit_log.createdAt) DESC, platform_audit_log.id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                self.send_json([row_to_audit(row) for row in rows])
                return

            if path == "/api/users":
                if not self.require_plan_feature(auth_user, "users"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        "SELECT * FROM users WHERE companyId = ? ORDER BY name COLLATE NOCASE",
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_user(row) for row in rows])
                return

            if path == "/api/users/by-email":
                if not self.require_plan_feature(auth_user, "users"):
                    return
                email = (query.get("email") or [""])[0].lower().strip()
                with connect() as conn:
                    row = conn.execute(
                        "SELECT * FROM users WHERE companyId = ? AND lower(email) = ?",
                        (company_id, email),
                    ).fetchone()
                self.send_json(row_to_user(row))
                return

            if path == "/api/users/by-login":
                if not self.require_plan_feature(auth_user, "users"):
                    return
                login = (query.get("login") or [""])[0].lower().strip()
                with connect() as conn:
                    row = conn.execute(
                        """
                        SELECT * FROM users
                        WHERE companyId = ? AND (lower(email) = ? OR lower(username) = ?)
                        """,
                        (company_id, login, login),
                    ).fetchone()
                self.send_json(row_to_user(row))
                return

            if path == "/api/budgets":
                if not self.require_plan_feature(auth_user, "budgets"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        "SELECT * FROM budgets WHERE companyId = ? ORDER BY datetime(createdAt) DESC",
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_budget(row) for row in rows])
                return

            if path == "/api/customers":
                if not self.require_plan_feature(auth_user, "budgets"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            customers.*,
                            COUNT(DISTINCT vehicles.id) AS vehicleCount,
                            COUNT(DISTINCT service_orders.id) AS serviceOrderCount
                        FROM customers
                        LEFT JOIN vehicles ON vehicles.customerId = customers.id
                        LEFT JOIN service_orders ON service_orders.customerId = customers.id
                        WHERE customers.companyId = ?
                        GROUP BY customers.id
                        ORDER BY customers.name COLLATE NOCASE
                        """,
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_customer(row) for row in rows])
                return

            if path == "/api/vehicles":
                if not self.require_plan_feature(auth_user, "budgets"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT vehicles.*, customers.name AS customerName
                        FROM vehicles
                        LEFT JOIN customers ON customers.id = vehicles.customerId
                        WHERE vehicles.companyId = ?
                        ORDER BY vehicles.plate COLLATE NOCASE, vehicles.model COLLATE NOCASE
                        """,
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_vehicle(row) for row in rows])
                return

            if path == "/api/service-orders":
                if not self.require_plan_feature(auth_user, "budgets"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            service_orders.*,
                            customers.name AS customerName,
                            customers.phone AS customerPhone,
                            vehicles.brand AS vehicleBrand,
                            vehicles.model AS vehicleModel,
                            vehicles.plate AS vehiclePlate,
                            budgets.status AS budgetStatus
                        FROM service_orders
                        LEFT JOIN customers ON customers.id = service_orders.customerId
                        LEFT JOIN vehicles ON vehicles.id = service_orders.vehicleId
                        LEFT JOIN budgets ON budgets.id = service_orders.budgetId
                        WHERE service_orders.companyId = ?
                        ORDER BY datetime(service_orders.createdAt) DESC, service_orders.id DESC
                        """,
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_service_order(row) for row in rows])
                return

            if path == "/api/parts":
                if not self.require_plan_feature(auth_user, "inventory"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT * FROM parts_inventory
                        WHERE companyId = ?
                        ORDER BY datetime(createdAt) DESC, id DESC
                        """,
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_part(row) for row in rows])
                return

            if path == "/api/suppliers":
                if not self.require_plan_feature(auth_user, "inventory"):
                    return
                with connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT * FROM suppliers
                        WHERE companyId = ?
                        ORDER BY tradeName COLLATE NOCASE, corporateName COLLATE NOCASE
                        """,
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_supplier(row) for row in rows])
                return

            if path == "/api/payables":
                if not self.require_plan_feature(auth_user, "billing"):
                    return
                limit = int((query.get("limit") or ["0"])[0] or 0)
                sql = """
                    SELECT * FROM accounts_payable
                    WHERE companyId = ?
                    ORDER BY datetime(createdAt) DESC, id DESC
                """
                params = [company_id]
                if limit > 0:
                    sql += " LIMIT ?"
                    params.append(limit)
                with connect() as conn:
                    rows = conn.execute(sql, params).fetchall()
                self.send_json([row_to_payable(row) for row in rows])
                return

            if path.startswith("/api/settings/"):
                key = path.rsplit("/", 1)[-1]
                with connect() as conn:
                    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
                value = json.loads(row["value"]) if row else None
                self.send_json(value)
                return

            super().do_GET()
        except Exception as error:
            self.send_json({"error": str(error)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        payload = self.read_json()

        try:
            if parsed.path == "/api/auth/login":
                login = str(payload.get("login") or "").lower().strip()
                password = payload.get("password") or ""
                ip_address = self.client_address[0] if self.client_address else ""
                user_agent = self.headers.get("User-Agent", "")
                with connect() as conn:
                    if is_login_locked(conn, login):
                        record_login_attempt(conn, login, False, "locked", ip_address, user_agent)
                        self.send_json({"error": "Muitas tentativas inválidas. Aguarde alguns minutos antes de tentar novamente."}, 429)
                        return

                    row = conn.execute(
                        """
                        SELECT
                            users.*,
                            companies.name AS companyName,
                            subscriptions.plan AS subscriptionPlan,
                            subscriptions.status AS subscriptionStatus,
                            subscriptions.billingCycle,
                            subscriptions.currentPeriodStart,
                            subscriptions.currentPeriodEnd,
                            subscriptions.trialEndsAt
                        FROM users
                        LEFT JOIN companies ON companies.id = users.companyId
                        LEFT JOIN subscriptions ON subscriptions.id = (
                            SELECT id FROM subscriptions AS latest_subscriptions
                            WHERE latest_subscriptions.companyId = users.companyId
                            ORDER BY datetime(latest_subscriptions.createdAt) DESC, latest_subscriptions.id DESC
                            LIMIT 1
                        )
                        WHERE lower(users.email) = ? OR lower(users.username) = ?
                        """,
                        (login, login),
                    ).fetchone()

                if not row or not verify_password(password, row["passwordHash"]):
                    with connect() as conn:
                        record_login_attempt(conn, login, False, "invalid_credentials", ip_address, user_agent)
                    self.send_json({"error": "Usuário, e-mail ou senha inválidos."}, 401)
                    return

                if password_needs_rehash(row["passwordHash"]):
                    with connect() as conn:
                        conn.execute(
                            "UPDATE users SET passwordHash = ?, updatedAt = datetime('now') WHERE id = ?",
                            (hash_password(password), row["id"]),
                        )

                user = row_to_user(row)
                if user.get("blocked"):
                    with connect() as conn:
                        record_login_attempt(conn, login, False, "blocked_user", ip_address, user_agent)
                    self.send_json({"error": "Este usuário está bloqueado. Procure o administrador."}, 403)
                    return

                with connect() as conn:
                    record_login_attempt(conn, login, True, "success", ip_address, user_agent)
                self.send_json({"user": user, "token": create_session(row["id"])})
                return

            if parsed.path == "/api/auth/logout":
                token = self.auth_token()
                delete_session(token)
                self.send_json({"ok": True})
                return

            if parsed.path == "/api/billing/webhooks/mercadopago":
                valid, message = verify_mercadopago_signature(payload, query, self.headers)
                if not valid:
                    self.send_json({"error": message}, 401)
                    return

                with connect() as conn:
                    row, created = store_billing_webhook_event(conn, "mercadopago", payload, query, self.headers)
                    if created:
                        log_platform_audit(
                            conn,
                            None,
                            "billing.webhook.received",
                            "billing_webhook_event",
                            row["id"],
                            None,
                            {
                                "provider": row.get("provider"),
                                "eventId": row.get("eventId"),
                                "eventType": row.get("eventType"),
                                "action": row.get("action"),
                                "resourceId": row.get("resourceId"),
                                "requestId": row.get("requestId"),
                            },
                        )
                self.send_json(
                    {
                        "ok": True,
                        "received": True,
                        "duplicate": not created,
                        "eventId": row.get("eventId"),
                    },
                    202,
                )
                return

            auth_user = None
            if parsed.path.startswith("/api/"):
                auth_user = self.require_auth()
                if auth_user is None:
                    return
            company_id = auth_user["companyId"] if auth_user else None

            if parsed.path == "/api/subscription/checkout":
                if is_platform_admin(auth_user):
                    self.send_json({"error": "Painel master não contrata plano de cliente."}, 403)
                    return

                try:
                    with connect() as conn:
                        checkout, plan_info = create_billing_checkout_request(conn, auth_user, payload)
                        log_platform_audit(
                            conn,
                            auth_user,
                            "billing.checkout.requested",
                            "billing_checkout_request",
                            checkout["id"],
                            company_id,
                            {
                                "plan": checkout["plan"],
                                "billingCycle": checkout["billingCycle"],
                                "provider": checkout["provider"],
                                "status": checkout["status"],
                                "amount": checkout["amount"],
                            },
                        )
                except ValueError as exc:
                    self.send_json({"error": str(exc)}, 400)
                    return

                response = {
                    "checkout": checkout,
                    "plan": plan_info,
                    "message": "Solicitação de contratação registrada.",
                }
                if checkout.get("status") == "provider_error":
                    response["error"] = checkout.get("error") or "Falha ao criar checkout no provedor."
                    self.send_json(response, 502)
                    return
                self.send_json(response, 201)
                return

            if parsed.path == "/api/platform/subscriptions":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                data = normalize_subscription(payload)
                columns = ", ".join(SUBSCRIPTION_COLUMNS)
                marks = ", ".join(["?"] * len(SUBSCRIPTION_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO subscriptions ({columns}) VALUES ({marks})",
                        [data[column] for column in SUBSCRIPTION_COLUMNS],
                    )
                    log_platform_audit(
                        conn,
                        auth_user,
                        "subscription.create",
                        "subscription",
                        cursor.lastrowid,
                        data["companyId"],
                        {"plan": data["plan"], "status": data["status"], "billingCycle": data["billingCycle"]},
                    )
                    row = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_subscription(row), 201)
                return

            if parsed.path == "/api/platform/payments":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                data = normalize_payment(payload)
                columns = ", ".join(PAYMENT_COLUMNS)
                marks = ", ".join(["?"] * len(PAYMENT_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO payments ({columns}) VALUES ({marks})",
                        [data[column] for column in PAYMENT_COLUMNS],
                    )
                    log_platform_audit(
                        conn,
                        auth_user,
                        "payment.create",
                        "payment",
                        cursor.lastrowid,
                        data["companyId"],
                        {
                            "amount": data["amount"],
                            "status": data["status"],
                            "provider": data["provider"],
                            "paidAt": data["paidAt"],
                        },
                    )
                    row = conn.execute("SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_payment(row), 201)
                return

            if parsed.path == "/api/platform/companies":
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                company = normalize_company(payload)
                owner_email = str(payload.get("ownerEmail") or "").lower().strip()
                owner_username = str(payload.get("ownerUsername") or "").lower().strip() or None
                owner_password = str(payload.get("ownerPassword") or "")
                owner_name = str(payload.get("ownerName") or "").strip()
                owner_phone = str(payload.get("ownerPhone") or "").strip()
                plan = normalize_plan_code(payload.get("plan"))
                status = str(payload.get("status") or "trial").strip()
                billing_cycle = normalize_billing_cycle(payload.get("billingCycle"))
                now = time.strftime("%Y-%m-%d %H:%M:%S")

                if not company["name"]:
                    self.send_json({"error": "Informe o nome da oficina."}, 400)
                    return
                if not owner_name or not owner_email or len(owner_password) < 6:
                    self.send_json({"error": "Informe dono, e-mail e senha inicial com pelo menos 6 caracteres."}, 400)
                    return

                with connect() as conn:
                    existing_email = conn.execute(
                        "SELECT 1 FROM users WHERE lower(email) = ?",
                        (owner_email,),
                    ).fetchone()
                    if existing_email:
                        self.send_json({"error": "Já existe um usuário com este e-mail."}, 409)
                        return

                    if owner_username:
                        existing_username = conn.execute(
                            """
                            SELECT 1 FROM users
                            WHERE lower(username) = ?
                            """,
                            (owner_username,),
                        ).fetchone()
                        if existing_username:
                            self.send_json({"error": "Já existe um usuário com este nome de usuário."}, 409)
                            return

                    cursor = conn.execute(
                        """
                        INSERT INTO companies (name, document, phone, createdAt, updatedAt)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (company["name"], company["document"], company["phone"], now, now),
                    )
                    company_id = cursor.lastrowid
                    owner_hash = hash_password(owner_password)
                    user_cursor = conn.execute(
                        """
                        INSERT INTO users (
                            companyId, isPlatformAdmin, name, username, email, phone,
                            passwordHash, role, accessLevel, blocked, createdAt, updatedAt
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'admin', 'administrador', ?, ?, ?)
                        """,
                        (
                            company_id,
                            False,
                            owner_name,
                            owner_username,
                            owner_email,
                            owner_phone,
                            owner_hash,
                            False,
                            now,
                            now,
                        ),
                    )
                    owner_id = user_cursor.lastrowid
                    conn.execute(
                        "UPDATE companies SET ownerUserId = ? WHERE id = ?",
                        (owner_id, company_id),
                    )
                    sub_cursor = conn.execute(
                        """
                        INSERT INTO subscriptions (companyId, plan, status, billingCycle, createdAt, updatedAt)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (company_id, plan, status, billing_cycle, now, now),
                    )
                    log_platform_audit(
                        conn,
                        auth_user,
                        "company.create",
                        "company",
                        company_id,
                        company_id,
                        {
                            "companyName": company["name"],
                            "ownerUserId": owner_id,
                            "ownerEmail": owner_email,
                            "subscriptionId": sub_cursor.lastrowid,
                            "plan": plan,
                            "status": status,
                            "billingCycle": billing_cycle,
                        },
                    )
                    row = conn.execute(
                        """
                        SELECT
                            companies.id,
                            companies.name,
                            companies.document,
                            companies.phone,
                            companies.ownerUserId,
                            companies.createdAt,
                            companies.updatedAt,
                            subscriptions.plan,
                            subscriptions.status AS subscriptionStatus,
                            subscriptions.billingCycle,
                            NULL AS currentPeriodStart,
                            subscriptions.currentPeriodEnd,
                            subscriptions.trialEndsAt,
                            1 AS userCount,
                            0 AS budgetCount,
                            0 AS approvedBudgetCount,
                            NULL AS lastPaymentAt
                        FROM companies
                        JOIN subscriptions ON subscriptions.id = ?
                        WHERE companies.id = ?
                        """,
                        (sub_cursor.lastrowid, company_id),
                    ).fetchone()
                self.send_json(dict(row), 201)
                return

            if parsed.path == "/api/users":
                if not self.require_plan_feature(auth_user, "users", write=True):
                    return
                data = normalize_user(payload)
                data["companyId"] = company_id
                if not data.get("passwordHash"):
                    self.send_json({"error": "Informe uma senha para criar o usuário."}, 400)
                    return
                columns = ", ".join(USER_COLUMNS)
                marks = ", ".join(["?"] * len(USER_COLUMNS))
                with connect() as conn:
                    user_count = conn.execute(
                        "SELECT COUNT(*) AS total FROM users WHERE companyId = ?",
                        (company_id,),
                    ).fetchone()["total"]
                    max_users = int(user_plan(auth_user)["limits"].get("users") or 0)
                    if max_users and user_count >= max_users:
                        self.send_json({"error": f"Limite de {max_users} usuário(s) atingido para este plano."}, 403)
                        return
                    cursor = conn.execute(
                        f"INSERT INTO users ({columns}) VALUES ({marks})",
                        [data[column] for column in USER_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_user(row), 201)
                return

            if parsed.path == "/api/budgets":
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                data = normalize_budget(payload)
                data["companyId"] = company_id
                columns = ", ".join(BUDGET_COLUMNS)
                marks = ", ".join(["?"] * len(BUDGET_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO budgets ({columns}) VALUES ({marks})",
                        [data[column] for column in BUDGET_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM budgets WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_budget(row), 201)
                return

            if parsed.path == "/api/customers":
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                data = normalize_customer(payload)
                data["companyId"] = company_id
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                data["createdAt"] = data.get("createdAt") or now
                data["updatedAt"] = now
                if not data["name"]:
                    self.send_json({"error": "Informe o nome do cliente."}, 400)
                    return
                columns = ", ".join(CUSTOMER_COLUMNS)
                marks = ", ".join(["?"] * len(CUSTOMER_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO customers ({columns}) VALUES ({marks})",
                        [data[column] for column in CUSTOMER_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM customers WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_customer(row), 201)
                return

            if parsed.path == "/api/vehicles":
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                data = normalize_vehicle(payload)
                data["companyId"] = company_id
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                data["createdAt"] = data.get("createdAt") or now
                data["updatedAt"] = now
                if not data["customerId"] or not data["plate"]:
                    self.send_json({"error": "Informe cliente e placa do veículo."}, 400)
                    return
                columns = ", ".join(VEHICLE_COLUMNS)
                marks = ", ".join(["?"] * len(VEHICLE_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO vehicles ({columns}) VALUES ({marks})",
                        [data[column] for column in VEHICLE_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_vehicle(row), 201)
                return

            if parsed.path == "/api/service-orders/from-budget":
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                budget_id = int(payload.get("budgetId") or 0)
                with connect() as conn:
                    budget = conn.execute(
                        "SELECT * FROM budgets WHERE id = ? AND companyId = ?",
                        (budget_id, company_id),
                    ).fetchone()
                    if budget is None:
                        self.send_json({"error": "Orçamento não encontrado."}, 404)
                        return
                    if budget["status"] != "aprovado":
                        self.send_json({"error": "A OS só pode ser gerada a partir de orçamento aprovado."}, 400)
                        return
                    existing = conn.execute(
                        "SELECT * FROM service_orders WHERE budgetId = ? AND companyId = ?",
                        (budget_id, company_id),
                    ).fetchone()
                    if existing:
                        self.send_json(row_to_service_order(existing))
                        return

                    customer_id = upsert_customer_from_budget(conn, budget)
                    vehicle_id = upsert_vehicle_from_budget(conn, budget, customer_id)
                    now = time.strftime("%Y-%m-%d %H:%M:%S")
                    data = normalize_service_order({
                        "companyId": company_id,
                        "budgetId": budget_id,
                        "customerId": customer_id,
                        "vehicleId": vehicle_id,
                        "number": next_service_order_number(conn, company_id),
                        "status": "aberta",
                        "priority": payload.get("priority") or "normal",
                        "entryDate": payload.get("entryDate") or now[:10],
                        "expectedDeliveryDate": payload.get("expectedDeliveryDate") or "",
                        "problemDescription": budget["notes"] or "",
                        "serviceDescription": budget["description"] or "",
                        "internalNotes": "",
                        "parts": json.loads(budget["parts"] or "[]"),
                        "labor": json.loads(budget["labor"] or "[]"),
                        "totalAmount": budget_total_value(budget),
                        "createdAt": now,
                        "updatedAt": now,
                    })
                    columns = ", ".join(SERVICE_ORDER_COLUMNS)
                    marks = ", ".join(["?"] * len(SERVICE_ORDER_COLUMNS))
                    cursor = conn.execute(
                        f"INSERT INTO service_orders ({columns}) VALUES ({marks})",
                        [data[column] for column in SERVICE_ORDER_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM service_orders WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_service_order(row), 201)
                return

            if parsed.path == "/api/service-orders":
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                data = normalize_service_order(payload)
                data["companyId"] = company_id
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                data["number"] = data["number"] or ""
                data["createdAt"] = data.get("createdAt") or now
                data["updatedAt"] = now
                with connect() as conn:
                    if not data["number"]:
                        data["number"] = next_service_order_number(conn, company_id)
                    columns = ", ".join(SERVICE_ORDER_COLUMNS)
                    marks = ", ".join(["?"] * len(SERVICE_ORDER_COLUMNS))
                    cursor = conn.execute(
                        f"INSERT INTO service_orders ({columns}) VALUES ({marks})",
                        [data[column] for column in SERVICE_ORDER_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM service_orders WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_service_order(row), 201)
                return

            if parsed.path == "/api/parts":
                if not self.require_plan_feature(auth_user, "inventory", write=True):
                    return
                with connect() as conn:
                    data = normalize_part(payload, next_part_code(conn))
                    data["companyId"] = company_id
                    columns = ", ".join(PART_COLUMNS)
                    marks = ", ".join(["?"] * len(PART_COLUMNS))
                    cursor = conn.execute(
                        f"INSERT INTO parts_inventory ({columns}) VALUES ({marks})",
                        [data[column] for column in PART_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM parts_inventory WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_part(row), 201)
                return

            if parsed.path == "/api/suppliers":
                if not self.require_plan_feature(auth_user, "inventory", write=True):
                    return
                data = normalize_supplier(payload)
                data["companyId"] = company_id
                columns = ", ".join(SUPPLIER_COLUMNS)
                marks = ", ".join(["?"] * len(SUPPLIER_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO suppliers ({columns}) VALUES ({marks})",
                        [data[column] for column in SUPPLIER_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_supplier(row), 201)
                return

            if parsed.path == "/api/payables":
                if not self.require_plan_feature(auth_user, "billing", write=True):
                    return
                data = normalize_payable(payload)
                data["companyId"] = company_id
                columns = ", ".join(PAYABLE_COLUMNS)
                marks = ", ".join(["?"] * len(PAYABLE_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO accounts_payable ({columns}) VALUES ({marks})",
                        [data[column] for column in PAYABLE_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM accounts_payable WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_payable(row), 201)
                return

            self.send_json({"error": "Rota não encontrada."}, 404)
        except Exception as error:
            if is_integrity_error(error):
                self.send_json({"error": str(error)}, 409)
                return
            self.send_json({"error": str(error)}, 500)

    def do_PUT(self):
        parsed = urlparse(self.path)
        payload = self.read_json()

        try:
            auth_user = None
            if parsed.path.startswith("/api/"):
                auth_user = self.require_auth()
                if auth_user is None:
                    return
            company_id = auth_user["companyId"] if auth_user else None

            if parsed.path.startswith("/api/platform/subscriptions/"):
                if not is_platform_admin(auth_user):
                    self.send_json({"error": "Acesso restrito ao painel master."}, 403)
                    return

                subscription_id = int(parsed.path.rsplit("/", 1)[-1])
                current = None
                with connect() as conn:
                    current = conn.execute(
                        "SELECT * FROM subscriptions WHERE id = ?",
                        (subscription_id,),
                    ).fetchone()
                if current is None:
                    self.send_json({"error": "Assinatura não encontrada."}, 404)
                    return

                data = normalize_subscription({**dict(current), **payload})
                data["companyId"] = current["companyId"]
                assignments = ", ".join([f"{column} = ?" for column in SUBSCRIPTION_COLUMNS])
                with connect() as conn:
                    conn.execute(
                        f"UPDATE subscriptions SET {assignments} WHERE id = ?",
                        [data[column] for column in SUBSCRIPTION_COLUMNS] + [subscription_id],
                    )
                    log_platform_audit(
                        conn,
                        auth_user,
                        "subscription.update",
                        "subscription",
                        subscription_id,
                        data["companyId"],
                        {
                            "before": {
                                "plan": current["plan"],
                                "status": current["status"],
                                "billingCycle": current["billingCycle"],
                                "currentPeriodStart": current["currentPeriodStart"],
                                "currentPeriodEnd": current["currentPeriodEnd"],
                                "trialEndsAt": current["trialEndsAt"],
                            },
                            "after": {
                                "plan": data["plan"],
                                "status": data["status"],
                                "billingCycle": data["billingCycle"],
                                "currentPeriodStart": data["currentPeriodStart"],
                                "currentPeriodEnd": data["currentPeriodEnd"],
                                "trialEndsAt": data["trialEndsAt"],
                            },
                        },
                    )
                    row = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,)).fetchone()
                self.send_json(row_to_subscription(row))
                return

            if parsed.path.startswith("/api/users/"):
                if not self.require_plan_feature(auth_user, "users", write=True):
                    return
                user_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    current = conn.execute(
                        "SELECT * FROM users WHERE id = ? AND companyId = ?",
                        (user_id, company_id),
                    ).fetchone()
                if current is None:
                    self.send_json({"error": "Usuário não encontrado."}, 404)
                    return

                data = normalize_user(payload, current)
                data["companyId"] = company_id
                assignments = ", ".join([f"{column} = ?" for column in USER_COLUMNS])
                with connect() as conn:
                    conn.execute(
                        f"UPDATE users SET {assignments} WHERE id = ? AND companyId = ?",
                        [data[column] for column in USER_COLUMNS] + [user_id, company_id],
                    )
                    row = conn.execute(
                        "SELECT * FROM users WHERE id = ? AND companyId = ?",
                        (user_id, company_id),
                    ).fetchone()
                self.send_json(row_to_user(row))
                return

            if parsed.path.startswith("/api/budgets/"):
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                budget_id = int(parsed.path.rsplit("/", 1)[-1])
                data = normalize_budget(payload)
                data["companyId"] = company_id
                assignments = ", ".join([f"{column} = ?" for column in BUDGET_COLUMNS])
                with connect() as conn:
                    conn.execute(
                        f"UPDATE budgets SET {assignments} WHERE id = ? AND companyId = ?",
                        [data[column] for column in BUDGET_COLUMNS] + [budget_id, company_id],
                    )
                    row = conn.execute(
                        "SELECT * FROM budgets WHERE id = ? AND companyId = ?",
                        (budget_id, company_id),
                    ).fetchone()
                self.send_json(row_to_budget(row))
                return

            if parsed.path.startswith("/api/customers/"):
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                customer_id = int(parsed.path.rsplit("/", 1)[-1])
                data = normalize_customer(payload)
                data["companyId"] = company_id
                data["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with connect() as conn:
                    current = conn.execute(
                        "SELECT * FROM customers WHERE id = ? AND companyId = ?",
                        (customer_id, company_id),
                    ).fetchone()
                    if current is None:
                        self.send_json({"error": "Cliente não encontrado."}, 404)
                        return
                    data["createdAt"] = current["createdAt"]
                    assignments = ", ".join([f"{column} = ?" for column in CUSTOMER_COLUMNS])
                    conn.execute(
                        f"UPDATE customers SET {assignments} WHERE id = ? AND companyId = ?",
                        [data[column] for column in CUSTOMER_COLUMNS] + [customer_id, company_id],
                    )
                    row = conn.execute(
                        "SELECT * FROM customers WHERE id = ? AND companyId = ?",
                        (customer_id, company_id),
                    ).fetchone()
                self.send_json(row_to_customer(row))
                return

            if parsed.path.startswith("/api/vehicles/"):
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                vehicle_id = int(parsed.path.rsplit("/", 1)[-1])
                data = normalize_vehicle(payload)
                data["companyId"] = company_id
                data["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with connect() as conn:
                    current = conn.execute(
                        "SELECT * FROM vehicles WHERE id = ? AND companyId = ?",
                        (vehicle_id, company_id),
                    ).fetchone()
                    if current is None:
                        self.send_json({"error": "Veículo não encontrado."}, 404)
                        return
                    data["createdAt"] = current["createdAt"]
                    assignments = ", ".join([f"{column} = ?" for column in VEHICLE_COLUMNS])
                    conn.execute(
                        f"UPDATE vehicles SET {assignments} WHERE id = ? AND companyId = ?",
                        [data[column] for column in VEHICLE_COLUMNS] + [vehicle_id, company_id],
                    )
                    row = conn.execute(
                        "SELECT * FROM vehicles WHERE id = ? AND companyId = ?",
                        (vehicle_id, company_id),
                    ).fetchone()
                self.send_json(row_to_vehicle(row))
                return

            if parsed.path.startswith("/api/service-orders/"):
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                service_order_id = int(parsed.path.rsplit("/", 1)[-1])
                data = normalize_service_order(payload)
                data["companyId"] = company_id
                data["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                if data["status"] in ("concluida", "entregue") and not data.get("completedAt"):
                    data["completedAt"] = data["updatedAt"]
                with connect() as conn:
                    current = conn.execute(
                        "SELECT * FROM service_orders WHERE id = ? AND companyId = ?",
                        (service_order_id, company_id),
                    ).fetchone()
                    if current is None:
                        self.send_json({"error": "Ordem de serviço não encontrada."}, 404)
                        return
                    data["createdAt"] = current["createdAt"]
                    data["number"] = current["number"]
                    assignments = ", ".join([f"{column} = ?" for column in SERVICE_ORDER_COLUMNS])
                    conn.execute(
                        f"UPDATE service_orders SET {assignments} WHERE id = ? AND companyId = ?",
                        [data[column] for column in SERVICE_ORDER_COLUMNS] + [service_order_id, company_id],
                    )
                    row = conn.execute(
                        "SELECT * FROM service_orders WHERE id = ? AND companyId = ?",
                        (service_order_id, company_id),
                    ).fetchone()
                self.send_json(row_to_service_order(row))
                return

            if parsed.path.startswith("/api/parts/"):
                if not self.require_plan_feature(auth_user, "inventory", write=True):
                    return
                part_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    current = conn.execute(
                        "SELECT code FROM parts_inventory WHERE id = ? AND companyId = ?",
                        (part_id, company_id),
                    ).fetchone()
                    data = normalize_part(payload, current["code"] if current else None)
                    data["companyId"] = company_id
                    assignments = ", ".join([f"{column} = ?" for column in PART_COLUMNS])
                    conn.execute(
                        f"UPDATE parts_inventory SET {assignments} WHERE id = ? AND companyId = ?",
                        [data[column] for column in PART_COLUMNS] + [part_id, company_id],
                    )
                    row = conn.execute(
                        "SELECT * FROM parts_inventory WHERE id = ? AND companyId = ?",
                        (part_id, company_id),
                    ).fetchone()
                self.send_json(row_to_part(row))
                return

            if parsed.path.startswith("/api/settings/"):
                if not self.require_plan_feature(auth_user, "users", write=True):
                    return
                key = parsed.path.rsplit("/", 1)[-1]
                with connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO app_settings (key, value)
                        VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (key, json.dumps(payload, ensure_ascii=False)),
                    )
                self.send_json(payload)
                return

            self.send_json({"error": "Rota não encontrada."}, 404)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)

        try:
            auth_user = None
            if parsed.path.startswith("/api/"):
                auth_user = self.require_auth()
                if auth_user is None:
                    return
            company_id = auth_user["companyId"] if auth_user else None

            if parsed.path.startswith("/api/users/"):
                if not self.require_plan_feature(auth_user, "users", write=True):
                    return
                user_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute(
                        "DELETE FROM users WHERE id = ? AND companyId = ?",
                        (user_id, company_id),
                    )
                self.send_json({"ok": True})
                return

            if parsed.path.startswith("/api/budgets/"):
                if not self.require_plan_feature(auth_user, "budgets", write=True):
                    return
                budget_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute(
                        "DELETE FROM budgets WHERE id = ? AND companyId = ?",
                        (budget_id, company_id),
                    )
                self.send_json({"ok": True})
                return

            if parsed.path.startswith("/api/parts/"):
                if not self.require_plan_feature(auth_user, "inventory", write=True):
                    return
                part_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute(
                        "DELETE FROM parts_inventory WHERE id = ? AND companyId = ?",
                        (part_id, company_id),
                    )
                self.send_json({"ok": True})
                return

            self.send_json({"error": "Rota não encontrada."}, 404)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)


if __name__ == "__main__":
    validate_runtime_config()
    init_db()
    prune_expired_sessions()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Ambiente: {APP_ENV}")
    print(f"Sistema rodando em http://{HOST}:{PORT}/")
    print(f"Banco SQLite: {DB_PATH}")
    server.serve_forever()
