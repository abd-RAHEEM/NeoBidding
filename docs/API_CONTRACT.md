# API Contract — British Auction RFQ System

> Version 0.2 · Phase 0 (rev 1)  
> Base path: `/api/v1`  
> OpenAPI docs: `GET /docs` (Swagger UI), `GET /redoc`  
> All timestamps: ISO 8601 UTC (`2026-11-14T00:00:00Z`)  
> All monetary values: **strings** in the JSON response (e.g. `"47500.00"`)  
> Error envelope: `{"error": {"code": "...", "message": "...", "details": {...}}}`

---

## Authentication

None in this demo. The bid endpoint accepts a `supplier_id` field in the request body. Document: in production this would be extracted from a JWT claim.

---

## Common Headers

| Header | Direction | Notes |
|--------|-----------|-------|
| `Content-Type: application/json` | Request | Required for POST |
| `Idempotency-Key: <uuid>` | Request | **Optional at the API level** (omit in curl / Swagger); **mandatory in the frontend** (always `crypto.randomUUID()` per attempt). Requests without a key are accepted but have **no retry guarantee** — a network retry will create a duplicate bid. |
| `Idempotent-Replay: true` | Response | Present when a replay is returned |

---

## Endpoints

### `GET /health`

```
200 OK
{
  "status": "ok",
  "db": "ok",
  "time": "2026-11-14T00:00:00Z"
}
```

---

### `GET /suppliers`

List all suppliers.

**Query params:** `q` (search by name), `page` (default 1), `page_size` (default 50, max 200)

**Response 200:**

```json
{
  "items": [
    { "id": "uuid", "name": "Maersk", "created_at": "2026-11-14T00:00:00Z" }
  ],
  "total": 10,
  "page": 1,
  "page_size": 50
}
```

---

### `POST /suppliers`

Create a supplier.

**Request body:**

```json
{ "name": "DHL Freight" }
```

**Response 201:**

```json
{ "id": "uuid", "name": "DHL Freight", "created_at": "2026-11-14T00:00:00Z" }
```

**Errors:**

- `409 SUPPLIER_NAME_CONFLICT` — name already exists

---

### `POST /rfqs`

Create a new RFQ.

**Request body:**

```json
{
  "name": "India–Dubai Q4 Freight",
  "reference_id": "RFQ-2026-001",
  "currency": "INR",
  "pickup_date": "2026-12-01",
  "bid_start_time": "2026-11-20T10:00:00Z",
  "bid_close_time": "2026-11-20T18:00:00Z",
  "forced_close_time": "2026-11-20T18:30:00Z",
  "auction_type": "BRITISH",
  "invited_supplier_ids": ["uuid1", "uuid2", "uuid3"],
  "british_config": {
    "trigger_window_minutes": 10,
    "extension_minutes": 5,
    "extension_trigger": "L1_CHANGE_IN_LAST_X"
  }
}
```

**Validation rules:**

- `forced_close_time > bid_close_time > bid_start_time`
- `len(invited_supplier_ids) >= 1`
- If `auction_type == "BRITISH"`, `british_config` is required with valid X ≥ 1, Y ≥ 1
- If `auction_type == "STANDARD"`, `british_config` must be absent or null
- `reference_id` unique
- `currency` in `{INR, USD, EUR, GBP, AED}`

**Response 201:**

```json
{
  "id": "uuid",
  "reference_id": "RFQ-2026-001",
  "name": "India–Dubai Q4 Freight",
  "currency": "INR",
  "pickup_date": "2026-12-01",
  "auction_type": "BRITISH",
  "bid_start_time": "2026-11-20T10:00:00Z",
  "original_close_time": "2026-11-20T18:00:00Z",
  "current_close_time": "2026-11-20T18:00:00Z",
  "forced_close_time": "2026-11-20T18:30:00Z",
  "status": "SCHEDULED",
  "british_config": {
    "trigger_window_minutes": 10,
    "extension_minutes": 5,
    "extension_trigger": "L1_CHANGE_IN_LAST_X"
  },
  "invited_suppliers": [
    { "id": "uuid1", "name": "Maersk" },
    { "id": "uuid2", "name": "DHL" },
    { "id": "uuid3", "name": "FedEx" }
  ],
  "created_at": "2026-11-14T00:00:00Z",
  "server_time": "2026-11-14T00:00:00Z"
}
```

**Errors:**

- `422` — validation failure (forced <= close, close <= start, invalid config, etc.)
- `409 REFERENCE_ID_CONFLICT`
- `404 SUPPLIER_NOT_FOUND` — one of the invited supplier IDs does not exist

---

