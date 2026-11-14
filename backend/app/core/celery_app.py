import ssl
from app.core.config import settings

try:
    from celery import Celery

    celery_app = Celery(
        "rfq_worker",
        broker=settings.REDIS_URL,
        backend=None,  # Redis is ONLY the broker; PostgreSQL is single source of truth
        include=["app.services.tasks"],
    )

    conf_updates = {
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "timezone": "UTC",
        "enable_utc": True,
        "beat_schedule": {
            "finalize_due_auctions_every_5s": {
                "task": "app.services.tasks.finalize_due_auctions",
                "schedule": 5.0,  # runs every 5 seconds
            },
        },
    }

    # Upstash and secure cloud Redis instances use rediss:// with TLS.
    # Enable SSL certificate verification for Celery / Kombu.
    if settings.REDIS_URL.startswith("rediss://"):
        conf_updates["broker_use_ssl"] = {
            "ssl_cert_reqs": ssl.CERT_REQUIRED,
        }

    celery_app.conf.update(**conf_updates)
except ImportError:
    # Graceful fallback when running in lightweight environments without Celery installed
    class MockCelery:
        conf = {}

        def task(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    celery_app = MockCelery()
