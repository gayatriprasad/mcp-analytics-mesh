-- Create a read-only role/user for the MCP SQL executor (least privilege)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_ro') THEN
    CREATE ROLE analytics_ro;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_executor') THEN
    CREATE USER mcp_executor WITH PASSWORD 'mcp_executor_pw';
  END IF;

  GRANT analytics_ro TO mcp_executor;
END $$;