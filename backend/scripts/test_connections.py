#!/usr/bin/env python3
"""
Connection verification script for Cloud PostgreSQL (Neon) and Cloud Redis (Upstash).

Usage:
    python backend/scripts/test_connections.py
    # or from project root:
    python scripts/test_connections.py
"""

import os
import re
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if backend_dir.name != "backend":
    backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import settings, backend_env


def mask_url(url: str) -> str:
    """Mask password or credentials in connection URL for safe logging."""
    if not url:
        return "(empty)"
    # Match user:pass@ or pass@
    return re.sub(r":([^:@/]+)@", r":*****@", url)


def test_postgresql() -> bool:
    print("\n" + "=" * 60)
    print(" 1. TESTING POSTGRESQL (NEON / CLOUD DB)")
    print("=" * 60)
    raw_url = settings.DATABASE_URL
    masked = mask_url(raw_url)
    print(f"[*] Configured URL: {masked}")

    if raw_url.startswith("sqlite"):
        print("[!] Note: DATABASE_URL is currently using SQLite.")
        print("    To test Neon PostgreSQL, set DATABASE_URL in backend/.env:")
        print("    DATABASE_URL=postgresql://<user>:<password>@<ep-hostname>.neon.tech/<dbname>?sslmode=require")
        return True

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import OperationalError
    except ImportError:
        print("[!] Missing dependency: SQLAlchemy is required. Install via:")
        print("    pip install -r backend/requirements.txt")
        return False

    try:
        import psycopg2  # noqa: F401
    except ImportError:
        print("[!] Missing driver: psycopg2-binary is required for PostgreSQL. Install via:")
        print("    pip install psycopg2-binary")
        return False

    start_time = time.perf_counter()
    try:
        engine = create_engine(
            raw_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        with engine.connect() as conn:
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # 1. Ping
            conn.execute(text("SELECT 1"))

            # 2. Database & User info
            info = conn.execute(text("SELECT current_database(), current_user, version()")).fetchone()
            db_name, db_user, pg_version = info[0], info[1], info[2]

            print(f"[+] Connection SUCCESSFUL ({elapsed_ms:.1f}ms latency)")
            print(f"    - Database : {db_name}")
            print(f"    - User     : {db_user}")
            print(f"    - Version  : {pg_version.split(',')[0]}")

            # 3. Check Alembic Migrations
            tables_result = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            ).fetchall()
            existing_tables = [row[0] for row in tables_result]

            if "alembic_version" in existing_tables:
                rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                print(f"    - Migrations: Applied (Revision: {rev})")
                print(f"    - Tables found: {len(existing_tables)} tables ({', '.join(sorted(existing_tables)[:6])}...)")
            else:
                print("    - Migrations: [NOT YET RUN] Table 'alembic_version' not found.")
                print("      -> Action required: Run migrations with:")
                print("         cd backend; alembic upgrade head")

        return True
    except OperationalError as oe:
        print(f"[-] PostgreSQL Connection FAILED: {oe}")
        print("    Troubleshooting checklist:")
        print("    1. Verify your connection string in backend/.env has the correct user and password.")
        print("    2. Ensure ?sslmode=require is included in the Neon connection string.")
        print("    3. If using Neon Pooled connection, ensure the hostname includes '-pooler'.")
        return False
    except Exception as exc:
        print(f"[-] PostgreSQL Connection ERROR: {exc}")
        return False


def test_redis() -> bool:
    print("\n" + "=" * 60)
    print(" 2. TESTING REDIS (UPSTASH / CELERY BROKER)")
    print("=" * 60)
    raw_url = settings.REDIS_URL
    masked = mask_url(raw_url)
    print(f"[*] Configured URL: {masked}")

    if "localhost" in raw_url or "127.0.0.1" in raw_url:
        print("[!] Note: REDIS_URL is pointing to localhost.")
        print("    To test Upstash Redis, set REDIS_URL in backend/.env:")
        print("    REDIS_URL=rediss://default:<password>@<endpoint>.upstash.io:6379")

    try:
        import redis
    except ImportError:
        print("[!] Missing dependency: redis is required. Install via:")
        print("    pip install -r backend/requirements.txt")
        return False

    is_tls = raw_url.startswith("rediss://")
    print(f"[*] Transport mode: {'TLS (rediss://) [Verified SSL]' if is_tls else 'Plain TCP (redis://)'}")

    start_time = time.perf_counter()
    try:
        connection_kwargs = {"socket_timeout": 10}
        if is_tls:
            import ssl
            connection_kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED

        client = redis.Redis.from_url(raw_url, **connection_kwargs)

        # 1. Ping
        if not client.ping():
            print("[-] Redis did not reply PONG to PING.")
            return False

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 2. Write / Read roundtrip test
        test_key = "__rfq_cloud_connectivity_probe__"
        test_val = f"probe_{int(time.time())}"
        client.setex(test_key, 30, test_val)
        read_val = client.get(test_key)
        if isinstance(read_val, bytes):
            read_val = read_val.decode("utf-8")
        client.delete(test_key)

        if read_val != test_val:
            print(f"[-] Redis read/write mismatch: wrote '{test_val}', got '{read_val}'")
            return False

        print(f"[+] Connection SUCCESSFUL ({elapsed_ms:.1f}ms latency)")
        print(f"    - PING roundtrip: OK")
        print(f"    - SET/GET/DEL probe: Verified")
        print(f"    - Role: Celery task queue broker only (DB remains source of truth)")
        return True
    except redis.exceptions.AuthenticationError as ae:
        print(f"[-] Redis Authentication FAILED: {ae}")
        print("    -> Check your Upstash Redis password/token in backend/.env.")
        return False
    except redis.exceptions.ConnectionError as ce:
        print(f"[-] Redis Connection FAILED: {ce}")
        print("    Troubleshooting checklist:")
        print("    1. Verify Upstash host and port (default: 6379).")
        print("    2. Ensure the URL starts with 'rediss://' (with double 's' for TLS).")
        return False
    except Exception as exc:
        print(f"[-] Redis Connection ERROR: {exc}")
        return False


def main():
    print("=" * 60)
    print(" British Auction RFQ System - Cloud Services Connectivity Check")
    print("=" * 60)
    if backend_env.exists():
        print(f"[i] Loaded environment from: {backend_env}")
    else:
        print(f"[i] No backend/.env found; using system environment or defaults.")

    pg_ok = test_postgresql()
    redis_ok = test_redis()

    print("\n" + "=" * 60)
    print(" SUMMARY")
    print("=" * 60)
    print(f" - PostgreSQL (Neon) : {'[PASS]' if pg_ok else '[FAIL]'}")
    print(f" - Redis (Upstash)   : {'[PASS]' if redis_ok else '[FAIL]'}")

    if pg_ok and redis_ok:
        print("\nAll configured connections are healthy!")
        sys.exit(0)
    else:
        print("\nOne or more connection checks failed. Check credentials above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
