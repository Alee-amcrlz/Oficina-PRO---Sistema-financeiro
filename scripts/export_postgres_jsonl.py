from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import json
import os
import sys

from data_tables import POSTGRES_LOGICAL_EXPORT_TABLES


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports"
TABLES = POSTGRES_LOGICAL_EXPORT_TABLES

CAMEL_CASE_COLUMNS = {
    "companyid": "companyId",
    "isplatformadmin": "isPlatformAdmin",
    "owneruserid": "ownerUserId",
    "userid": "userId",
    "customerid": "customerId",
    "vehicleid": "vehicleId",
    "budgetid": "budgetId",
    "subscriptionid": "subscriptionId",
    "providerpaymentid": "providerPaymentId",
    "providercheckoutid": "providerCheckoutId",
    "sandboxinitpoint": "sandboxInitPoint",
    "requestpayload": "requestPayload",
    "responsepayload": "responsePayload",
    "eventid": "eventId",
    "eventtype": "eventType",
    "resourceid": "resourceId",
    "requestid": "requestId",
    "signaturets": "signatureTs",
    "receivedat": "receivedAt",
    "processedat": "processedAt",
    "actoruserid": "actorUserId",
    "actoremail": "actorEmail",
    "targettype": "targetType",
    "targetid": "targetId",
    "targetcompanyid": "targetCompanyId",
    "passwordhash": "passwordHash",
    "accesslevel": "accessLevel",
    "tokenhash": "tokenHash",
    "expiresat": "expiresAt",
    "lastseenat": "lastSeenAt",
    "ipaddress": "ipAddress",
    "useragent": "userAgent",
    "createdat": "createdAt",
    "updatedat": "updatedAt",
    "appliedat": "appliedAt",
    "clientname": "clientName",
    "clientemail": "clientEmail",
    "clientphone": "clientPhone",
    "clientzip": "clientZip",
    "clientstreet": "clientStreet",
    "clientnumber": "clientNumber",
    "clientaddress": "clientAddress",
    "clientdistrict": "clientDistrict",
    "clientstate": "clientState",
    "vehiclebrand": "vehicleBrand",
    "vehiclemodel": "vehicleModel",
    "vehicleyear": "vehicleYear",
    "vehiclecolor": "vehicleColor",
    "vehiclekm": "vehicleKm",
    "laborvalue": "laborValue",
    "partsvalue": "partsValue",
    "approvedat": "approvedAt",
    "entrydate": "entryDate",
    "expecteddeliverydate": "expectedDeliveryDate",
    "completedat": "completedAt",
    "problemdescription": "problemDescription",
    "servicedescription": "serviceDescription",
    "internalnotes": "internalNotes",
    "totalamount": "totalAmount",
    "competencedate": "competenceDate",
    "invoicenumber": "invoiceNumber",
    "supplierid": "supplierId",
    "suppliercnpj": "supplierCnpj",
    "suppliername": "supplierName",
    "costprice": "costPrice",
    "saleprice": "salePrice",
    "stockquantity": "stockQuantity",
    "serialnumber": "serialNumber",
    "corporatename": "corporateName",
    "tradename": "tradeName",
    "sellername": "sellerName",
    "billingcycle": "billingCycle",
    "providercustomerid": "providerCustomerId",
    "providersubscriptionid": "providerSubscriptionId",
    "currentperiodstart": "currentPeriodStart",
    "currentperiodend": "currentPeriodEnd",
    "trialendsat": "trialEndsAt",
    "paidat": "paidAt",
}


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_psycopg():
    try:
        import psycopg  # type: ignore
    except ImportError:
        print('[ERRO] DATABASE_URL exige psycopg: python -m pip install "psycopg[binary]"')
        return None
    return psycopg


def pg_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def table_columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [row[0] for row in cur.fetchall()]


def row_dict(columns, row):
    return {
        CAMEL_CASE_COLUMNS.get(column.lower(), column): value
        for column, value in zip(columns, row)
    }


def export_table(cur, table, target_dir):
    columns = table_columns(cur, table)
    if not columns:
        return {"exists": False, "rows": 0}

    order_column = "id" if "id" in columns else ("version" if "version" in columns else columns[0])
    sql = f"SELECT * FROM {pg_identifier(table)} ORDER BY {pg_identifier(order_column)}"
    cur.execute(sql)

    path = target_dir / f"{table}.jsonl"
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in cur:
            handle.write(
                json.dumps(row_dict(columns, row), ensure_ascii=False, sort_keys=True, default=json_default) + "\n"
            )
            count += 1
    return {"exists": True, "rows": count, "file": path.name}


def main():
    load_env_file(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERRO] DATABASE_URL não configurado.")
        return 1

    psycopg = require_psycopg()
    if psycopg is None:
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = EXPORT_DIR / f"postgres-export-{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": "postgresql",
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "tables": {},
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for table in TABLES:
                manifest["tables"][table] = export_table(cur, table, target_dir)

    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )
    print(target_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
