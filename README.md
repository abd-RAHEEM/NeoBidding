# British Auction RFQ System

> Full-Stack Intern Assignment · Python/FastAPI + React

---

## Quick Start (Docker — one command)

```bash
docker compose up --build
```

Then open:

- **UI:** http://localhost:5173
- **API docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/api/v1/health

---

## Project Status

| Phase                                                     | Status      | Notes             |
| --------------------------------------------------------- | ----------- | ----------------- |
| Phase 0 — HLD, Schema, API Contract                       | ✅ Complete | Revised (rev 1); approved |
| Phase 1 — Auction Engine + State Machine + Unit Tests     | ✅ Complete | 37 unit tests passing (P0) |
| Phase 2 — Bid Service, API, Migrations, Integration Tests | 🔲 Pending  | Awaiting Phase 1 approval |
| Phase 3 — Celery Sweeper + Recovery Tests                 | 🔲 Pending  |                   |
| Phase 4 — React Frontend                                  | 🔲 Pending  |                   |
| Phase 5 — Docker, Seed, README completion                 | 🔲 Pending  |                   |
| Phase 6 — Full Verification                               | 🔲 Pending  |                   |

---

## Assumptions & Decisions

> All ambiguous spec points are resolved here. Entries 16–22 were added in Phase 0 rev 1.

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Idempotency-Key is optional at the API level** | Allows curl/Swagger testing without a key; the UI always sends one. |
| 2 | **Monetary values serialized as strings** | Preserves exact decimal representation; avoids JSON float precision loss. |
| 3 | **Rank ties broken by (submitted_at ASC, bid_id ASC)** | The earlier bid wins ties — first-mover advantage is the most defensible tiebreaker. |
| 4 | **`in_trigger_window` left-bound is inclusive** | A bid at exactly `T_c - X minutes` is inside the window. This maximises the extension opportunity, which is the intent of the British Auction. |
| 5 | **A new supplier's first bid counts as an L1 change** | There is no prior L1 when it is the first bid; the new supplier becomes L1, so L1 changed from "none" to them. This is stated in the spec. |
| 6 | **Extension added to `current_close_time`, not `now`** | Prevents the window from shrinking when the trigger fires late in the window. |
| 7 | **Status derived from timestamps, stored as cache** | The DB column is only used for query filtering. Business logic always calls `derive_status()`. |
| 8 | **Redis is Celery broker only** | No app state, counters, or caches in Redis. PostgreSQL is the single source of truth. |
| 9 | **No auth** | Explicitly out of scope. `supplier_id` is passed in the request body. Future work: JWT middleware. |
| 10 | **All visibility is open** | All data visible to all viewers. See HLD §14. |
| 11 | **Polling at 3 s** | Simpler than SSE/WebSocket; upgrade path documented in HLD §15. |
| 12 | **`FORCE_CLOSED` when `current_close == forced_close`** | If the auction extended all the way to `forced_close`, it closes as `FORCE_CLOSED`, not `CLOSED`. |
| 13 | **Idempotency key stored as VARCHAR(64)** | UUID v4 is 36 chars; 64 gives headroom without being unbounded. Keys longer than 64 chars are rejected with 422. |
| 14 | **`is_recovered = true` threshold: 5 seconds** | Events written more than 5 s after their `occurred_at` are flagged as recovered. |
| 15 | **`AUCTION_CREATED` event written at RFQ creation time** | The first event in the log is creation, written inside the same transaction as the RFQ row. |
| 16 | **`carrier_name` is derived from `suppliers.name`, not client-supplied** | Prevents identity spoofing; preserves historical name at bid time even if the supplier record is later renamed. The bid request body has no `carrier_name` field. |
| 17 | **`GET /rfqs` status is computed with a SQL CASE expression, never from the cached column** | The cached `status` column is for Celery to identify stale rows. API responses always reflect the timestamp-derived status, so they are correct even when Celery is offline. |
| 18 | **No hard-delete endpoints for `suppliers` or `rfqs`** | Historical bids and audit events would be silently orphaned. `bids.rfq_id`, `bids.supplier_id`, `auction_events.rfq_id`, and `auction_events.bid_id` FKs are `ON DELETE RESTRICT`. Config rows (`british_auction_configs`, `rfq_suppliers`) cascade-delete with the RFQ because they carry no independent historical value. |
| 19 | **`submitted_at`, `occurred_at`, and `created_at` on events are set by `clock.now()`; no `DEFAULT NOW()` on those columns** | Ensures the injectable `FakeClock` controls all timestamp values in tests. DB `NOW()` defaults are only kept on `suppliers.created_at`, `rfqs.created_at`, and `rfq_suppliers.invited_at` where the auction engine never inspects the value. |
| 20 | **Frontend always sends `Idempotency-Key`; requests without one have no retry guarantee** | Documented clearly in the API contract and UI code. The API accepts key-less requests for curl/Swagger ergonomics only. |
| 21 | **No separate index on `(rfq_id, supplier_id, idempotency_key)`** | The `UNIQUE` constraint on `bids` already creates a B-tree index on those columns. A separate `CREATE INDEX` would be redundant and waste write overhead. |
| 22 | **BRITISH ↔ config invariant enforced at the application layer** | The DB enforces *at most one* config via the PK on `british_auction_configs`. The *exactly one for BRITISH / none for STANDARD* rule is enforced at the route + Pydantic validation layer, which is 100% tested by integration tests. A DB trigger would add complexity without additional safety. |

---

## Docs

- [High-Level Design (HLD)](docs/HLD.md)
- [Database Schema](docs/SCHEMA.md)
- [API Contract](docs/API_CONTRACT.md)

---

_Full README with setup, test commands, demo walkthrough, and known limitations will be completed in Phase 5._
