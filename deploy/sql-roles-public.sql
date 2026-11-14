-- The login role for the MCP `sql_query` tool under a reader's own token
-- (backend/app/entry/mcp/sql_query.py). It reads the `public_api` views and
-- nothing else.
-- Run it after the migration that creates the schema. Safe to run again:
--   docker exec -i agentique-db-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--     -v ON_ERROR_STOP=1 < /opt/agentique/deploy/sql-roles-public.sql
--
-- The views run with their owner's rights, so the role needs no grant on the
-- tables behind them and gets none.

DO $$
BEGIN
	IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_public') THEN
		CREATE ROLE mcp_public LOGIN;
	END IF;
END
$$;
-- Anyone with an account can send SQL through this role, so one slow query
-- must not stall the box: few connections, short statements.
ALTER ROLE mcp_public CONNECTION LIMIT 5;
ALTER ROLE mcp_public SET statement_timeout = '3s';
ALTER ROLE mcp_public SET default_transaction_read_only = on;
ALTER ROLE mcp_public SET search_path = public_api;
GRANT USAGE ON SCHEMA public_api TO mcp_public;
GRANT SELECT ON ALL TABLES IN SCHEMA public_api TO mcp_public;
-- Set out of band, not here, so no password lands in git. Same value as
-- MCP_PUBLIC_DB_PASSWORD in /opt/agentique/.env:
--   ALTER ROLE mcp_public PASSWORD '<generated>';

-- Views added later are owned by POSTGRES_USER. Replace `postgres` if
-- POSTGRES_USER is ever something else.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public_api
	GRANT SELECT ON TABLES TO mcp_public;
