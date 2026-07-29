-- Login roles for /usr/local/bin/agentique-sql (deploy/agentique-sql).
-- One-time, on the box:
--   docker exec -i agentique-db-1 psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--     -v ON_ERROR_STOP=1 < /opt/agentique/deploy/sql-roles.sql
--
-- Both roles are passwordless. pg_hba in the postgres image trusts local
-- socket connections (what `docker exec psql` uses) and requires a password
-- over TCP, so a passwordless role cannot log in through the ssh tunnel.
-- Neither role owns anything and neither can CREATE in `public` (PG15+ dropped
-- that default grant), so DDL stays with alembic.

-- Read-only.
CREATE ROLE agentique_ro LOGIN;
GRANT USAGE ON SCHEMA public TO agentique_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agentique_ro;
ALTER ROLE agentique_ro SET default_transaction_read_only = on;
ALTER ROLE agentique_ro SET statement_timeout = '30s';

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
