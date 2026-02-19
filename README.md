# MCP Analytics Mesh

A deterministic, auditable, multi-agent analytics backbone built from
scratch using: - Model Context Protocol (MCP) principles - Schema-first
contracts - Single-writer architecture - Postgres (Dockerized) -
FastAPI-based MCP services - Structured audit logging

------------------------------------------------------------------------

## 🚀 Project Overview

This project was intentionally built **from zero infrastructure** to a
working, deterministic analytics mesh.

It includes:

-   Dockerized Postgres
-   Controlled schema migrations
-   Online Retail II dataset ingestion (\~1M rows)
-   Snapshot-based data cataloging
-   Read-only MCP SQL service
-   Structured audit trail
-   Fail-fast dataset readiness guard

This was not built in a straight line. Multiple roadblocks were
encountered and solved systematically.

------------------------------------------------------------------------

## 🧱 Architecture Philosophy

This project follows staff-level engineering principles:

### 1️⃣ Determinism First

-   Explicit schema migrations
-   Snapshot IDs tied to dataset state
-   Fail-fast behavior when dataset is not ready

### 2️⃣ Schema-First Contracts

-   Canonical retail schema
-   Analytics views (`v_sales`, `v_sales_daily`, `v_sales_monthly`)
-   Controlled SQL execution path

### 3️⃣ Auditability

-   Every query emits structured JSON audit logs
-   Snapshot ID included in every response
-   SQL hash recorded

### 4️⃣ Isolation of Concerns

-   `infra_utils` → data ingestion and migrations
-   `mcp_sql` → controlled SQL execution
-   Workspace-based project separation using `uv`

------------------------------------------------------------------------

## 📦 Phase 1A -- Infrastructure + Data Layer

### ✔ Dockerized Postgres

-   Port 5432 exposed
-   Role-based access
-   Schema initialization via migrations

### ✔ Online Retail II Loader

Challenges solved: - Broken UCI download URLs - Column name
inconsistencies (`invoice` vs `invoice_no`, `price` vs `unit_price`) -
Bulk loading performance (moved from row inserts → COPY) - Environment
resolution across workspace

Result: - 1,067,371 rows loaded - Deterministic snapshot ID - Data
catalog updated

Example verification:

``` sql
SELECT COUNT(*) FROM retail.online_retail;
```

------------------------------------------------------------------------

## 📊 Analytical Views

Created canonical views:

-   `retail.v_sales`
-   `retail.v_sales_daily`
-   `retail.v_sales_monthly`

These standardize: - Revenue = quantity \* unit_price - Order counts -
Customer counts - Returns flag

------------------------------------------------------------------------

## 🔐 MCP SQL Service

FastAPI service exposing:

### GET `/schema`

Returns allowed schema metadata.

### POST `/execute_sql_safe`

-   Read-only enforcement
-   Dataset readiness guard
-   Snapshot-aware responses
-   Structured audit logging

Example request:

``` json
{
  "trace_id": "test123",
  "sql": "SELECT country, SUM(quantity*unit_price) AS revenue FROM retail.online_retail GROUP BY country ORDER BY revenue DESC LIMIT 5",
  "params": [],
  "max_rows": 100
}
```

------------------------------------------------------------------------

## 🧠 Key Engineering Learnings

This project required solving real-world engineering issues:

-   Port collisions and container validation
-   dotenv resolution across workspace boundaries
-   Decimal JSON serialization failures
-   Bulk data loading optimization
-   Uvicorn module path resolution
-   Dataset variant schema mismatches
-   Fail-fast guard design for empty datasets

Each issue was resolved systematically with: - Explicit debugging
signals - Deterministic validation queries - Incremental hardening

------------------------------------------------------------------------

## 🛠 Local Setup

### 1. Clone repository

    git clone <repo_url>
    cd mcp-analytics-mesh

### 2. Create environment

    uv venv
    source .venv/bin/activate
    uv sync

### 3. Start Postgres

    docker compose -f infra/docker/docker-compose.yml up -d
    ./scripts/db_migrate.sh

### 4. Load dataset

    uv run --project services/infra_utils python -u services/infra_utils/src/infra_utils/load_online_retail.py

### 5. Start MCP SQL service

    uv run --project services/mcp_sql uvicorn mcp_sql.app:app --reload --port 8001

------------------------------------------------------------------------

## 📈 Current Status

-   Data layer: ✅ Complete
-   MCP SQL service: ✅ Operational
-   Snapshot determinism: ✅ Verified
-   Audit trail: ✅ Verified

Next planned phase: - SQLSpec contract enforcement - QueryPlan
orchestration - Multi-agent mesh wiring

------------------------------------------------------------------------

## 🎯 Why This Project Matters

This is not a toy demo.

It demonstrates: - Real infra wiring - Deterministic data lifecycle -
Audit-compliant query execution - Schema-first multi-agent design
foundations

It reflects production-grade thinking applied to a controlled
environment.

------------------------------------------------------------------------

Built: 2026-02-19T05:21:42.662821 UTC
