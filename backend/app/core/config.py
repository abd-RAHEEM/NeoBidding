import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project or backend root if present
backend_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(backend_dir / ".env")


class Settings:
    PROJECT_NAME: str = "British Auction RFQ System"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./rfq.db"
    )
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0"
    )
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000").split(",")
        if origin.strip()
    ]


settings = Settings()

