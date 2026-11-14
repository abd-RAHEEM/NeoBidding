# Cloud-Hosted Architecture & Deployment Guide
## Neon (PostgreSQL) + Upstash (Redis) + Render (FastAPI & React)

This document describes how to configure, develop locally against, and deploy **NeoBidding: British Auction RFQ System** using cloud-managed infrastructure:
- **Neon**: Serverless cloud PostgreSQL (Single Source of Truth).
- **Upstash**: Serverless cloud Redis (Celery task queue broker only, TLS-enabled).
- **Render**: Cloud hosting platform for the FastAPI Web Service, Celery Worker, Celery Beat, and React Static Site.

---

## 1. System Architecture & Separation of Concerns

```
+---------------------------------------------------------------------------------+
|                                 USER BROWSER                                    |
|                      React 18 + Vite SPA (Render / Local)                       |
+---------------------------------------------------------------------------------+
          |                                                   |
          | HTTP / JSON REST                                  | HTTP / JSON REST
          | (Local Dev -> Vite Proxy /api/v1)                 | (Prod -> VITE_API_BASE_URL)
          v                                                   v
+---------------------------------------------------------------------------------+
|                              FASTAPI WEB SERVICE                                |
|                        (Uvicorn ASGI, Stateless API)                            |
+---------------------------------------------------------------------------------+
          |                                                   |
          | SQL (psycopg2, pool_pre_ping=True)                | TLS Queue Push (rediss://)
          v                                                   v
+-------------------------------+                   +-----------------------------+
|        NEON POSTGRESQL        |                   |        UPSTASH REDIS        |
|  * Single Source of Truth     |                   |  * Celery Broker ONLY       |
|  * RFQs, Bids, Audit Events   |                   |  * TLS Certificate Verified |
|  * Row-level Locks & Triggers |                   |  * No persistent business   |
|  * Alembic Migration Managed  |                   |    data stored here         |
+-------------------------------+                   +-----------------------------+
          ^                                                   ^
          | SQL Read/Write                                    | TLS Task Consumption
          |                                                   |
+---------------------------------------------------------------------------------+
|                          CELERY WORKER & CELERY BEAT                            |
|  * Celery Beat  : Periodic sweeper (checks due auctions every 5 seconds)       |
|  * Celery Worker: Executes finalize_due_auctions tasks against Neon DB          |
+---------------------------------------------------------------------------------+
```

### Key Principles
1. **Single Source of Truth:** Neon PostgreSQL stores all RFQs, bids, suppliers, and auction state machines. Redis is **strictly a message broker** for Celery; Celery's result backend is disabled (`backend=None`).
2. **Encrypted Cloud Redis:** Upstash requires TLS via the `rediss://` scheme. Celery is configured with `broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED}` to enforce certificate verification.
3. **Resilient Serverless Pooling:** Neon's serverless compute suspends after inactivity. SQLAlchemy is configured with `pool_pre_ping=True` and `pool_recycle=300` to automatically reconnect seamlessly without throwing `ConnectionClosed` errors.

---

## 2. Setting Up Cloud Credentials

