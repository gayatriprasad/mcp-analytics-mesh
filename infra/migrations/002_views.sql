-- 002_views.sql: canonical metrics/views for analytics questions

CREATE SCHEMA IF NOT EXISTS retail;

-- Canonical fact view: adds revenue and return flag
CREATE OR REPLACE VIEW retail.v_sales AS
SELECT
  invoice_no,
  stock_code,
  description,
  quantity,
  unit_price,
  (quantity * unit_price) AS revenue,
  invoice_date,
  customer_id,
  country,
  CASE WHEN quantity < 0 THEN TRUE ELSE FALSE END AS is_return
FROM retail.online_retail;

-- Daily rollup (common for trend queries)
CREATE OR REPLACE VIEW retail.v_sales_daily AS
SELECT
  date_trunc('day', invoice_date) AS day,
  country,
  COUNT(DISTINCT invoice_no) AS orders,
  COUNT(DISTINCT customer_id) AS customers,
  SUM(quantity) AS units,
  SUM(quantity * unit_price) AS revenue,
  SUM(CASE WHEN quantity < 0 THEN quantity * unit_price ELSE 0 END) AS return_revenue
FROM retail.online_retail
GROUP BY 1,2;

-- Monthly rollup
CREATE OR REPLACE VIEW retail.v_sales_monthly AS
SELECT
  date_trunc('month', invoice_date) AS month,
  country,
  COUNT(DISTINCT invoice_no) AS orders,
  COUNT(DISTINCT customer_id) AS customers,
  SUM(quantity) AS units,
  SUM(quantity * unit_price) AS revenue
FROM retail.online_retail
GROUP BY 1,2;