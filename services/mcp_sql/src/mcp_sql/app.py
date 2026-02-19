from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .executor import execute_sql
from .safety import is_safe_readonly_sql
from .audit import emit_event
from .config import MAX_DEFAULT_ROWS

app = FastAPI(title="MCP SQL Service")

class SQLRequest(BaseModel):
    trace_id: str
    sql: str
    params: list = []
    max_rows: int = MAX_DEFAULT_ROWS

@app.get("/schema")
def get_schema():
    return {
        "allowed_schema": "retail",
        "tables": ["online_retail"]
    }

@app.post("/execute_sql_safe")
def execute(req: SQLRequest):

    safe, reason = is_safe_readonly_sql(req.sql)
    if not safe:
        raise HTTPException(status_code=400, detail=f"Unsafe SQL: {reason}")

    try:
        result = execute_sql(req.sql, req.params, req.max_rows)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    emit_event(req.trace_id, "SQL_EXECUTED", result)

    return result