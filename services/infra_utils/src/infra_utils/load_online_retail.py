"""
Online Retail II loader (Phase 1A)

What it does (deterministic + idempotent):
- Loads .env (so it always targets the intended Docker Postgres)
- Downloads the UCI Online Retail II Excel if missing
- Reads both sheets, normalizes columns/types, drops unusable rows
- Loads into Postgres (TRUNCATE + COPY for speed)
- Updates retail.data_catalog with snapshot_id + last_ingested_at
- Prints truth signals (DF rows, DB target, rowcount post-load)

Run from repo root:
  uv run --project services/infra_utils python -m infra_utils.load_online_retail

Or (script path, also from root):
  uv run --project services/infra_utils python services/infra_utils/src/infra_utils/load_online_retail.py
"""


from __future__ import annotations

import os
import io
import csv
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests
import pandas as pd
import psycopg
from dotenv import load_dotenv

from pathlib import Path
# Path("logs/audit/_loader_heartbeat.txt").parent.mkdir(parents=True, exist_ok=True)
# Path("logs/audit/_loader_heartbeat.txt").write_text("loader executed\n")
# raise SystemExit("loader executed (heartbeat written)")

# ------------------------
# ENV + CONFIG
# ------------------------

load_dotenv()  # ensures POSTGRES_* are available when running via uv

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# UCI provides the dataset as an Excel file; this URL generally works.
DATA_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.xlsx"
DATA_FILE = DATA_DIR / "online_retail_ii.xlsx"

DB_SCHEMA = "retail"
TABLE_NAME = "online_retail"
CATALOG_TABLE = "data_catalog"
DATASET_NAME = "online_retail"


def _required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}. Check your .env at repo root.")
    return v


POSTGRES_USER = _required_env("POSTGRES_USER")
POSTGRES_PASSWORD = _required_env("POSTGRES_PASSWORD")
POSTGRES_DB = _required_env("POSTGRES_DB")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{POSTGRES_PORT}/{POSTGRES_DB}"


# ------------------------
# DOWNLOAD
# ------------------------

DATA_URLS = [
    # Try a couple of UCI variants (they do change paths)
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx",
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx?download=1",
]

DATA_FILE = DATA_DIR / "online_retail_ii.xlsx"

def download_dataset() -> None:
    if DATA_FILE.exists():
        print(f"[download] found existing: {DATA_FILE}")
        return

    last_err = None
    for url in DATA_URLS:
        try:
            print(f"[download] trying: {url}")
            resp = requests.get(url, timeout=180)
            if resp.status_code == 200 and len(resp.content) > 1_000_000:
                DATA_FILE.write_bytes(resp.content)
                print(f"[download] saved to: {DATA_FILE} ({DATA_FILE.stat().st_size} bytes)")
                return
            else:
                last_err = f"status={resp.status_code}, bytes={len(resp.content)}"
        except Exception as e:
            last_err = repr(e)

    raise RuntimeError(
        "[download] failed to download Online Retail II.\n"
        f"Last error: {last_err}\n\n"
        "Fallback options:\n"
        "1) Manually download the Excel and save as: data/raw/online_retail_ii.xlsx\n"
        "2) (Optional) Use Kaggle API and we’ll wire it in."
    )


# ------------------------
# LOAD + NORMALIZE
# ------------------------