### A. Neon (PostgreSQL)
1. Sign in to [Neon Console](https://console.neon.tech).
2. Create a new project (e.g., `rfq-auction`).
3. Under **Dashboard -> Connection Details**:
   - Select **Connection string**.
   - Check **Pooled connection** (recommended for serverless compute).
   - Ensure the string looks like:
     ```
     postgresql://<username>:<password>@ep-<endpoint-id>-pooler.<region>.aws.neon.tech/<dbname>?sslmode=require
     ```
   *(Note: If your URL starts with `postgres://`, our backend configuration automatically normalizes it to `postgresql://` for SQLAlchemy).*

### B. Upstash (Redis)
1. Sign in to [Upstash Console](https://console.upstash.com).
2. Create a new Redis Database (e.g., `rfq-broker`). Select your preferred region (ideally close to your Neon region).
3. Under **Details -> Connect to your database**:
   - Look for the **Redis URL** tab or **Celery** connection string.
   - The connection string starts with `rediss://` (double 's' indicates TLS/SSL):
     ```
     rediss://default:<password>@<endpoint-id>.upstash.io:<port>
     ```
   - Keep the default port `6379`.

---

## 3. Local Development (Windows PowerShell)

No local PostgreSQL, local Redis, or Docker installation is needed. All services connect directly to your cloud Neon and Upstash instances.

### Step 1: Clone & Configure Environment Variables
In your project root:

```powershell
# Copy the example environment file
Copy-Item backend\.env.example backend\.env
```

Open `backend\.env` in your editor and enter your credentials:
```env
DATABASE_URL=postgresql://neondb_owner:YOUR_NEON_PASSWORD@ep-sample-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
REDIS_URL=rediss://default:YOUR_UPSTASH_PASSWORD@sample-endpoint.upstash.io:6379
CORS_ORIGIN=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
```

> **Security Note:** `backend/.env` is ignored by Git (`.gitignore`) and will never be committed to your repository.

---

### Step 2: Install Python Dependencies
```powershell
# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install required packages (FastAPI, SQLAlchemy, psycopg2-binary, Celery, Redis, python-dotenv)
pip install -r backend\requirements.txt
```

---

### Step 3: Verify Connections Safely
Before starting any service or running migrations, test your Neon and Upstash connections using our built-in probe:

```powershell
$env:PYTHONPATH="backend"
python backend\scripts\test_connections.py
```

**Expected output:**
```
============================================================
 British Auction RFQ System - Cloud Services Connectivity Check
============================================================
[i] Loaded environment from: D:\osama\Projects\RFQ\backend\.env

============================================================
 1. TESTING POSTGRESQL (NEON / CLOUD DB)
============================================================
[*] Configured URL: postgresql://neondb_owner:*****@ep-sample-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
[+] Connection SUCCESSFUL (42.1ms latency)
    - Database : neondb
    - User     : neondb_owner
    - Version  : PostgreSQL 16.x ...

============================================================
 2. TESTING REDIS (UPSTASH / CELERY BROKER)
============================================================
[*] Configured URL: rediss://default:*****@sample-endpoint.upstash.io:6379
[*] Transport mode: TLS (rediss://) [Verified SSL]
[+] Connection SUCCESSFUL (38.4ms latency)
    - PING roundtrip: OK
    - SET/GET/DEL probe: Verified
    - Role: Celery task queue broker only (DB remains source of truth)

============================================================
 SUMMARY
============================================================
 - PostgreSQL (Neon) : [PASS]
 - Redis (Upstash)   : [PASS]

All configured connections are healthy!
```

---

### Step 4: Apply Database Migrations (Alembic)
Run the initial database schema migration to create all tables, indexes, and constraints in Neon:

```powershell
cd backend
alembic upgrade head
cd ..
```

*(Optional) Seed sample auctions for testing:*
```powershell
$env:PYTHONPATH="backend"
python scripts\seed.py --live
```

---

### Step 5: Start All Services in Separate PowerShell Windows

#### Terminal 1: FastAPI Web Service
```powershell
cd backend
..\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

#### Terminal 2: Celery Worker
> **Important for Windows Users:** Celery's default `prefork` pool uses Unix `fork()`, which does not exist on Windows. You **must** specify `--pool=solo` on Windows:
```powershell
cd backend
..\venv\Scripts\Activate.ps1
celery -A app.core.celery_app.celery_app worker --pool=solo -l info
```

#### Terminal 3: Celery Beat (Scheduler)
Runs the periodic task `finalize_due_auctions` every 5 seconds:
```powershell
cd backend
..\venv\Scripts\Activate.ps1
celery -A app.core.celery_app.celery_app beat -l info
```

#### Terminal 4: React Frontend (Vite)
```powershell
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173). The frontend automatically routes all API requests through Vite's local reverse proxy to `http://localhost:8000/api/v1`.

---

## 4. Render Deployment Guide

Render hosts your application across 4 coordinated services:
1. **FastAPI Web Service** (Web Service, Python)
2. **Celery Worker** (Background Worker, Python)
3. **Celery Beat** (Background Worker, Python)
4. **React Frontend** (Static Site)

You can deploy using either the **Render Blueprint (`render.yaml`)** or manual dashboard setup.

---

### Service Configuration Details

#### 1. FastAPI Web Service (`rfq-backend`)
- **Service Type:** Web Service
- **Runtime:** Python 3
- **Build Command:** `pip install -r backend/requirements.txt`
- **Pre-Deploy Command:** `cd backend && alembic upgrade head`
- **Start Command:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/api/v1/health`
- **Environment Variables:**
  | Variable | Value / Description |
  |---|---|
  | `DATABASE_URL` | Your Neon PostgreSQL connection string (`postgresql://...`) |
  | `REDIS_URL` | Your Upstash Redis connection string (`rediss://...`) |
  | `CORS_ORIGIN` | Your deployed frontend URL (e.g. `https://rfq-frontend.onrender.com`) |
  | `PYTHONPATH` | `backend` |

---

#### 2. Celery Worker (`rfq-celery-worker`)
- **Service Type:** Background Worker
- **Runtime:** Python 3
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `cd backend && celery -A app.core.celery_app.celery_app worker -l info`
- **Environment Variables:**
  | Variable | Value / Description |
  |---|---|
  | `DATABASE_URL` | Your Neon PostgreSQL connection string |
  | `REDIS_URL` | Your Upstash Redis connection string |
  | `PYTHONPATH` | `backend` |

---

#### 3. Celery Beat Scheduler (`rfq-celery-beat`)
- **Service Type:** Background Worker
- **Runtime:** Python 3
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `cd backend && celery -A app.core.celery_app.celery_app beat -l info`
- **Environment Variables:** Same as Celery Worker.
- **Instance Count:** Strictly **1** instance (never scale Beat to multiple instances to prevent duplicate task execution).

---

#### 4. React Static Site (`rfq-frontend`)
- **Service Type:** Static Site
- **Build Command:** `cd frontend && npm install && npm run build`
- **Publish Directory:** `./frontend/dist`
- **Redirects / Rewrites (SPA Routing):**
  - **Type:** Rewrite
  - **Source:** `/*`
  - **Destination:** `/index.html`
- **Environment Variables:**
  | Variable | Value / Description |
  |---|---|
  | `VITE_API_BASE_URL` | `https://rfq-backend.onrender.com/api/v1` (replace with your actual backend URL) |

---

### Step-by-Step Deployment Walkthrough

1. **Push your code to GitHub / GitLab**.
2. **Deploy via Render Blueprint (One-Click):**
   - In Render, click **New +** -> **Blueprint**.
   - Connect your repository. Render reads `render.yaml`.
   - In the prompt, enter your `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGIN`, and `VITE_API_BASE_URL`.
   - Click **Apply**.
3. **Configure Cross-Origin Resource Sharing (CORS):**
   - Once the React Static Site is built, copy its public URL (e.g. `https://rfq-frontend.onrender.com`).
   - Go to your `rfq-backend` Web Service on Render -> **Environment**.
   - Update `CORS_ORIGIN` to match `https://rfq-frontend.onrender.com`.
   - Render will automatically trigger a redeploy of the backend.

---

## 5. Free-Tier Limitations & Operational Best Practices

> [!WARNING]
> **Upstash Daily Command Limit:**
> Upstash's Free Tier includes **10,000 commands/day**.
> Celery Beat polls `finalize_due_auctions` every 5 seconds (17,280 triggers/day). Over 24 hours, this can consume ~30,000 to 50,000 commands.
> - **Recommendation for Free Tier:** If testing on Upstash free tier, increase the interval in `backend/app/core/celery_app.py` from `5.0` to `30.0` or `60.0` seconds, or upgrade Upstash to Pay-As-You-Go ($0.20 per 100k commands).

> [!NOTE]
> **Render Free Tier Spin-Down:**
> Render Free Web Services sleep after 15 minutes of inactivity. When a new request arrives, it may take 30-50 seconds to wake up.
> Render Background Workers (Celery Worker and Beat) require the Starter plan ($7/mo each). If you want a 100% free setup for hobby testing, you can run the Celery Worker and Beat on your local machine pointing to cloud Neon and Upstash while the Web Service runs on Render.

> [!TIP]
> **Neon Serverless Cold Starts:**
> Neon compute can suspend after 5 minutes of idle time. Our backend's `pool_pre_ping=True` and `pool_recycle=300` settings handle this gracefully. The first request after a cold start may take ~1-2 seconds while Neon spins up.
