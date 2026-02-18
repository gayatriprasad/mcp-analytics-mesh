from __future__ import annotations
import re
import sqlglot

DISALLOWED = {"INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP", "TRUNCATE", "GRANT", "REVOKE"}

def is_safe_readonly_sql(sql: str) -> tuple[bool, str]:
    s = sql.strip().rstrip(";")
    if not s:
        return False, "empty_sql"

    # quick deny patterns
    if re.search(r"\bselect\s+\*\b", s, flags=re.IGNORECASE):
        return False, "select_star_not_allowed"

    try:
        expr = sqlglot.parse_one(s)
    except Exception:
        return False, "sql_parse_failed"

    # only allow SELECT / WITH ... SELECT
    kind = expr.key.upper()
    if kind not in {"SELECT", "WITH"}:
        return False, f"statement_not_allowed:{kind}"

    # deny if any disallowed tokens appear in the parsed SQL string form
    normalized = expr.sql(dialect="postgres").upper()
    for kw in DISALLOWED:
        if re.search(rf"\b{kw}\b", normalized):
            return False, f"keyword_not_allowed:{kw}"

    return True, "ok"
