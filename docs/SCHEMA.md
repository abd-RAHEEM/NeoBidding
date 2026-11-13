# Database Schema Reference

> Version 0.2 · Phase 0 (rev 1) · 2026-11-14  
> Database: PostgreSQL 15  
> All monetary columns: `NUMERIC(14,2)`  
> All timestamps: `TIMESTAMP WITH TIME ZONE` (UTC)

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    suppliers {
        uuid id PK
        varchar name UK
        timestamptz created_at
    }

    rfqs {
        uuid id PK
        varchar reference_id UK
        varchar name
        char3 currency
        date pickup_date
        enum auction_type
        timestamptz bid_start_time
        timestamptz original_close_time
        timestamptz current_close_time
        timestamptz forced_close_time
        enum status
        timestamptz created_at
    }

    rfq_suppliers {
        uuid id PK
        uuid rfq_id FK
        uuid supplier_id FK
        timestamptz invited_at
    }

    british_auction_configs {
        uuid rfq_id PK_FK
        int trigger_window_minutes
        int extension_minutes
        enum extension_trigger
    }

    bids {
        uuid id PK
        uuid rfq_id FK
        uuid supplier_id FK
        varchar carrier_name_snapshot
        numeric freight_charges
        numeric origin_charges
        numeric destination_charges
        numeric total_price
        int transit_time_days
        int quote_validity_days
        timestamptz submitted_at
        varchar64 idempotency_key
        char64 request_hash
        jsonb result_snapshot
    }

    auction_events {
        uuid id PK
        uuid rfq_id FK
        enum event_type
        uuid bid_id FK
        jsonb payload
        text reason
        timestamptz occurred_at
        timestamptz created_at
        bool is_recovered
    }

    rfqs ||--o{ rfq_suppliers : "invites"
    suppliers ||--o{ rfq_suppliers : "is invited to"
    rfqs ||--o| british_auction_configs : "has config"
    rfqs ||--o{ bids : "receives"
    suppliers ||--o{ bids : "submits"
    rfqs ||--o{ auction_events : "generates"
    bids ||--o{ auction_events : "referenced by"
```

---

## Table Definitions

### `suppliers`

Master list of freight carriers/suppliers.

> **No hard-delete endpoint is exposed.** A supplier cannot be deleted if it has submitted any bids (`bids.supplier_id` FK is `ON DELETE RESTRICT`). This preserves historical bid integrity.

```sql
CREATE TABLE suppliers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK, generated |
| `name` | VARCHAR(255) | Unique display name |
| `created_at` | TIMESTAMPTZ | Row creation time (UTC); set by the application via `clock.now()` |

---

### `rfqs`

Core auction entity. `status` is a **cached derived value** — the authoritative state is always computed from timestamps by `derive_status()`.

> **No hard-delete endpoint is exposed.** An RFQ cannot be deleted once it has associated bids or auction events (`bids.rfq_id` and `auction_events.rfq_id` FKs are `ON DELETE RESTRICT`). Config and invitation rows (`british_auction_configs`, `rfq_suppliers`) cascade-delete if an RFQ row is ever removed by an administrator directly in the DB, since they carry no independent historical value.

```sql
CREATE TYPE auction_type_enum AS ENUM ('STANDARD', 'BRITISH');
CREATE TYPE auction_status_enum AS ENUM ('SCHEDULED', 'ACTIVE', 'CLOSED', 'FORCE_CLOSED');

CREATE TABLE rfqs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_id         VARCHAR(64) NOT NULL UNIQUE,
    name                 VARCHAR(255) NOT NULL,
    currency             CHAR(3) NOT NULL DEFAULT 'INR',
    pickup_date          DATE,
    auction_type         auction_type_enum NOT NULL DEFAULT 'STANDARD',
    bid_start_time       TIMESTAMPTZ NOT NULL,
    original_close_time  TIMESTAMPTZ NOT NULL,
    current_close_time   TIMESTAMPTZ NOT NULL,
    forced_close_time    TIMESTAMPTZ NOT NULL,
    status               auction_status_enum NOT NULL DEFAULT 'SCHEDULED',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_forced_after_original
        CHECK (forced_close_time > original_close_time),
    CONSTRAINT chk_original_after_start
        CHECK (original_close_time > bid_start_time),
    CONSTRAINT chk_current_in_bounds
        CHECK (current_close_time >= original_close_time
               AND current_close_time <= forced_close_time),
    CONSTRAINT chk_currency_valid
        CHECK (currency IN ('INR','USD','EUR','GBP','AED'))
);
```

| Column                | Type         | Constraint      | Notes                                      |
| --------------------- | ------------ | --------------- | ------------------------------------------ |
| `id`                  | UUID         | PK              | Generated                                  |
| `reference_id`        | VARCHAR(64)  | UNIQUE NOT NULL | Buyer-facing ID                            |
| `name`                | VARCHAR(255) | NOT NULL        | Display name                               |
| `currency`            | CHAR(3)      | CHECK IN (...)  | Default `INR`                              |
| `pickup_date`         | DATE         | nullable        | Service/pickup date                        |
| `auction_type`        | ENUM         | NOT NULL        | `STANDARD` or `BRITISH`                    |
| `bid_start_time`      | TIMESTAMPTZ  | NOT NULL        | When bidding opens                         |
| `original_close_time` | TIMESTAMPTZ  | NOT NULL        | Scheduled close (immutable after creation) |
| `current_close_time`  | TIMESTAMPTZ  | CHECK bounds    | Advances on each extension                 |
| `forced_close_time`   | TIMESTAMPTZ  | NOT NULL        | Hard stop; `> original_close_time`         |
| `status`              | ENUM         | NOT NULL        | Cache only; derived by `derive_status()`   |
| `created_at`          | TIMESTAMPTZ  | NOT NULL        | Set by application via `clock.now()`; DB `DEFAULT NOW()` is a fallback only |

**CHECK constraints:**

- `forced_close_time > original_close_time`
- `original_close_time > bid_start_time`
- `original_close_time <= current_close_time <= forced_close_time`
- `currency IN ('INR','USD','EUR','GBP','AED')`

---

### `rfq_suppliers`

Many-to-many join: which suppliers are invited to each RFQ. This is **configuration data**, not historical data — it has no independent value if the RFQ is gone.

```sql
CREATE TABLE rfq_suppliers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id      UUID NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    invited_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (rfq_id, supplier_id)
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `rfq_id` | UUID | FK → rfqs (`ON DELETE CASCADE`; invitation has no meaning without the RFQ) |
| `supplier_id` | UUID | FK → suppliers (`ON DELETE RESTRICT`; a supplier that has been invited cannot be deleted while the invitation exists) |
| `invited_at` | TIMESTAMPTZ | Set by application via `clock.now()`; DB `DEFAULT NOW()` is a fallback only |

**Constraint:** `UNIQUE(rfq_id, supplier_id)` — a supplier may be invited only once per RFQ.

---

### `british_auction_configs`

Extension configuration; exists **if and only if** `auction_type = 'BRITISH'`.

#### Enforcement of the BRITISH ↔ config invariant

The database enforces *at most one* config per RFQ via the PK (`rfq_id` is both PK and FK). The *exactly one for BRITISH* requirement and *none for STANDARD* requirement are enforced at the **application layer** (`bid_service.py` and the RFQ creation route), which are the only code paths that create `rfqs` rows and `british_auction_configs` rows:

| `auction_type` | Application rule | DB side-effect |
|---|---|---|
| `BRITISH` | `british_config` field required; creation fails with 422 if absent | Row inserted into `british_auction_configs` |
| `STANDARD` | `british_config` must be absent or null; creation fails with 422 if present | No row in `british_auction_configs` |

> **Why not a DB constraint?** A pure-SQL enforcement (e.g. a trigger or a generated column) would require a trigger or a deferrable FK, both of which add complexity for a constraint that is already 100% enforced at the API boundary (Pydantic schema + route logic) and tested by integration tests. The PK already makes over-insertion impossible; the application layer prevents under-insertion.

```sql
CREATE TYPE extension_trigger_enum AS ENUM (
    'BID_IN_LAST_X',
    'ANY_RANK_CHANGE_IN_LAST_X',
    'L1_CHANGE_IN_LAST_X'
);

CREATE TABLE british_auction_configs (
    rfq_id                  UUID PRIMARY KEY REFERENCES rfqs(id) ON DELETE CASCADE,
    trigger_window_minutes  INTEGER NOT NULL,
    extension_minutes       INTEGER NOT NULL,
    extension_trigger       extension_trigger_enum NOT NULL,

    CONSTRAINT chk_trigger_window_positive CHECK (trigger_window_minutes >= 1),
    CONSTRAINT chk_extension_positive      CHECK (extension_minutes >= 1)
);
```

| Column | Type | Constraint | Notes |
|--------|------|------------|-------|
| `rfq_id` | UUID | PK / FK → rfqs (`ON DELETE CASCADE`; config has no meaning without the RFQ) | One config per RFQ |
| `trigger_window_minutes` | INTEGER | CHECK ≥ 1 | `X` in the spec |
| `extension_minutes` | INTEGER | CHECK ≥ 1 | `Y` in the spec |
| `extension_trigger` | ENUM | NOT NULL | Which event triggers extension |

---

### `bids`

Append-only quote submissions. Each row is one supplier quote. **Bids are historical records and must never be silently deleted.**

#### `carrier_name` derivation

`carrier_name` is **not accepted from the client**. When a bid is submitted, the application looks up `suppliers.name` using the authenticated `supplier_id` and stores that name as a snapshot at the time of submission. This prevents suppliers from submitting bids under a false identity and ensures the historical record is consistent even if the supplier's name is later updated in the master table.

```sql
CREATE TABLE bids (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id               UUID NOT NULL REFERENCES rfqs(id) ON DELETE RESTRICT,
    supplier_id          UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    carrier_name         VARCHAR(255) NOT NULL,
    freight_charges      NUMERIC(14,2) NOT NULL,
    origin_charges       NUMERIC(14,2) NOT NULL,
    destination_charges  NUMERIC(14,2) NOT NULL,
    total_price          NUMERIC(14,2) NOT NULL,
    transit_time_days    INTEGER NOT NULL,
    quote_validity_days  INTEGER NOT NULL,
    submitted_at         TIMESTAMPTZ NOT NULL,
    idempotency_key      VARCHAR(64),
    request_hash         CHAR(64),
    result_snapshot      JSONB,

    CONSTRAINT chk_freight_nonneg      CHECK (freight_charges >= 0),
    CONSTRAINT chk_origin_nonneg       CHECK (origin_charges >= 0),
    CONSTRAINT chk_destination_nonneg  CHECK (destination_charges >= 0),
    CONSTRAINT chk_total_positive      CHECK (total_price > 0),
    CONSTRAINT chk_total_sum           CHECK (
        total_price = freight_charges + origin_charges + destination_charges
    ),
    CONSTRAINT chk_transit_positive    CHECK (transit_time_days >= 1),
    CONSTRAINT chk_validity_positive   CHECK (quote_validity_days >= 1),
    UNIQUE (rfq_id, supplier_id, idempotency_key)
);
```

> **`submitted_at` has no `DEFAULT NOW()`** — it must be supplied explicitly by the application using `clock.now()`. This keeps the application clock (injectable `FakeClock` in tests) as the single source of `submitted_at` and prevents the DB clock from silently diverging in test scenarios.

| Column | Type | Constraint | Notes |
|--------|------|------------|-------|
| `id` | UUID | PK | Generated |
| `rfq_id` | UUID | FK → rfqs (`ON DELETE RESTRICT`) | Prevents silent deletion of historical auction data |
| `supplier_id` | UUID | FK → suppliers (`ON DELETE RESTRICT`) | Preserves historical supplier identity |
| `carrier_name` | VARCHAR(255) | NOT NULL | **Snapshot** derived from `suppliers.name` at submission time; **not client-supplied** |
| `freight_charges` | NUMERIC(14,2) | CHECK ≥ 0 | Main freight cost |
| `origin_charges` | NUMERIC(14,2) | CHECK ≥ 0 | Origin port charges |
| `destination_charges` | NUMERIC(14,2) | CHECK ≥ 0 | Destination port charges |
| `total_price` | NUMERIC(14,2) | CHECK > 0, CHECK = sum | Computed server-side from the three charge columns |
| `transit_time_days` | INTEGER | CHECK ≥ 1 | Estimated days |
| `quote_validity_days` | INTEGER | CHECK ≥ 1 | Days quote is valid |
| `submitted_at` | TIMESTAMPTZ | NOT NULL (no DB default) | Set by application via `clock.now()`; not DB-generated |
| `idempotency_key` | VARCHAR(64) | nullable; UNIQUE(rfq,supplier,key) | Client-provided UUID; `NULL` rows not constrained (NULL ≠ NULL in SQL) |
| `request_hash` | CHAR(64) | nullable | SHA-256 of canonical payload |
| `result_snapshot` | JSONB | nullable | Stored response for idempotency replay |

**Note on UNIQUE constraint:** `UNIQUE(rfq_id, supplier_id, idempotency_key)` — in PostgreSQL, `NULL` values are not considered equal, so rows without an idempotency key are unconstrained (allowing multiple null-key bids from the same supplier to the same RFQ, which is correct for curl/Swagger testing). **This UNIQUE constraint also creates the backing B-tree index; no separate index on these columns is needed.**

---

### `auction_events`

Append-only audit log. Ordered by `(occurred_at, id)` for chronological display. **Audit events must never be silently deleted; they are the permanent record of what happened.**

```sql
CREATE TYPE auction_event_type_enum AS ENUM (
    'AUCTION_CREATED',
    'AUCTION_STARTED',
    'BID_PLACED',
    'TIME_EXTENDED',
    'EXTENSION_SKIPPED_AT_FORCED_CLOSE',
    'AUCTION_CLOSED',
    'AUCTION_FORCE_CLOSED'
);

CREATE TABLE auction_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id       UUID NOT NULL REFERENCES rfqs(id) ON DELETE RESTRICT,
    event_type   auction_event_type_enum NOT NULL,
    bid_id       UUID REFERENCES bids(id) ON DELETE RESTRICT,
    payload      JSONB NOT NULL DEFAULT '{}',
    reason       TEXT NOT NULL DEFAULT '',
    occurred_at  TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    is_recovered BOOLEAN NOT NULL DEFAULT FALSE
);
```

> **Neither `occurred_at` nor `created_at` have `DEFAULT NOW()`** — both must be supplied explicitly by the application using `clock.now()` (for `occurred_at`, the logical time of the event; for `created_at`, the physical wall-clock write time). This keeps the application clock as the single source of both values and allows `FakeClock` in tests to control both fields independently.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `rfq_id` | UUID | FK → rfqs (`ON DELETE RESTRICT`; audit log must survive the RFQ record) |
| `event_type` | ENUM | Type of lifecycle or bid event |
| `bid_id` | UUID | FK → bids (`ON DELETE RESTRICT`; audit event must survive the bid row); nullable — set only for `BID_PLACED` |
| `payload` | JSONB | Structured data (see below) |
| `reason` | TEXT | Human-readable explanation |
| `occurred_at` | TIMESTAMPTZ | **Logical** time (when the event actually happened); set via `clock.now()` |
| `created_at` | TIMESTAMPTZ | Physical row-write time; set via `clock.now()` at insert time |
| `is_recovered` | BOOLEAN | True when `created_at - occurred_at > 5 s` (recovery) |

#### Event payload schemas

| Event type                          | Payload fields                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------------------- |
| `AUCTION_CREATED`                   | `{rfq_id, name, reference_id, auction_type}`                                            |
| `AUCTION_STARTED`                   | `{rfq_id}`                                                                              |
| `BID_PLACED`                        | `{bid_id, supplier_id, supplier_name, total_price, rank_before, rank_after, in_window}` |
| `TIME_EXTENDED`                     | `{trigger_type, old_close, new_close, extension_minutes, bid_id}`                       |
| `EXTENSION_SKIPPED_AT_FORCED_CLOSE` | `{trigger_type, forced_close, bid_id}`                                                  |
| `AUCTION_CLOSED`                    | `{final_close_time, extension_count}`                                                   |
| `AUCTION_FORCE_CLOSED`              | `{forced_close_time, extension_count}`                                                  |

---

## Indexes

```sql
-- Listing page: filter by derived status (SQL CASE expression) and upcoming close time
CREATE INDEX idx_rfqs_status_close ON rfqs (status, current_close_time);

-- Bid lookup for ranking (supplier's best bid per RFQ)
CREATE INDEX idx_bids_rfq_supplier_total ON bids (rfq_id, supplier_id, total_price);

-- Bid history ordered by price or time
CREATE INDEX idx_bids_rfq_total_time ON bids (rfq_id, total_price ASC, submitted_at ASC);

-- Activity log chronological order
CREATE INDEX idx_events_rfq_occurred ON auction_events (rfq_id, occurred_at ASC, id ASC);

-- Partial unique index on lifecycle events (prevents duplicate STARTED/CLOSED events)
-- Only one AUCTION_STARTED, AUCTION_CLOSED, or AUCTION_FORCE_CLOSED per RFQ
CREATE UNIQUE INDEX uix_lifecycle_events ON auction_events (rfq_id, event_type)
    WHERE event_type IN (
        'AUCTION_STARTED',
        'AUCTION_CLOSED',
        'AUCTION_FORCE_CLOSED'
    );
```

> **No separate idempotency index:** The `UNIQUE(rfq_id, supplier_id, idempotency_key)` constraint on `bids` already creates a B-tree index on those three columns, which covers the idempotency lookup query (`WHERE rfq_id = $1 AND supplier_id = $2 AND idempotency_key = $3`). Adding a duplicate `CREATE INDEX` would waste storage and write overhead.

---

## Enum Summary

| Enum name                 | Values                                                                                                                                             |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `auction_type_enum`       | `STANDARD`, `BRITISH`                                                                                                                              |
| `auction_status_enum`     | `SCHEDULED`, `ACTIVE`, `CLOSED`, `FORCE_CLOSED`                                                                                                    |
| `extension_trigger_enum`  | `BID_IN_LAST_X`, `ANY_RANK_CHANGE_IN_LAST_X`, `L1_CHANGE_IN_LAST_X`                                                                                |
| `auction_event_type_enum` | `AUCTION_CREATED`, `AUCTION_STARTED`, `BID_PLACED`, `TIME_EXTENDED`, `EXTENSION_SKIPPED_AT_FORCED_CLOSE`, `AUCTION_CLOSED`, `AUCTION_FORCE_CLOSED` |

---

## Integrity Summary

The database enforces the following independently of application code:

| Rule | Mechanism |
|---|---|
| `forced_close > original_close > bid_start` | CHECK constraints on `rfqs` |
| `original_close ≤ current_close ≤ forced_close` | CHECK constraint on `rfqs` |
| Charges non-negative, total > 0, total = sum of parts | CHECK constraints on `bids` |
| Transit ≥ 1, validity ≥ 1 | CHECK constraints on `bids` |
| `X ≥ 1`, `Y ≥ 1` | CHECK constraints on `british_auction_configs` |
| Supplier invited at most once per RFQ | UNIQUE on `rfq_suppliers(rfq_id, supplier_id)` |
| Idempotency key unique per (rfq, supplier) | UNIQUE on `bids(rfq_id, supplier_id, idempotency_key)` (also serves as the lookup index) |
| At most one lifecycle event of each type per RFQ | Partial UNIQUE index on `auction_events` |
| Historical bids not silently deleted | `bids.rfq_id` and `bids.supplier_id` FKs are `ON DELETE RESTRICT` |
| Audit events not silently deleted | `auction_events.rfq_id` and `auction_events.bid_id` FKs are `ON DELETE RESTRICT` |
| Config/invitation rows cleaned up with RFQ | `british_auction_configs.rfq_id` and `rfq_suppliers.rfq_id` FKs are `ON DELETE CASCADE` |
| Supplier cannot be deleted while invited | `rfq_suppliers.supplier_id` FK is `ON DELETE RESTRICT` |
| Currency whitelist | CHECK on `rfqs.currency` |
| Application clock controls `submitted_at`, `occurred_at`, `created_at` | No `DEFAULT NOW()` on those columns (application must supply the value) |
