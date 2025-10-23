from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///data/warehouse/kpi_copilot.db"
    KPI_PLANNER_MODE: str = "auto"    # "auto" | "llm" | "registry"

    # Insights narrator
    INSIGHTS_MODE: str = "auto"       # "auto" | "llm" | "deterministic"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT: int = 8              # seconds
    LLM_MAX_TOKENS: int = 180         # very small; 2–3 bullets
    OPENAI_API_KEY: str | None = None

settings = Settings()
