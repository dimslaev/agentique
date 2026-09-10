-- Login roles for /usr/local/bin/agentique-sql (deploy/agentique-sql) and for
-- the MCP `sql_query` tool (backend/app/mcp/tools.py).
-- One-time, on the box:
--   docker exec -i agentique-db-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--     -v ON_ERROR_STOP=1 < /opt/agentique/deploy/sql-roles.sql
--
-- pg_hba in the postgres image trusts local socket connections (what
-- `docker exec psql` uses) and requires a password over TCP. agentique_rw
-- stays passwordless so it can only ever be reached through the socket;
-- agentique_ro needs a password because the backend reaches it over TCP on
-- loopback for the MCP tool -- see the ALTER ROLE below.
-- Neither role owns anything and neither can CREATE in `public` (PG15+ dropped
-- that default grant), so DDL stays with alembic.

-- Read-only.
CREATE ROLE agentique_ro LOGIN;
GRANT USAGE ON SCHEMA public TO agentique_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agentique_ro;
-- ...except `user`: emails and password hashes, which nothing reading through
-- this role has a reason to see. Re-run this file after any restore that
-- recreates the table -- the default privileges at the bottom grant SELECT on
-- every new table, this one included.
REVOKE SELECT ON TABLE "user" FROM agentique_ro;
ALTER ROLE agentique_ro SET default_transaction_read_only = on;
ALTER ROLE agentique_ro SET statement_timeout = '30s';
-- Set out of band, not here, so no password lands in git. Same value as
-- MCP_DB_PASSWORD in /opt/agentique/.env:
--   ALTER ROLE agentique_ro PASSWORD '<generated>';
-- SELECT-only and read-only by default, so the worst a leak buys is a copy of
-- data the site already publishes.

-- Read/write DML.
CREATE ROLE agentique_rw LOGIN;
GRANT USAGE ON SCHEMA public TO agentique_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO agentique_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agentique_rw;
-- lock_timeout keeps a bad write from stalling the backend behind a lock.
ALTER ROLE agentique_rw SET statement_timeout = '60s';
ALTER ROLE agentique_rw SET lock_timeout = '5s';
ALTER ROLE agentique_rw SET idle_in_transaction_session_timeout = '60s';

-- Tables created later (alembic, or a --clean restore) are owned by
-- POSTGRES_USER, so grant on its future objects too. Replace `postgres` if
-- POSTGRES_USER is ever something else.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
	GRANT SELECT ON TABLES TO agentique_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
	GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agentique_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
	GRANT USAGE, SELECT ON SEQUENCES TO agentique_rw;
