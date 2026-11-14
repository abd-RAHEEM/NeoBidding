# NeoBidding: British Auction RFQ System

> **Full-Stack British Reverse Auction engine for enterprise procurement and carrier freight bidding.**  
> **Developed by [Abdul Raheem](https://github.com/abd-RAHEEM)**

[![Backend Tests](https://img.shields.io/badge/backend%20tests-54%20passed-0B6E4F?style=for-the-badge&logo=pytest)](backend/tests/)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-15%20passed-0B6E4F?style=for-the-badge&logo=vitest)](frontend/src/test/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](frontend/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](frontend/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white)](frontend/tailwind.config.js)
[![PostgreSQL](https://img.shields.io/badge/Neon_Postgres-Serverless-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech)
[![Redis](https://img.shields.io/badge/Upstash_Redis-TLS_Broker-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://upstash.com)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)

---

## 📸 Interactive UI Gallery

Click each dropdown below to preview the platform interface:

<details open>
<summary><b>1. Auctions Ledger & Live Trading Desk</b></summary>
<br>

Real-time visibility into active, scheduled, and closed procurement auctions. Features multi-criteria search, status filtering, countdown clocks synchronized to server time, and current lowest bid leaders.

![Auctions Ledger](docs/screenshots/01_auctions_ledger.png)
</details>

<details>
<summary><b>2. Create RFQ & British Auction Configurator</b></summary>
<br>

Comprehensive auction creation workflow with configurable starting price (reserve ceiling), bid step decrement, anti-sniping trigger window duration, dynamic extension length, and carrier invitation lists.

![Create RFQ](docs/screenshots/02_create_rfq.png)
</details>

<details>
<summary><b>3. Live Auction Bidding Desk, Rankings & Audit Trail</b></summary>
<br>

Real-time trading desk providing synchronized server clocks, live countdown timers with trigger window visual indicators, three-tier cost component quote inputs (freight, origin, destination), ranked supplier leaderboards (L1, L2, L3), and immutable chronological audit event logs.

![Auction Bidding Desk](docs/screenshots/03_auction_bidding.png)
</details>

---

## 🏛️ System Architecture

NeoBidding is architected as an event-driven, decoupled system adhering to strict ACID transactional boundaries:

```
                          ┌─────────────────────────────────────┐
                          │     React 18 + Vite Trading Desk    │
                          │   (TanStack Query + Tailwind CSS)   │
                          └──────────────────┬──────────────────┘
                                             │ HTTP / REST
                                             ▼
                          ┌─────────────────────────────────────┐
                          │          FastAPI Gateway            │
                          │   Pydantic v2 · SQLAlchemy 2.0      │
                          └──────┬───────────────────────┬──────┘
                                 │                       │
      Pessimistic Row Lock (ACID)│                       │ Asynchronous Tasks
        SELECT ... FOR UPDATE    │                       │ (Enqueued via TLS)
                                 ▼                       ▼
      ┌───────────────────────────────────┐    ┌──────────────────────────────────┐
      │     Neon Serverless PostgreSQL    │    │      Upstash Serverless Redis    │
      │  Single Source of Truth (State)   │    │      Celery Message Broker       │
      │   - RFQs & BritishAuctionConfigs  │    │      TLS (rediss://) Protocol    │
      │   - Impartial Audit Log & Events  │    └─────────────────┬────────────────┘
      │   - Suppliers & Costed Bids       │                      │
      └───────────────────────────────────┘                      │ Task Consumption
                                                                 ▼
                                               ┌──────────────────────────────────┐
                                               │      Celery Worker & Beat        │
                                               │   - Scheduled Lifecycle Sweeper  │
                                               │   - Auto-Close Due Auctions      │
                                               │   - Anti-Sniping Timer Auditor   │
                                               └──────────────────────────────────┘
```

---

## 🧠 Core Engineering Concepts & Invariants

### 1. British Reverse Auction Mechanism
Unlike forward auctions (where prices ascend to the highest bidder), procurement uses **reverse auctions** where buyers post Request For Quotes (RFQs) and pre-qualified suppliers submit descending quotes:
- **Total Landed Cost Formula:** $\text{Total} = \text{Freight Charges} + \text{Origin Charges} + \text{Destination Charges}$.
- **Monotonic Decrement:** Each carrier's subsequent bid must strictly improve upon either their own prior quote or beat the market reserve ceiling by at least the configured minimum decrement step:
  $$\text{Bid}_{\text{new}} \le \min(\text{Bid}_{\text{prior}}, \text{Reserve Ceiling}) - \Delta_{\text{step}}$$
- **Leading Rank (L1):** The carrier offering the lowest verified landed cost holds Rank #1. Ties are broken chronologically based on monotonic submission timestamps ($\text{timestamp}_{\text{earlier}} < \text{timestamp}_{\text{later}}$).

### 2. Algorithmic Anti-Sniping Dynamic Extension Engine
"Sniping" is an adversarial auction strategy where bidders withhold submissions until the final seconds to prevent competitors from counter-bidding. NeoBidding neutralizes this via an automated dynamic extension engine:
- **Trigger Window:** A sliding interval $[T_{\text{close}} - \omega, T_{\text{close}}]$ where $\omega$ is the configured trigger window (e.g. 5 minutes).
- **Extension Trigger Rule:**
  - `ANY_BID`: Any valid bid submitted inside the trigger window triggers an extension.
  - `LEAD_CHANGE_ONLY`: An extension is only triggered if the incoming quote captures the Rank #1 (L1) leading position.
- **Dynamic Clock Adjustment:**
  $$T_{\text{close, new}} = \max(T_{\text{close, current}}, T_{\text{bid}} + \Delta_{\text{extension}})$$
- **Halting Problem Prevention (Forced Close Cap):** To guarantee auctions cannot extend indefinitely, a hard cap is enforced:
  $$T_{\text{close, new}} \le T_{\text{open}} + \Delta_{\text{max\_extension\_duration}}$$

### 3. 13-Step Transactional State Machine (`SELECT ... FOR UPDATE`)
Every bid submission is processed through an atomic 13-step pipeline protected by PostgreSQL row-level pessimistic locking:

```mermaid
stateDiagram-v2
    [*] --> IdempotencyCheck: 1. Idempotency Key Lookup
    IdempotencyCheck --> AcquirePessimisticLock: Replay Found ? Return Cached : Proceed
    AcquirePessimisticLock --> ValidateStatus: 2. SELECT ... FOR UPDATE (RFQ Row)
    ValidateStatus --> ValidateTemporalWindow: 3. Is RFQ in ACTIVE status?
    ValidateTemporalWindow --> VerifySupplierInvitation: 4. Check Server Clock vs [Open, Close]
    VerifySupplierInvitation --> CalculateLandedCost: 5. Verify Supplier in Invited Whitelist
    CalculateLandedCost --> VerifyMonotonicDecrement: 6. Sum (Freight + Origin + Dest)
    VerifyMonotonicDecrement --> RecalculateRankings: 7. Validate step <= ceiling & prior
    RecalculateRankings --> EvaluateTriggerWindow: 8. Compute new supplier ranking (L1..LN)
    EvaluateTriggerWindow --> ApplyDynamicExtension: 9. Is bid time within [Close - Window, Close]?
    ApplyDynamicExtension --> RecordAuditEvent: 10. Adjust close_time & emit extension event
    RecordAuditEvent --> PersistBidRecord: 11. Write immutable AuctionEvent ledger
    PersistBidRecord --> CommitTransaction: 12. Insert Bid entity into PostgreSQL
    CommitTransaction --> [*]: 13. Release Lock & Return BidResponse
```

### 4. Concurrency & High-Contention Race Condition Guarding
When multiple suppliers submit quotes in the same millisecond:
- **Database Row Locks:** The active RFQ record is locked with `with_for_update()`. Parallel incoming requests for the same RFQ queue deterministically at the database engine level.
- **Zero In-Memory Drift:** State is never held in ephemeral server memory or worker caches. The single source of truth is always the relational PostgreSQL database.
- **Financial Precision:** Currency arithmetic is executed strictly using Python `Decimal` and PostgreSQL `NUMERIC(14,2)` columns, eliminating IEEE 754 floating-point inaccuracies.

### 5. Architectural Separation: State vs Broker
- **Neon PostgreSQL:** Acts as the sole authoritative repository for all domain models (`RFQ`, `BritishAuctionConfig`, `Bid`, `Supplier`, `AuctionEvent`, `IdempotencyRecord`).
- **Upstash Redis:** Strictly utilized as the high-speed, TLS-secured Celery message broker (`rediss://`). No domain state resides in Redis, keeping the architecture purely relational and failure-resilient.

---

## 🛠️ Tech Stack & Infrastructure

| Tier | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React 18, Vite 6, TypeScript 5.5 | High-speed trading desk UI with zero build-time overhead |
| **State & Data Fetching** | TanStack Query v5 | Automated background cache invalidation and 3s polling |
| **Styling** | Tailwind CSS 3.4 | Financial terminal aesthetic with custom design tokens |
| **API Server** | FastAPI 0.115, Starlette, Pydantic v2 | High-throughput async REST endpoints with OpenAPI schema |
| **ORM & Migrations** | SQLAlchemy 2.0, Alembic | Type-safe query building with transactional migrations |
| **Database** | Neon Serverless PostgreSQL | Cloud-native Postgres with connection pooling and SSL |
| **Task Queue & Broker** | Celery 5.4, Upstash Redis | Asynchronous background lifecycle workers over TLS |
| **Testing** | Pytest, AnyIO, Vitest, Testing Library | End-to-end integration and unit validation suites |

---

## 🚀 Local Development Setup

### Prerequisites
- **Python 3.12+**
- **Node.js 18+** & **npm**

### 1. Environment Configuration

#### Backend (`backend/.env`):
Create `backend/.env` (or copy from `backend/.env.example`):
```env
# Neon Serverless PostgreSQL Connection String
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-dawn-mountain-b36rpodf-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require

# Upstash TLS-Enabled Redis Broker
REDIS_URL=rediss://default:YOUR_PASSWORD@evident-stork-25760.upstash.io:6379

# Allowed CORS Origins
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

#### Frontend (`frontend/.env`):
Create `frontend/.env` (or copy from `frontend/.env.example`):
```env
# API Base URL (leave empty for local dev to use Vite proxy)
VITE_API_BASE_URL=
```

---

### 2. Pre-Flight Connection Verification
Safely test connectivity to both Neon PostgreSQL and Upstash Redis before starting services:

```powershell
python scripts/test_connections.py
```

Expected output:
```
[+] Neon PostgreSQL Connection: SUCCESSFUL
    PostgreSQL Version: PostgreSQL 17.5 on x86_64-pc-linux-gnu
[+] Upstash Redis Connection: SUCCESSFUL
    Ping Response: True
    Upstash Redis Version: 7.2.14
```

---

### 3. Database Migration & Live Data Seeding

```powershell
# Run Alembic schema migrations
alembic -c backend/alembic.ini upgrade head

# Seed carriers and live auction scenarios
$env:PYTHONPATH="backend"
python scripts/seed.py --live
```

---

### 4. Running the Application Services

Open four terminal windows (or tabs) to run the full distributed platform:

#### Terminal 1 — FastAPI Backend Service:
```powershell
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
*API Docs available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)*

#### Terminal 2 — Celery Background Worker:
```powershell
$env:PYTHONPATH="backend"
celery -A app.core.celery_app.celery_app worker --loglevel=info --pool=solo
```

#### Terminal 3 — Celery Beat Lifecycle Scheduler:
```powershell
$env:PYTHONPATH="backend"
$env:CELERY_BEAT_SCHEDULE_PATH="celerybeat-schedule"
celery -A app.core.celery_app.celery_app beat --loglevel=info -s celerybeat-schedule
```

#### Terminal 4 — React Frontend Trading Desk:
```powershell
npm run dev --prefix frontend
```
*Trading Desk accessible at: [http://localhost:5173](http://localhost:5173)*

---

## 🧪 Automated Testing Suites

Both backend and frontend feature comprehensive test suites validating business invariants:

### Backend Test Matrix (Pytest — 54 Passed)
```powershell
$env:PYTHONPATH="backend"
pytest backend/tests -v
```
- `test_acceptance_scenario.py`: Full end-to-end multi-carrier reverse auction simulation.
- `test_auction_engine.py`: Dynamic anti-sniping trigger calculation, lead change extension rules.
- `test_concurrency.py`: High-concurrency sub-second simultaneous bid submissions.
- `test_db_constraints.py`: Strict database check constraints and foreign key integrity.
- `test_idempotency.py`: Distributed idempotency key collision and replay verification.
- `test_state_machine.py`: Complete 13-step auction lifecycle transitions (`DRAFT` $\to$ `OPEN` $\to$ `ACTIVE` $\to$ `CLOSED`).

### Frontend Test Matrix (Vitest — 15 Passed)
```powershell
npm run test --prefix frontend
```
- Component unit tests: `Countdown`, `Badge`, `Currency`, `StatsStrip`, `BidForm`, `SupplierRankingTab`.
- Page interaction tests: Auction filtering, carrier selection, real-time error boundary recovery.

### Production Build Validation
```powershell
npm run build --prefix frontend
```

---

## 👨‍💻 Author & Attribution

**Developed by Abdul Raheem**  
- **GitHub:** [@abd-RAHEEM](https://github.com/abd-RAHEEM)  
- **Repository:** [https://github.com/abd-RAHEEM/NeoBidding](https://github.com/abd-RAHEEM/NeoBidding)  

---

