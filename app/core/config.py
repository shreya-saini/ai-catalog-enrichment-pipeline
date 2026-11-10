
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = os.getenv(
        "APP_NAME", "AI Catalog Enrichment Pipeline"
    )

    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:///./catalog.db"
    )

    llm_mode: str = os.getenv("LLM_MODE", "mock")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    gemini_model: str = os.getenv(
        "GEMINI_MODEL", "gemini-2.5-flash"
    )

    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))


settings = Settings()
