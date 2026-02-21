# Railway Deploy (AidCare Backend)

## 1. Create service from repo
- In Railway, create a new service from your forked repo.
- Set **Root Directory** to `aidcare-backend`.
  - This is required because this repo is a monorepo.

## 2. Build + start settings
This folder already has:
- `railway.json`
- `Dockerfile`
- `start.py`

Railway should build with Dockerfile and start with `python start.py`.

## 3. Required environment variables
Set these in Railway service variables:
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`

Recommended:
- `AIDCARE_PRELOAD_MODELS_ON_STARTUP=0`
  - Speeds startup and avoids cold-start failures on small instances.
- `AIDCARE_ALLOW_SQLITE_FALLBACK=1`
  - Lets service boot if `DATABASE_URL` is missing.

For persistent DB (recommended):
- Attach Railway Postgres and set `DATABASE_URL`.

Optional for TTS:
- `ELEVENLABS_API_KEY`
- `YARNGPT_API_KEY`

## 4. Health check
Use `/health` as your health endpoint.

## 5. Common errors and fixes
- `DATABASE_URL environment variable not set`
  - Add Postgres plugin or keep `AIDCARE_ALLOW_SQLITE_FALLBACK=1`.

- `python: can't open file '/app/start.py'`
  - Root directory is wrong. Set Root Directory to `aidcare-backend`.

- Docker build fails during apt install
  - Pull latest backend changes (Dockerfile fix included).

- Frontend cannot call backend from Railway domain (CORS)
  - Pull latest backend changes (Railway CORS regex included).

## 6. Frontend note
If frontend is deployed separately, set:
- `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>.up.railway.app`
