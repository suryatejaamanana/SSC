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

## Production deployment (free tier): Render + Neon + Backblaze B2

One Render web service (`govt-exam`, see `render.yaml` and `Dockerfile`) runs Next.js (public) and FastAPI (internal, `/api/*` is proxied). State lives outside Render:

- **PostgreSQL**: Neon (free). Use the *direct* (non-`-pooler`) connection string as `DATABASE_URL`. Migrations run on every boot (`start.sh`).
- **Images / source PDFs**: a **private** Backblaze B2 bucket (`MEDIA_BACKEND=b2`). The API reads objects and serves them only after the login and published-question checks; no public bucket and no presigned URLs.
- **PDF import** is disabled on Render (`IMPORTS_ENABLED=false`, the free instance has 512MB RAM). Import locally instead.

First admin: register in the UI, then promote that user directly in Neon (`update users set role='admin' where email='you@example.com'`). There is no automatic admin creation.

### Importing a paper locally into Neon + B2

Put the production values in `backend/.env.production` (git-ignored via `.env.*`; confirm with `git status` that it is not listed), then:

```bash
cd backend
source .venv/bin/activate && pip install -r requirements.txt
set -a; source .env.production; set +a     # DATABASE_URL, MEDIA_BACKEND=b2, B2_*

python -m scripts.check_b2                 # write/read/delete round-trip + bucket-is-private check
python -m scripts.import_paper path/to/paper.pdf \
    --year 2024 --tier "Tier 1" --admin-email you@example.com
```

`import_paper` prints the target kind (local or PRODUCTION), database host and storage backend (bucket name for B2) and never prints credentials. `--admin-email` must be an existing admin account.

Safeguards:

- **Production** (any non-local database host) asks you to type the database host back at an interactive prompt. `--yes` is **refused** for production targets (it is only accepted for local ones), and a non-interactive session is refused too.
- **Mixed targets are rejected** with no override: a remote database with local-disk media, a local database with `MEDIA_BACKEND=b2`, and a Neon `-pooler` host (use the direct connection string).

Do **not** run the backend tests (`pytest`) in a shell where the production variables are loaded: they `TRUNCATE` every table. The test suite now refuses to start unless `DATABASE_URL` points at a local database, but load production variables only in the shell (or subshell) where you run the import.
