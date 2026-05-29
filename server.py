from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import json
import sqlite3


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "oficina.db"
HOST = "127.0.0.1"
PORT = 4173


USER_COLUMNS = [
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


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        master_hash = hashlib.sha256("Master@123".encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO users (name, email, passwordHash, role, accessLevel, blocked, createdAt)
            SELECT 'MASTER', 'master@oficina.local', ?, 'admin', 'administrador', 0, datetime('now')
            WHERE NOT EXISTS (
                SELECT 1 FROM users WHERE lower(email) = 'master@oficina.local'
            )
            """,
            (master_hash,),
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
    item["blocked"] = bool(item.get("blocked"))
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


def normalize_user(payload):
    data = {key: payload.get(key) for key in USER_COLUMNS}
    data["email"] = str(data.get("email") or "").lower().strip()
    data["blocked"] = 1 if data.get("blocked") else 0
    return data


def normalize_budget(payload):
    data = {key: payload.get(key) for key in BUDGET_COLUMNS}
    data["userId"] = int(data.get("userId") or 0)
    data["parts"] = json.dumps(data.get("parts") or [], ensure_ascii=False)
    data["labor"] = json.dumps(data.get("labor") or [], ensure_ascii=False)
    data["laborValue"] = float(data.get("laborValue") or 0)
    data["partsValue"] = float(data.get("partsValue") or 0)
    return data


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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/api/health":
                self.send_json({"ok": True, "database": str(DB_PATH)})
                return

            if path == "/api/users":
                with connect() as conn:
                    rows = conn.execute("SELECT * FROM users ORDER BY name COLLATE NOCASE").fetchall()
                self.send_json([row_to_user(row) for row in rows])
                return

            if path == "/api/users/by-email":
                email = (query.get("email") or [""])[0].lower().strip()
                with connect() as conn:
                    row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
                self.send_json(row_to_user(row))
                return

            if path == "/api/budgets":
                with connect() as conn:
                    rows = conn.execute("SELECT * FROM budgets ORDER BY datetime(createdAt) DESC").fetchall()
                self.send_json([row_to_budget(row) for row in rows])
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
            if parsed.path == "/api/users":
                data = normalize_user(payload)
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

            self.send_json({"error": "Rota não encontrada."}, 404)
        except sqlite3.IntegrityError as error:
            self.send_json({"error": str(error)}, 409)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)

    def do_PUT(self):
        parsed = urlparse(self.path)
        payload = self.read_json()

        try:
            if parsed.path.startswith("/api/users/"):
                user_id = int(parsed.path.rsplit("/", 1)[-1])
                data = normalize_user(payload)
                assignments = ", ".join([f"{column} = ?" for column in USER_COLUMNS])
                with connect() as conn:
                    conn.execute(
                        f"UPDATE users SET {assignments} WHERE id = ?",
                        [data[column] for column in USER_COLUMNS] + [user_id],
                    )
                    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                self.send_json(row_to_user(row))
                return

            if parsed.path.startswith("/api/budgets/"):
                budget_id = int(parsed.path.rsplit("/", 1)[-1])
                data = normalize_budget(payload)
                assignments = ", ".join([f"{column} = ?" for column in BUDGET_COLUMNS])
                with connect() as conn:
                    conn.execute(
                        f"UPDATE budgets SET {assignments} WHERE id = ?",
                        [data[column] for column in BUDGET_COLUMNS] + [budget_id],
                    )
                    row = conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
                self.send_json(row_to_budget(row))
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
            if parsed.path.startswith("/api/users/"):
                user_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                self.send_json({"ok": True})
                return

            if parsed.path.startswith("/api/budgets/"):
                budget_id = int(parsed.path.rsplit("/", 1)[-1])
                with connect() as conn:
                    conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
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