### `GET /rfqs`

List auctions with filtering and pagination.

> **Status is always derived from timestamps, never from the cached `status` column.** The implementation uses a SQL `CASE` expression over `bid_start_time`, `current_close_time`, and `forced_close_time` with the server's current time (`NOW()` at query execution). The `?status=` filter applies this derived expression so that results are always correct regardless of whether the Celery sweeper has run.

**Query params:**

| Param       | Type   | Notes                                           |
| ----------- | ------ | ----------------------------------------------- |
| `status`    | enum   | `SCHEDULED`, `ACTIVE`, `CLOSED`, `FORCE_CLOSED` |
| `q`         | string | Search by name or reference_id                  |
| `page`      | int    | Default 1                                       |
| `page_size` | int    | Default 20, max 100                             |

**Response 200:**

```json
{
  "items": [
    {
      "id": "uuid",
      "reference_id": "RFQ-2026-001",
      "name": "India–Dubai Q4 Freight",
      "currency": "INR",
      "auction_type": "BRITISH",
      "current_lowest_bid": "47500.00",
      "current_close_time": "2026-11-20T18:05:00Z",
      "forced_close_time": "2026-11-20T18:30:00Z",
      "status": "ACTIVE",
      "bid_start_time": "2026-11-20T10:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "server_time": "2026-11-14T00:00:00Z"
}
```

---

### `GET /rfqs/{id}`

Auction detail with ranking, stats and config.

**Response 200:**

```json
{
  "id": "uuid",
  "reference_id": "RFQ-2026-001",
  "name": "India–Dubai Q4 Freight",
  "currency": "INR",
  "pickup_date": "2026-12-01",
  "auction_type": "BRITISH",
  "bid_start_time": "2026-11-20T10:00:00Z",
  "original_close_time": "2026-11-20T18:00:00Z",
  "current_close_time": "2026-11-20T18:05:00Z",
  "forced_close_time": "2026-11-20T18:30:00Z",
  "status": "ACTIVE",
  "british_config": {
    "trigger_window_minutes": 10,
    "extension_minutes": 5,
    "extension_trigger": "L1_CHANGE_IN_LAST_X"
  },
  "invited_suppliers": [
    { "id": "uuid1", "name": "Maersk" },
    { "id": "uuid2", "name": "DHL" },
    { "id": "uuid3", "name": "FedEx" }
  ],
  "ranking": [
    {
      "rank": 1,
      "supplier_id": "uuid2",
      "supplier_name": "DHL",
      "carrier_name": "DHL Freight GmbH",
      "freight_charges": "40000.00",
      "origin_charges": "5000.00",
      "destination_charges": "2500.00",
      "total_price": "47500.00",
      "transit_time_days": 14,
      "quote_validity_days": 30,
      "submitted_at": "2026-11-20T17:55:00Z",
      "bid_id": "uuid"
    },
    {
      "rank": null,
      "supplier_id": "uuid3",
      "supplier_name": "FedEx",
      "carrier_name": null,
      "total_price": null,
      "submitted_at": null,
      "bid_id": null,
      "no_bid": true
    }
  ],
  "stats": {
    "total_bids": 12,
    "suppliers_bidding": 2,
    "suppliers_invited": 3,
    "extension_count": 2,
    "first_bid_price": "52000.00",
    "current_lowest_price": "47500.00",
    "price_improvement_pct": "8.65"
  },
  "created_at": "2026-11-14T00:00:00Z",
  "server_time": "2026-11-20T17:58:00Z"
}
```

---

### `GET /rfqs/{id}/bids`

Full bid history for an RFQ.

**Query params:**

| Param       | Type | Default | Notes                                             |
| ----------- | ---- | ------- | ------------------------------------------------- |
| `sort`      | enum | `price` | `price` (total asc) or `time` (submitted_at desc) |
| `page`      | int  | 1       |                                                   |
| `page_size` | int  | 50      | Max 200                                           |

**Response 200:**

```json
{
  "items": [
    {
      "id": "uuid",
      "rfq_id": "uuid",
      "supplier_id": "uuid2",
      "supplier_name": "DHL",
      "carrier_name": "DHL Freight GmbH",
      "freight_charges": "40000.00",
      "origin_charges": "5000.00",
      "destination_charges": "2500.00",
      "total_price": "47500.00",
      "transit_time_days": 14,
      "quote_validity_days": 30,
      "submitted_at": "2026-11-20T17:55:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 50,
  "server_time": "2026-11-20T17:58:00Z"
}
```

---

### `POST /rfqs/{id}/bids`