def load_dataframe() -> pd.DataFrame:
    print("[load] reading excel sheets...")
    # Exact sheet names in Online Retail II (UCI)
    df_2009_2010 = pd.read_excel(DATA_FILE, sheet_name="Year 2009-2010", engine="openpyxl")
    df_2010_2011 = pd.read_excel(DATA_FILE, sheet_name="Year 2010-2011", engine="openpyxl")

    df = pd.concat([df_2009_2010, df_2010_2011], ignore_index=True)

    # Normalize column names
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )

    # Canonicalize to our DB column names
    
    rename_map = {
            # invoice number variants
            "invoiceno": "invoice_no",
            "invoice_no": "invoice_no",
            "invoice": "invoice_no",

            # stock code variants
            "stockcode": "stock_code",
            "stock_code": "stock_code",

            # description variants
            "description": "description",

            # quantity variants
            "quantity": "quantity",

            # invoice date variants
            "invoicedate": "invoice_date",
            "invoice_date": "invoice_date",

            # unit price variants
            "unitprice": "unit_price",
            "unit_price": "unit_price",
            "price": "unit_price",

            # customer id variants
            "customerid": "customer_id",
            "customer_id": "customer_id",

            # country variants
            "country": "country",
        }
    df = df.rename(columns=rename_map)

    # Ensure expected columns exist (some datasets vary slightly)
    expected = ["invoice_no", "stock_code", "description", "quantity",
            "invoice_date", "unit_price", "customer_id", "country"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise RuntimeError(f"[load] Missing expected columns: {missing}. Found columns: {list(df.columns)}")

    # Type normalization
    df["invoice_no"] = df["invoice_no"].astype(str)
    df["stock_code"] = df["stock_code"].astype(str)
    df["description"] = df["description"].astype(str)

    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce", utc=False)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["customer_id"] = df["customer_id"].astype(str)
    df["country"] = df["country"].astype(str)

    # Drop rows that cannot be used for time-series / aggregation
    df = df.dropna(subset=["invoice_no", "invoice_date", "quantity", "unit_price", "country"])

    # Basic trimming
    df["country"] = df["country"].str.strip()
    df["invoice_no"] = df["invoice_no"].str.strip()

    # Keep as Python-native types for COPY later
    df = df[expected]

    print(f"[load] DF ROWS: {len(df):,}")
    print(f"[load] date range: {df['invoice_date'].min()} -> {df['invoice_date'].max()}")
    return df


# ------------------------
# SNAPSHOT ID (deterministic)
# ------------------------

def compute_snapshot_id(df: pd.DataFrame) -> str:
    """
    Deterministic snapshot id based on:
    - row count
    - min/max invoice_date
    - sha256 of first N rows stable fields (to reduce collision risk)
    """
    base = f"{len(df)}|{df['invoice_date'].min()}|{df['invoice_date'].max()}"

    # Hash a small stable sample to avoid heavy cost
    sample = df.head(5000)[["invoice_no", "stock_code", "invoice_date", "quantity", "unit_price", "country"]]
    sample_bytes = sample.to_csv(index=False).encode("utf-8")

    h = hashlib.sha256()
    h.update(base.encode("utf-8"))
    h.update(sample_bytes)
    return h.hexdigest()[:16]


# ------------------------
# POSTGRES LOAD (fast COPY)
# ------------------------

def _connect() -> psycopg.Connection:
    return psycopg.connect(DB_URL)


def load_to_postgres(df: pd.DataFrame) -> None:
    snapshot_id = compute_snapshot_id(df)

    print(f"[db] connecting to: {DB_URL.replace(POSTGRES_PASSWORD, '*')}")
    with _connect() as conn:
        with conn.cursor() as cur:
            # Truth signal: where did we connect?
            cur.execute("SELECT inet_server_addr(), inet_server_port(), current_database(), current_user;")
            print("[db] CONNECTED TO:", cur.fetchone())

            # Truncate table (idempotent reset)
            print(f"[db] truncating {DB_SCHEMA}.{TABLE_NAME} ...")
            cur.execute(f"TRUNCATE TABLE {DB_SCHEMA}.{TABLE_NAME};")

            # COPY using CSV in-memory buffer
            print(f"[db] COPY loading into {DB_SCHEMA}.{TABLE_NAME} ...")
            buf = io.StringIO()
            writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)

            # Write rows in table column order
            for row in df.itertuples(index=False, name=None):
                # invoice_date must be string or datetime; psycopg COPY accepts text fine
                row = list(row)
                # Convert pandas Timestamp to ISO string (no tz)
                if hasattr(row[4], "to_pydatetime"):
                    row[4] = row[4].to_pydatetime().replace(tzinfo=None).isoformat(sep=" ")
                writer.writerow(row)

            buf.seek(0)

            copy_sql = f"""
                COPY {DB_SCHEMA}.{TABLE_NAME}
                (invoice_no, stock_code, description, quantity, invoice_date, unit_price, customer_id, country)
                FROM STDIN WITH (FORMAT CSV)
            """
            with cur.copy(copy_sql) as copy:
                copy.write(buf.getvalue())

            # Update catalog
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            cur.execute(
                f"""
                UPDATE {DB_SCHEMA}.{CATALOG_TABLE}
                SET snapshot_id = %s,
                    last_ingested_at = %s
                WHERE dataset_name = %s
                """,
                (snapshot_id, now, DATASET_NAME),
            )

            # Verify rowcount
            cur.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.{TABLE_NAME};")
            cnt = cur.fetchone()[0]

            cur.execute(f"SELECT dataset_name, snapshot_id, last_ingested_at FROM {DB_SCHEMA}.{CATALOG_TABLE} WHERE dataset_name=%s;", (DATASET_NAME,))
            cat = cur.fetchone()

            conn.commit()

    print(f"[db] loaded rows: {cnt:,}")
    print(f"[db] catalog: {cat}")


# ------------------------
# MAIN
# ------------------------

def main() -> None:
    print("[run] starting Online Retail II loader...")
    print("[run] ENV CHECK:", POSTGRES_USER, POSTGRES_DB, POSTGRES_PORT)

    download_dataset()
    df = load_dataframe()

    if len(df) == 0:
        raise RuntimeError("DataFrame is empty after load/normalize. Aborting.")

    load_to_postgres(df)
    print("[run] done.")


if __name__ == "__main__":
    main()