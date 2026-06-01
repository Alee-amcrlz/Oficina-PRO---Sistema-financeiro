from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import hmac
import json
import secrets
import sqlite3
import time


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "oficina.db"
HOST = "127.0.0.1"
PORT = 4173
SESSION_TTL_SECONDS = 8 * 60 * 60
SESSIONS = {}


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


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def ensure_column(conn, table, column, definition):
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def hash_password(password):
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


def verify_password(password, stored_hash):
    return hmac.compare_digest(hash_password(password), str(stored_hash or ""))


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "userId": int(user_id),
        "expiresAt": time.time() + SESSION_TTL_SECONDS,
    }
    return token


def get_session_user(token):
    session = SESSIONS.get(token)
    if not session:
        return None

    if session["expiresAt"] < time.time():
        SESSIONS.pop(token, None)
        return None

    with connect() as conn:
        row = conn.execute(
            """
            SELECT users.*, companies.name AS companyName
            FROM users
            LEFT JOIN companies ON companies.id = users.companyId
            WHERE users.id = ?
            """,
            (session["userId"],),
        ).fetchone()

    user = row_to_user(row)
    if not user or user.get("blocked"):
        SESSIONS.pop(token, None)
        return None

    session["expiresAt"] = time.time() + SESSION_TTL_SECONDS
    return user


def is_platform_admin(user):
    return bool(user and user.get("isPlatformAdmin"))


