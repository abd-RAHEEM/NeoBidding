import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend/.env is loaded reliably regardless of working directory
backend_dir = Path(__file__).resolve().parent.parent.parent
backend_env = backend_dir / ".env"
root_env = backend_dir.parent / ".env"

if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv()


def normalize_database_url(url: str | None) -> str:
    """
    Ensure PostgreSQL connection strings are compatible with SQLAlchemy and psycopg2.
    Translates legacy postgres:// scheme (commonly provided by cloud hosts like Neon/Render)
    to postgresql://.
    """
    if not url:
        return "sqlite:///./rfq.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def normalize_redis_url(url: str | None) -> str:
    """
    Sanitize and normalize Redis URLs.
    Handles users pasting the CLI command from Upstash Console (e.g., redis-cli --tls -u redis://...)
    and ensures TLS (rediss://) is used for cloud-hosted Redis like Upstash.
    """
    if not url:
        return "redis://localhost:6379/0"
    url = url.strip()
    if "redis-cli" in url:
        has_tls = "--tls" in url
        import re
        match = re.search(r"-u\s+([^\s]+)", url)
        if match:
            url = match.group(1).strip('"\'')
        if has_tls and url.startswith("redis://"):
            url = url.replace("redis://", "rediss://", 1)
    elif "upstash.io" in url and url.startswith("redis://"):
        url = url.replace("redis://", "rediss://", 1)
    return url


class Settings:
    PROJECT_NAME: str = "NeoBidding: British Auction RFQ System"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///./rfq.db")
    )
    REDIS_URL: str = normalize_redis_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in (os.getenv("CORS_ORIGIN") or os.getenv("CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000").split(",")
        if origin.strip()
    ]


settings = Settings()
