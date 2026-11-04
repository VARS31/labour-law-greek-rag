"""Postgres connection and schema (the numbered files in sql/)."""

import psycopg

from .config import ROOT, load_settings

SQL_DIR = ROOT / "sql"
HNSW_EF_SEARCH = 100   # pgvector returns at most ef_search rows from an HNSW scan; hybrid search asks for 50


def connect(settings=None, **kwargs):
    s = settings or load_settings()
    conn = psycopg.connect(host=s.postgres_host, port=s.postgres_port, dbname=s.postgres_db,
                           user=s.postgres_user, password=s.postgres_password, **kwargs)
    conn.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH}")
    # Our queries are small, so compiling them (JIT) never pays off. It also fires by mistake when semantic search
    # switches sequential scans off: that adds a huge artificial cost, and JIT then added ~27 ms to a ~7 ms scan.
    conn.execute("SET jit = off")
    return conn


def friendly_errors(fn):
    """Run a command's main(): if the database or Ollama can't be reached, print one clear line instead of a
    traceback and exit with status 1."""
    from .model_client import ModelError
    try:
        fn()
    except psycopg.OperationalError as error:
        s = load_settings()
        raise SystemExit(f"Can't reach the database at {s.postgres_host}:{s.postgres_port}. Is it running? "
                         f"Start it with: docker compose up -d\n({str(error).strip().splitlines()[0]})") from None
    except ModelError as error:
        raise SystemExit(f"{error}\nIs Ollama running? Check with: ollama list") from None


def schema_files(upto=None):
    files = sorted(SQL_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    return [f for f in files if upto is None or int(f.name[:3]) <= upto]


def apply_schema(conn, upto=None):
    """Run sql/001_….sql, sql/002_….sql, … in order. Every file is safe to run again."""
    for path in schema_files(upto):
        conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()


def vector_literal(values):
    """A Python list of floats as pgvector text: '[0.1,0.2,…]'. Pass it with a ::vector cast."""
    return "[" + ",".join(f"{x:.7g}" for x in values) + "]"