def init_db():
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

            CREATE INDEX IF NOT EXISTS idx_accounts_payable_created ON accounts_payable(createdAt);
            CREATE INDEX IF NOT EXISTS idx_accounts_payable_due ON accounts_payable(competenceDate);
            CREATE INDEX IF NOT EXISTS idx_accounts_payable_supplier ON accounts_payable(supplierName COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_company ON subscriptions(companyId);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
            CREATE INDEX IF NOT EXISTS idx_payments_company ON payments(companyId);
            CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
            """
        )
        ensure_column(conn, "users", "companyId", "INTEGER")
        ensure_column(conn, "users", "isPlatformAdmin", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "budgets", "companyId", "INTEGER")
        ensure_column(conn, "parts_inventory", "companyId", "INTEGER")
        ensure_column(conn, "suppliers", "companyId", "INTEGER")
        ensure_column(conn, "accounts_payable", "companyId", "INTEGER")
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_users_company ON users(companyId);
            CREATE INDEX IF NOT EXISTS idx_budgets_company ON budgets(companyId);
            CREATE INDEX IF NOT EXISTS idx_parts_inventory_company ON parts_inventory(companyId);
            CREATE INDEX IF NOT EXISTS idx_suppliers_company ON suppliers(companyId);
            CREATE INDEX IF NOT EXISTS idx_accounts_payable_company ON accounts_payable(companyId);
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

        master_hash = hash_password("Master@123")
        conn.execute(
            """
            INSERT INTO users (companyId, isPlatformAdmin, name, username, email, passwordHash, role, accessLevel, blocked, createdAt)
            SELECT ?, 1, 'MASTER', 'master', 'master@oficina.local', ?, 'admin', 'administrador', 0, datetime('now')
            WHERE NOT EXISTS (
                SELECT 1 FROM users WHERE lower(email) = 'master@oficina.local'
            )
            """,
            (default_company_id, master_hash),
        )
        conn.execute(
            """
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), 'master'),
                companyId = COALESCE(companyId, ?),
                isPlatformAdmin = 1
            WHERE lower(email) = 'master@oficina.local'
            """,
            (default_company_id,),
        )
        conn.execute(
            """
            UPDATE companies
            SET ownerUserId = COALESCE(
                ownerUserId,
                (SELECT id FROM users WHERE lower(email) = 'master@oficina.local' LIMIT 1)
            )
            WHERE id = ?
            """,
            (default_company_id,),
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
    return item


def row_to_budget(row):
    if row is None:
        return None
    item = dict(row)
    for key in ("parts", "labor"):
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except json.JSONDecodeError:
            item[key] = []
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
    data["blocked"] = 1 if data.get("blocked") else 0
    data["isPlatformAdmin"] = 1 if data.get("isPlatformAdmin") else 0
    return data


def normalize_budget(payload):
    data = {key: payload.get(key) for key in BUDGET_COLUMNS}
    data["userId"] = int(data.get("userId") or 0)
    data["parts"] = json.dumps(data.get("parts") or [], ensure_ascii=False)
    data["labor"] = json.dumps(data.get("labor") or [], ensure_ascii=False)
    data["laborValue"] = float(data.get("laborValue") or 0)
    data["partsValue"] = float(data.get("partsValue") or 0)
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
    data["plan"] = str(data.get("plan") or "trial").strip()
    data["status"] = str(data.get("status") or "trial").strip()
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


def next_part_code(conn):
    row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'parts_inventory'").fetchone()
    next_id = int(row["seq"] or 0) + 1 if row else 1
    return f"PEC-{next_id:05d}"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                self.send_json({"ok": True, "database": str(DB_PATH)})
                return

            auth_user = None
            if path.startswith("/api/"):
                auth_user = self.require_auth()
                if auth_user is None:
                    return
            company_id = auth_user["companyId"] if auth_user else None

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
                            subscriptions.plan,
                            subscriptions.status AS subscriptionStatus,
                            subscriptions.currentPeriodEnd,
                            subscriptions.trialEndsAt,
                            COUNT(DISTINCT users.id) AS userCount,
                            COUNT(DISTINCT budgets.id) AS budgetCount,
                            COUNT(DISTINCT CASE WHEN budgets.status = 'aprovado' THEN budgets.id END) AS approvedBudgetCount,
                            MAX(payments.paidAt) AS lastPaymentAt
                        FROM companies
                        LEFT JOIN subscriptions ON subscriptions.companyId = companies.id
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

            if path == "/api/users":
                with connect() as conn:
                    rows = conn.execute(
                        "SELECT * FROM users WHERE companyId = ? ORDER BY name COLLATE NOCASE",
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_user(row) for row in rows])
                return

            if path == "/api/users/by-email":
                email = (query.get("email") or [""])[0].lower().strip()
                with connect() as conn:
                    row = conn.execute(
                        "SELECT * FROM users WHERE companyId = ? AND lower(email) = ?",
                        (company_id, email),
                    ).fetchone()
                self.send_json(row_to_user(row))
                return

            if path == "/api/users/by-login":
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
                with connect() as conn:
                    rows = conn.execute(
                        "SELECT * FROM budgets WHERE companyId = ? ORDER BY datetime(createdAt) DESC",
                        (company_id,),
                    ).fetchall()
                self.send_json([row_to_budget(row) for row in rows])
                return

            if path == "/api/parts":
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
        payload = self.read_json()

        try:
            if parsed.path == "/api/auth/login":
                login = str(payload.get("login") or "").lower().strip()
                password = payload.get("password") or ""
                with connect() as conn:
                    row = conn.execute(
                        """
                        SELECT users.*, companies.name AS companyName
                        FROM users
                        LEFT JOIN companies ON companies.id = users.companyId
                        WHERE lower(users.email) = ? OR lower(users.username) = ?
                        """,
                        (login, login),
                    ).fetchone()

                if not row or not verify_password(password, row["passwordHash"]):
                    self.send_json({"error": "Usuário, e-mail ou senha inválidos."}, 401)
                    return

                user = row_to_user(row)
                if user.get("blocked"):
                    self.send_json({"error": "Este usuário está bloqueado. Procure o administrador."}, 403)
                    return

                self.send_json({"user": user, "token": create_session(row["id"])})
                return

            if parsed.path == "/api/auth/logout":
                token = self.auth_token()
                if token:
                    SESSIONS.pop(token, None)
                self.send_json({"ok": True})
                return

            auth_user = None
            if parsed.path.startswith("/api/"):
                auth_user = self.require_auth()
                if auth_user is None:
                    return
            company_id = auth_user["companyId"] if auth_user else None

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
                    row = conn.execute("SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_payment(row), 201)
                return

            if parsed.path == "/api/users":
                data = normalize_user(payload)
                data["companyId"] = company_id
                if not data.get("passwordHash"):
                    self.send_json({"error": "Informe uma senha para criar o usuário."}, 400)
                    return
                columns = ", ".join(USER_COLUMNS)
                marks = ", ".join(["?"] * len(USER_COLUMNS))
                with connect() as conn:
                    cursor = conn.execute(
                        f"INSERT INTO users ({columns}) VALUES ({marks})",
                        [data[column] for column in USER_COLUMNS],
                    )
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
                self.send_json(row_to_user(row), 201)
                return

            if parsed.path == "/api/budgets":
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

            if parsed.path == "/api/parts":
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
        except sqlite3.IntegrityError as error:
            self.send_json({"error": str(error)}, 409)
        except Exception as error:
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
                    row = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,)).fetchone()
                self.send_json(row_to_subscription(row))
                return

            if parsed.path.startswith("/api/users/"):
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

            if parsed.path.startswith("/api/parts/"):
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
                user_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute(
                        "DELETE FROM users WHERE id = ? AND companyId = ?",
                        (user_id, company_id),
                    )
                self.send_json({"ok": True})
                return

            if parsed.path.startswith("/api/budgets/"):
                budget_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute(
                        "DELETE FROM budgets WHERE id = ? AND companyId = ?",
                        (budget_id, company_id),
                    )
                self.send_json({"ok": True})
                return

            if parsed.path.startswith("/api/parts/"):
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
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Sistema rodando em http://{HOST}:{PORT}/")
    print(f"Banco SQLite: {DB_PATH}")
    server.serve_forever()
