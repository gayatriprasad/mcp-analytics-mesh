import psycopg
import hashlib
import time
from .config import DB_URL

def execute_sql(sql: str, params: list, max_rows: int):
    start = time.time()

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, [p["value"] for p in params] if params else [])
            rows = cur.fetchmany(max_rows)
            columns = [desc.name for desc in cur.description]
            rowcount = cur.rowcount

            # Get snapshot + readiness signal
            cur.execute("""
                SELECT snapshot_id
                FROM retail.data_catalog
                WHERE dataset_name='online_retail'
            """)
            snapshot_id = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM retail.online_retail;")
            table_count = cur.fetchone()[0]

            if snapshot_id == "UNSET" or table_count == 0:
                raise RuntimeError(f"Dataset not ready: snapshot_id={snapshot_id}, rowcount={table_count}")

            runtime_ms = int((time.time() - start) * 1000)
            sql_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]

    return {
        "rowcount": rowcount,
        "columns": columns,
        "rows": rows,
        "runtime_ms": runtime_ms,
        "sql_hash": sql_hash,
        "snapshot_id": snapshot_id
    }