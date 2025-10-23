from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///data/warehouse/kpi_copilot.db"

settings = Settings()
