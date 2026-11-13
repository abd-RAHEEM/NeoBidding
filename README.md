# British Reverse Auction in an RFQ System

> Production-Grade Full-Stack Implementation · Python/FastAPI + React 18 + PostgreSQL + Celery + Redis

[![Tests](https://img.shields.io/badge/backend%20tests-54%20passed-0B6E4F?style=flat-square)](backend/tests/)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-10%20passed-0B6E4F?style=flat-square)](frontend/src/test/)
[![Python](https://img.shields.io/badge/python-3.11%2B%20%7C%203.12-1B1F24?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18%20%7C%20Vite%206-61DAFB?style=flat-square&logo=react)](frontend/)
[![Tailwind](https://img.shields.io/badge/Tailwind-Custom%20Tokens-38B2AC?style=flat-square&logo=tailwindcss)](frontend/tailwind.config.js)

---

## 1. Quick Start

### Option A: One Command with Docker Compose (Recommended)

```bash
docker compose up --build
```

This single command starts:
- **PostgreSQL 15** with schema migrations applied automatically
- **Redis 7** (broker for Celery)
- **FastAPI Backend (`api`)** with live seed data on startup
- **Celery Worker & Celery Beat** (lifecycle sweeper)
- **React Frontend (`web`)** served via Nginx with `/api` reverse proxy

Open in your browser:
- **Trading Desk UI:** [http://localhost:5173](http://localhost:5173) (or [http://localhost:3000](http://localhost:3000))
- **Interactive OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Health & DB Sync:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

### Option B: Running Locally (Without Docker)

#### Prerequisites
- Python 3.11+ (or 3.12)
- Node.js 20+ & pnpm (or npm)

#### 1. Backend Setup
```bash
# From repository root
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python ../scripts/seed.py --live
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup
```bash
# In a separate terminal
cd frontend
pnpm install
pnpm dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 2. Project Status & Deliverables

| Tier | Component | Status | Test Coverage |
| :--- | :--- | :---: | :--- |
| **P0** | **Pure Auction Engine & State Machine** | ✅ Complete | 37 unit tests passing (boundary rules, ranking, trigger evaluation, cap mathematics) |
| **P1** | **PostgreSQL Schema & Alembic Migrations** | ✅ Complete | 6 DB CHECK constraint & foreign key integrity tests |
| **P1** | **13-Step Transactional Bid Service** | ✅ Complete | Row locks (`FOR UPDATE`), strictly-lower validation, auto-snapshotting |
| **P1** | **REST APIs (`/api/v1/rfqs`, `/suppliers`)** | ✅ Complete | Full workflow acceptance scenario, idempotency replay, server-time sync |
| **P1** | **React 18 Trading Desk UI** | ✅ Complete | 10 Vitest tests, custom ledger design tokens, live countdown, 2 views, bid form |
| **P1** | **High-Level Design (HLD)** | ✅ Complete | [docs/HLD.md](docs/HLD.md), [docs/SCHEMA.md](docs/SCHEMA.md), [docs/API_CONTRACT.md](docs/API_CONTRACT.md) |
| **P2** | **Celery Lifecycle Sweeper & Recovery** | ✅ Complete | Sweeps every 1s; self-healing crash recovery tested with `is_recovered` audit flag |
| **P2** | **Idempotency Guarantee** | ✅ Complete | SHA-256 payload canonicalization, unique constraint, replay without re-validation |
| **P2** | **Docker Compose & Makefile** | ✅ Complete | 6-container setup, healthchecks, auto-seed with `--live` flag |
| **P3** | **Evaluator Demo Scripts & Documentation** | ✅ Complete | `scripts/simulate_bidding.py`, interactive walkthrough guide, scalability analysis |

---

## 3. Evaluator Live Demo Walkthrough

The demo seed populates realistic freight carriers (`Maersk`, `DHL`, `Blue Dart`, `DB Schenker`, `FedEx`) and auctions across every lifecycle state:
- `RFQ-2026-SCHED`: **Scheduled** (opens in 30 minutes)
- `RFQ-2026-ACTIVE`: **Active** (regular bidding, outside trigger window)
- `RFQ-2026-LIVE`: **Trigger Window Active** (closing in ~4 minutes, ready for anti-sniping demonstration)
- `RFQ-2026-CLOSED`: **Closed** (concluded with final L1 winning quote)
- `RFQ-2026-FORCE-CLOSED`: **Force Closed** (repeatedly extended until hitting the hard cap)

### Step 1: Open the Trading Desk UI
Navigate to [http://localhost:5173](http://localhost:5173).
Notice:
1. **Live Server Clock:** Top right header displays synchronized server UTC time with a heartbeat indicator.
2. **Auction Cards:** Displays live countdowns, current L1 lowest prices, and anti-sniping status badges.

### Step 2: Live Anti-Sniping Extension in Browser
Click on `★ LIVE DEMO: Chennai to Rotterdam Express (RFQ-2026-LIVE)`.
1. Look at the countdown: It displays an amber **"Trigger Window"** badge with a pulsing timer.
2. Check the **Supplier Ranking Tab**: One row per invited carrier. Shows rank, total price, and muted "No bid submitted yet" rows for carriers without quotes.
3. Submit a quote via the **Submit Carrier Quote** form:
   - Select a carrier (e.g. `DB Schenker India`)
   - Notice the form highlights that carrier's previous best quote and warns in real-time if a quote is not strictly lower.
   - Enter a freight charge that lowers the total price below current L1 (e.g. `82600.00`).
   - Click **Submit Binding Quote**.
4. **Observe the Immediate Anti-Sniping Reaction:**
   - Close time extends by **+5 minutes** instantly!
   - Activity log writes a `TIME_EXTENDED` event with a human-readable explanation:
     `"L1 changed from DHL Global Forwarding to DB Schenker India at 07:51 PM, inside the last 5 min window. Close moved 07:51 PM → 07:56 PM."`
   - Extension counter updates, and price improvement metric increases.

### Step 3: Anti-Sniping CLI Simulation & Idempotency Replay
Run the automated CLI simulator in your terminal:
```bash
python scripts/simulate_bidding.py
```
**Sample Terminal Output:**
```text
[*] Found RFQ: ★ LIVE DEMO: Chennai to Rotterdam Express (RFQ-2026-LIVE)
    Status: ACTIVE
    Current Close Time: 2026-11-13T19:56:01.058953
    Forced Close Time:  2026-11-13T20:12:01.058953
    Current Lowest Quote: INR 83600.00

[*] Submitting new competitive bid from 'Blue Dart Express':
    Freight:     INR 78420.00
    Origin:      INR 500.00
    Destination: INR 500.00
    Total Price: INR 79420.00 (Strictly lower)
    Idempotency-Key: 5bf3059f-c061-469f-be0e-704ff4ca9af5

[✓] Bid accepted successfully! Bid ID: b15ae89a-b617-4bb3-b9b1-d0c2679e1394
    New Supplier Rank: #1
    New Current Close Time: 2026-11-13T20:01:01.058953+00:00

    ⚡ ANTI-SNIPING EXTENSION TRIGGERED!
    Reason: L1 changed from DB Schenker India to Blue Dart Express inside the last 5 min window. Close moved 07:56 PM → 08:01 PM.

[*] Demonstrating Idempotency: Retrying with identical key...
[✓] Idempotent Replay Verified: was_replayed=True, Bid ID unchanged=b15ae89a-b617-4bb3-b9b1-d0c2679e1394
```

---

## 4. System Architecture & Core Concepts

```
                        ┌─────────────────────────────────────────┐
                        │          React 18 Trading Desk          │
                        │ (TanStack Query, Zod, Custom Tokens)   │
                        └───────────────────┬─────────────────────┘
                                            │ REST /api/v1
                                            ▼
                        ┌─────────────────────────────────────────┐
                        │          FastAPI Backend Engine         │
                        │  • Clock Injection (System / Fake)      │
                        │  • 13-Step Transactional Bid Service    │
                        │  • Strict State Machine (4 States)      │
                        │  • SHA-256 Idempotency Engine           │
                        └─────────────┬───────────────────────────┘
                                      │
              ┌───────────────────────┴──────────────────────────┐
              ▼                                                  ▼
┌───────────────────────────┐                      ┌───────────────────────────┐
│     PostgreSQL 15 DB      │                      │      Redis 7 Broker       │
│ • Single Source of Truth  │                      │ (Celery Queue Only)       │
│ • Row-level Locks         │                      └─────────────┬─────────────┘
│ • CHECK Constraints       │                                    │
│ • Immutable Audit Events  │                                    ▼
└───────────────────────────┘                      ┌───────────────────────────┐
                                                   │    Celery Worker & Beat   │
                                                   │ • 1s Background Sweeper   │
                                                   │ • Self-healing Recovery   │
                                                   └───────────────────────────┘
```

### 4.1 British Reverse Auction State Machine

```
              ┌─────────────┐
              │  SCHEDULED  │
              └──────┬──────┘
                     │ (now >= bid_start_time)
                     ▼
              ┌─────────────┐  Bidding in [T_close - X, T_close)
              │   ACTIVE    │ ◄─────────────────────────────────┐
              └──────┬──────┘  extends close: min(T + Y, T_cap) │
                     │                                          │
       ┌─────────────┴────────────────────────┐                 │
       │                                      │                 │
       │ (now >= current_close                │ (now >= close   │
       │  AND current_close < forced_close)   │  AND close ==   │
       ▼                                      │      forced)    │
┌─────────────┐                               ▼                 │
│   CLOSED    │                        ┌──────────────┐         │
│  (Terminal) │                        │ FORCE_CLOSED │         │
└─────────────┘                        │  (Terminal)  │         │
                                       └──────────────┘         │
                                              ▲                 │
                                              └─────────────────┘
```

### 4.2 Anti-Sniping Extension Trigger Policies
1. **`BID_IN_LAST_X`**: Any valid bid placed within the last $X$ minutes extends the auction by $Y$ minutes.
2. **`ANY_RANK_CHANGE_IN_LAST_X`**: Extends if any carrier shifts position in the supplier ranking table.
3. **`L1_CHANGE_IN_LAST_X`**: Extends only if the lowest bidder (L1 leader) changes.
4. **Hard Forced Cap**: Under no circumstance can `current_close_time` ever exceed `forced_close_time`:
   $$\text{new\_close\_time} = \min(\text{current\_close\_time} + Y, \text{forced\_close\_time})$$

---

## 5. Verification & Testing

Every single test executes against an isolated database with an injected `FakeClock`, producing 100% deterministic results in under 1 second.

### Run All Backend Tests
```bash
$env:PYTHONPATH="backend"
pytest backend/tests
```
**Output:**
```text
backend\tests\test_acceptance_scenario.py .                              [  1%]
backend\tests\test_api.py ....                                           [  9%]
backend\tests\test_auction_engine.py ........................            [ 53%]
backend\tests\test_clock.py ..                                           [ 57%]
backend\tests\test_concurrency.py .                                      [ 59%]
backend\tests\test_db_constraints.py ......                              [ 70%]
backend\tests\test_idempotency.py .                                      [ 72%]
backend\tests\test_lifecycle_recovery.py ....                            [ 79%]
backend\tests\test_state_machine.py ...........                          [100%]

======================= 54 passed, 2 warnings in 0.51s ========================
```

### Run Frontend Tests & Lint
```bash
cd frontend
pnpm test
pnpm lint
pnpm build
```
**Output:**
```text
 ✓ src/test/Components.test.tsx (10 tests) 151ms
 Test Files  1 passed (1)
      Tests  10 passed (10)
$ tsc --noEmit (0 errors)
✓ built in 1.63s
```

### Run Backend Lint
```bash
ruff check backend/
```
**Output:**
```text
All checks passed!
```

---

## 6. Assumptions & Decisions Log

| # | Decision | Architectural Rationale |
|---|----------|-------------------------|
| 1 | **Optional Idempotency-Key in API, Mandatory in Frontend** | Maximizes Swagger/curl testing ergonomics while guaranteeing zero double-quote submissions in the web UI. Requests without a key are explicitly documented as lacking retry safety. |
| 2 | **Monetary values serialized as Strings (e.g. `"9500.00"`), DB stored as `NUMERIC(14,2)`** | Completely eliminates IEEE-754 floating-point rounding errors across financial freight balances. Python `float` is strictly prohibited. |
| 3 | **Rank ties broken by `(submitted_at ASC, bid_id ASC)`** | First-mover advantage: The supplier who dared to quote the low price earlier retains ranking preference. |
| 4 | **`in_trigger_window` left-bound is inclusive: $[T_c - X, T_c)$** | A bid placed exactly at the trigger window boundary activates the anti-sniping extension, maximizing supplier fairness. |
| 5 | **First quote from an unquoted supplier triggers L1 change if it beats current L1** | Transition from "no leader" to a designated carrier is an active rank change. |
| 6 | **Extension added to `current_close_time`, not `now`** | Preserves predictable increments ($T_c \to T_c + Y$) and prevents trigger window compression when network latency delays bid ingestion. |
| 7 | **Real-time Status Calculation via SQL `CASE` Expressions** | The API never relies on a stale status column; status is always computed relative to the authoritative server clock, guaranteeing correctness even if background workers stall. |
| 8 | **Redis is Strictly a Celery Message Broker** | PostgreSQL remains the sole source of truth. No application state, bid caches, or volatile counters exist in Redis. |
| 9 | **No Authentication (Open Visibility Trading Desk)** | Per assignment scope, role-based login is omitted. Visibility is modeled as an open trading desk where all quotes, rankings, and audit events are transparent. |
| 10 | **Carrier Name Integrity via Snapshotting** | The bid submission API accepts only `supplier_id`. The carrier's name is derived directly from the verified supplier database record and stored as a historical snapshot on the quote. |
| 11 | **Cascading Deletes Blocked for Historical Integrity** | Foreign key constraints on bids and events utilize `ON DELETE RESTRICT`, preventing accidental data deletion of historical auction audit trails. |
| 12 | **Pure Clock Dependency Injection** | All timestamps (`submitted_at`, `occurred_at`, `created_at`) are injected via the `Clock` interface (`SystemClock` in production, `FakeClock` in tests). DB `NOW()` is only an unread fallback. |
| 13 | **Single Configuration Invariant for British Auctions** | Enforced at the database level via a shared primary key `rfq_id` on `british_auction_configs` (1:1 relationship) and at the application layer with Pydantic validators. |
| 14 | **Self-Healing Sweeper Recovery (`is_recovered = true`)** | If the Celery daemon is stopped and later restored, the sweeper processes all missed auction transitions and writes audit events flagged with `is_recovered = true`. |

---

## 7. Scalability & Future Work

1. **Role-Based Access Control (RBAC):**
   - Buyer view: Full bid history, carrier identity, profit margins.
   - Carrier view: Anonymized competitor rankings (e.g. "Rank #2 - Best quote is ₹9,200.00"), hiding competitor carrier names until award.
2. **WebSocket / SSE Live Streaming:**
   - TanStack Query 3-second polling provides robust, resilient zero-config updates. A production deployment with 1,000+ concurrent suppliers would benefit from Server-Sent Events (SSE) or Redis Pub/Sub WebSockets for sub-second quote broadcasts.
3. **Carrier Route Graph (Neo4j / Graph Extension):**
   - Model carrier lane capacity, origin/destination hubs, transshipment ports, and transit time reliability scores for multi-leg freight allocation.
