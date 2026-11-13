import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from fastapi import Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.exceptions import HTTPException

from app.api.v1.routes import health, rfqs, suppliers
from app.db.session import Base
from app.models.enums import AuctionStatus
from app.schemas.bid import BidCreate
from app.schemas.rfq import RFQCreate
from app.schemas.supplier import SupplierCreate
from app.services.clock import FakeClock


class CaseInsensitiveDict(dict):
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default

    def __contains__(self, key):
        return any(k.lower() == str(key).lower() for k in self)

    def __getitem__(self, key):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        raise KeyError(key)


class ResponseProxy:
    def __init__(self, status_code: int, data: Any = None, headers: Optional[dict[str, str]] = None):
        self.status_code = status_code
        self._data = data
        self.headers = CaseInsensitiveDict(headers or {})

    def json(self) -> Any:
        if isinstance(self._data, str):
            return json.loads(self._data)
        return self._data

    @property
    def text(self) -> str:
        if isinstance(self._data, str):
            return self._data
        return json.dumps(self._data)


import threading

_api_lock = threading.Lock()


class DirectApiClient:
    """
    Direct in-process API test client that exercises route logic, schemas,
    and exception handlers directly without network socket loopbacks.
    Uses a fresh session per request, matching FastAPI's per-request dependency.
    """
    def __init__(self, session_factory, clock: FakeClock):
        self.session_factory = session_factory
        self.clock = clock

    def _format_http_error(self, exc: HTTPException) -> ResponseProxy:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return ResponseProxy(exc.status_code, {"error": exc.detail})
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
        }
        return ResponseProxy(
            exc.status_code,
            {
                "error": {
                    "code": code_map.get(exc.status_code, "ERROR"),
                    "message": str(exc.detail),
                    "details": {},
                }
            },
        )

    def _format_validation_error(self, exc: Exception) -> ResponseProxy:
        return ResponseProxy(
            422,
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": {},
                }
            },
        )

    def get(self, url: str, headers: Optional[dict[str, str]] = None) -> ResponseProxy:
        with _api_lock:
            parsed = urlparse(url)
            path = parsed.path
            query = parse_qs(parsed.query)

            db = self.session_factory()
            try:
                if path == "/api/v1/health":
                    res = health.health_check(db, self.clock)
                    return ResponseProxy(200, res)

                elif path == "/api/v1/suppliers":
                    q = query.get("q", [None])[0]
                    page = int(query.get("page", [1])[0])
                    page_size = int(query.get("page_size", [50])[0])
                    res = suppliers.list_suppliers(q=q, page=page, page_size=page_size, db=db)
                    return ResponseProxy(200, res.model_dump(mode="json"))

                elif path == "/api/v1/rfqs":
                    status_param = query.get("status", [None])[0]
                    status_enum = AuctionStatus(status_param) if status_param else None
                    q = query.get("q", [None])[0]
                    page = int(query.get("page", [1])[0])
                    page_size = int(query.get("page_size", [20])[0])
                    res = rfqs.list_rfqs(
                        status=status_enum,
                        q=q,
                        page=page,
                        page_size=page_size,
                        db=db,
                        clock=self.clock,
                    )
                    return ResponseProxy(200, res.model_dump(mode="json"))

                # /api/v1/rfqs/{id}/bids
                m_bids = re.match(r"^/api/v1/rfqs/([^/]+)/bids$", path)
                if m_bids:
                    rfq_id = UUID(m_bids.group(1))
                    sort = query.get("sort", ["price"])[0]
                    page = int(query.get("page", [1])[0])
                    page_size = int(query.get("page_size", [50])[0])
                    res = rfqs.list_bids_history(
                        id=rfq_id,
                        sort=sort,
                        page=page,
                        page_size=page_size,
                        db=db,
                        clock=self.clock,
                    )
                    return ResponseProxy(200, res.model_dump(mode="json"))

                # /api/v1/rfqs/{id}/activity
                m_activity = re.match(r"^/api/v1/rfqs/([^/]+)/activity$", path)
                if m_activity:
                    rfq_id = UUID(m_activity.group(1))
                    page = int(query.get("page", [1])[0])
                    page_size = int(query.get("page_size", [50])[0])
                    res = rfqs.list_activity_log(
                        id=rfq_id,
                        page=page,
                        page_size=page_size,
                        db=db,
                        clock=self.clock,
                    )
                    return ResponseProxy(200, res.model_dump(mode="json"))

                # /api/v1/rfqs/{id}
                m_rfq = re.match(r"^/api/v1/rfqs/([^/]+)$", path)
                if m_rfq:
                    rfq_id = UUID(m_rfq.group(1))
                    res = rfqs.get_rfq(id=rfq_id, db=db, clock=self.clock)
                    return ResponseProxy(200, res.model_dump(mode="json"))

                return ResponseProxy(404, {"error": {"code": "NOT_FOUND", "message": "Not Found", "details": {}}})

            except HTTPException as e:
                return self._format_http_error(e)
            except (ValueError, ValidationError) as e:
                return self._format_validation_error(e)
            finally:
                db.close()

    def post(self, url: str, json: Any = None, headers: Optional[dict[str, str]] = None) -> ResponseProxy:
        with _api_lock:
            headers = headers or {}
            parsed = urlparse(url)
            path = parsed.path

            db = self.session_factory()
            try:
                if path == "/api/v1/suppliers":
                    payload = SupplierCreate.model_validate(json)
                    res = suppliers.create_supplier(payload=payload, db=db, clock=self.clock)
                    return ResponseProxy(201, res.model_dump(mode="json"))

                elif path == "/api/v1/rfqs":
                    payload = RFQCreate.model_validate(json)
                    res = rfqs.create_rfq(payload=payload, db=db, clock=self.clock)
                    return ResponseProxy(201, res.model_dump(mode="json"))

                # /api/v1/rfqs/{id}/bids
                m_bid = re.match(r"^/api/v1/rfqs/([^/]+)/bids$", path)
                if m_bid:
                    rfq_id = UUID(m_bid.group(1))
                    payload = BidCreate.model_validate(json)
                    idempotency_key = headers.get("Idempotency-Key")
                    resp = Response()
                    res = rfqs.post_bid(
                        id=rfq_id,
                        payload=payload,
                        response=resp,
                        idempotency_key=idempotency_key,
                        db=db,
                        clock=self.clock,
                    )
                    resp_headers = dict(resp.headers)
                    return ResponseProxy(resp.status_code, res.model_dump(mode="json"), headers=resp_headers)

                return ResponseProxy(404, {"error": {"code": "NOT_FOUND", "message": "Not Found", "details": {}}})

            except HTTPException as e:
                return self._format_http_error(e)
            except (ValueError, ValidationError) as e:
                return self._format_validation_error(e)
            finally:
                db.close()


@pytest.fixture
def fake_clock():
    initial = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
    return FakeClock(initial)


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db(test_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_engine, fake_clock):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return DirectApiClient(TestingSessionLocal, fake_clock)
