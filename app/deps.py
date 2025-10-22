import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DB_URI = os.getenv("DB_URI", "sqlite:///data/warehouse/kpi_copilot.db")

# sqlite needs check_same_thread=False when used in ASGI contexts
engine: Engine = create_engine(DB_URI, connect_args={"check_same_thread": False})