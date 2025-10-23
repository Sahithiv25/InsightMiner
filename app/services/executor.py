from __future__ import annotations
import pandas as pd
from sqlalchemy import create_engine
from app.core.config import settings  # or wherever your DB URL lives

_engine = create_engine(settings.DATABASE_URL, future=True)

def run_sql(sql: str) -> pd.DataFrame:
    with _engine.connect() as con:
        return pd.read_sql(sql, con)

def run_sql_explain(sql: str) -> None:
    """Raise if SQLite can't parse/plan the query."""
    explain = f"EXPLAIN QUERY PLAN {sql}"
    with _engine.connect() as con:
        _ = con.exec_driver_sql(explain).fetchall()
