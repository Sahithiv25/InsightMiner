from sqlalchemy import text
from pandas import DataFrame
from app.deps import engine
import pandas as pd

DENYLIST = ("UPDATE", "DELETE", "INSERT", "DROP", "ALTER", "ATTACH", "PRAGMA")

def run_sql(sql: str) -> DataFrame:
    upper = sql.upper()
    if any(kw in upper for kw in DENYLIST):
        raise ValueError("Unsafe SQL")
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    return df