Submit a bid. The `Idempotency-Key` header is **optional at the API level** (omit for curl/Swagger). **The frontend always sends one** (`crypto.randomUUID()` per submission attempt, reused on retry, regenerated after success). Without a key, the request has no retry guarantee.

> **`carrier_name` is not accepted from the client.** The server derives it by looking up `suppliers.name` for the given `supplier_id` and stores it as a snapshot. This prevents identity spoofing and ensures historical consistency even if a supplier's name is later changed.

**Request header (optional for API; mandatory for UI):**

```
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

**Request body:**

```json
{
  "supplier_id": "uuid2",
  "freight_charges": "40000.00",
  "origin_charges": "5000.00",
  "destination_charges": "2500.00",
  "transit_time_days": 14,
  "quote_validity_days": 30
}
```

**Response 201 (new bid):**

```json
{
  "bid": {
    "id": "uuid",
    "rfq_id": "uuid",
    "supplier_id": "uuid2",
    "carrier_name": "DHL",
    "freight_charges": "40000.00",
    "origin_charges": "5000.00",
    "destination_charges": "2500.00",
    "total_price": "47500.00",
    "transit_time_days": 14,
    "quote_validity_days": 30,
    "submitted_at": "2026-11-20T17:55:00Z"
  },
  "rank": 1,
  "extended": true,
  "new_close_time": "2026-11-20T18:05:00Z",
  "extension_reason": "L1 changed from Maersk to DHL at 5:55:00 PM, inside the last 10 min window. Close moved 6:00 PM → 6:05 PM.",
  "server_time": "2026-11-20T17:55:00Z"
}
```

**Response 200 (idempotency replay):**
Same body as original success response, plus header:

```
Idempotent-Replay: true
```

**Errors:**

| HTTP  | Code                       | Trigger                                           |
| ----- | -------------------------- | ------------------------------------------------- |
| `403` | `SUPPLIER_NOT_INVITED`     | `supplier_id` not in `rfq_suppliers` for this RFQ |
| `409` | `AUCTION_NOT_STARTED`      | `now < bid_start_time`                            |
| `409` | `AUCTION_CLOSED`           | `now >= current_close_time`                       |
| `409` | `IDEMPOTENCY_KEY_CONFLICT` | Same key, different payload                       |
| `422` | `BID_NOT_LOWER`            | Total ≥ supplier's current best bid               |
| `422` | `INVALID_CHARGES`          | Negative charges, total ≤ 0, total ≠ sum          |
| `422` | Pydantic                   | Missing fields, wrong types                       |
| `404` | `RFQ_NOT_FOUND`            | Unknown RFQ ID                                    |

---

### `GET /rfqs/{id}/activity`

Auction event log, ordered chronologically.

**Query params:** `page`, `page_size`

**Response 200:**

```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "TIME_EXTENDED",
      "bid_id": "uuid",
      "payload": {
        "trigger_type": "L1_CHANGE_IN_LAST_X",
        "old_close": "2026-11-20T18:00:00Z",
        "new_close": "2026-11-20T18:05:00Z",
        "extension_minutes": 5
      },
      "reason": "L1 changed from Maersk to DHL at 5:55:00 PM, inside the last 10 min window. Close moved 6:00 PM → 6:05 PM.",
      "occurred_at": "2026-11-20T17:55:00Z",
      "created_at": "2026-11-20T17:55:00Z",
      "is_recovered": false
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 50,
  "server_time": "2026-11-20T17:58:00Z"
}
```

---

## Error Envelope

All error responses use this structure:

```json
{
  "error": {
    "code": "SUPPLIER_NOT_INVITED",
    "message": "Supplier uuid2 is not invited to RFQ uuid.",
    "details": {
      "supplier_id": "uuid2",
      "rfq_id": "uuid"
    }
  }
}
```

---

## Money Serialization

Monetary values are always serialized as **strings** to preserve exact decimal representation:

```python
# Python (Pydantic v2 custom serializer)
@field_serializer('total_price', 'freight_charges', ...)
def serialize_decimal(self, v: Decimal) -> str:
    return str(v.quantize(Decimal("0.01")))
```

The frontend parses these as strings and formats with `Intl.NumberFormat`:

```ts
new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(
  Number(total_price),
);
```

---

## Pagination

All list endpoints use offset-based pagination:

| Param       | Default | Notes                   |
| ----------- | ------- | ----------------------- |
| `page`      | 1       | 1-indexed               |
| `page_size` | varies  | Bounded by endpoint max |

Response includes `total` (total matching rows), `page`, `page_size`.

---

## CORS

```python
origins = [os.getenv("CORS_ORIGIN", "http://localhost:5173")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
```
