# SSC CGL Practice Platform

Full-stack platform for practicing SSC CGL previous-year papers. Backend: FastAPI + PostgreSQL + SQLAlchemy + Alembic. Frontend: Next.js (App Router). See `.claude` plan history for the full architecture design.

Status: **Phase 0 (project scaffolding) only.** No auth, no database models, no exam logic yet.

## Project layout

```
.
├── docker-compose.yml       # Postgres + backend + frontend services
├── .env.example             # docker-compose variables (postgres creds, ports)
├── backend/                 # FastAPI app
│   ├── app/
│   │   ├── main.py          # app factory, CORS, /health
│   │   ├── core/config.py   # Settings (env vars)
│   │   └── db/               # engine, session, Base, get_db dependency
│   ├── alembic/              # migrations (async template, no models yet)
│   ├── requirements.txt
│   └── .env.example
└── frontend/                 # Next.js app (App Router + TypeScript + Tailwind)
    └── .env.example
```

## Option A — Run with Docker Compose

Requires Docker + Docker Compose installed.

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

docker compose up --build
```

- Backend: http://localhost:8000/health
- Frontend: http://localhost:3000
- Postgres: localhost:5432 (credentials from `.env`)

## Option B — Run natively (no Docker)

Requires a local PostgreSQL server, Python 3.12+, and Node 20+.

**1. Database**

```bash
sudo -u postgres psql -c "CREATE USER ssc_cgl WITH PASSWORD 'change_me';"
sudo -u postgres psql -c "CREATE DATABASE ssc_cgl OWNER ssc_cgl;"
```

**2. Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL if your Postgres creds differ
uvicorn app.main:app --reload
```

Visit http://localhost:8000/health — should return `{"status": "ok", "database": "ok"}`.

**3. Frontend**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Visit http://localhost:3000.

## Alembic

Migrations live in `backend/alembic/`. The database URL is read from `app.core.config.get_settings()` (i.e. `backend/.env`), not hardcoded in `alembic.ini`. From `backend/`:

```bash
alembic current            # show current revision
alembic revision --autogenerate -m "message"   # after adding models (Phase 1+)
alembic upgrade head
```

No models exist yet (Phase 0), so there is nothing to migrate — this is set up so Phase 1 can start writing models immediately.
