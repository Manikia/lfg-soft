# LFG Tool — Middleware API

FastAPI backend for the League of Legends LFG (Looking For Game) tool.

## What this does

Sits between the Python CLI client and Supabase. The client never touches the database directly — all logic runs here. This keeps your database credentials secret and prevents injection attacks.

## Setup (do this once)

### 1. Set up the database

Go to **Supabase → SQL Editor** and run the contents of `setup_database.sql`.

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Fill in all values:
- `SUPABASE_URL` — from Supabase → Settings → API
- `SUPABASE_SERVICE_ROLE_KEY` — the service_role key (not anon!)
- `UPSTASH_REDIS_REST_URL` — from Upstash dashboard
- `UPSTASH_REDIS_REST_TOKEN` — from Upstash dashboard
- `RESEND_API_KEY` — from Resend dashboard
- `RIOT_API_KEY` — from developer.riotgames.com
- `SECRET_KEY` — any random string (used for future auth)

### 3. Update the sender email

In `email_service.py`, change `FROM_EMAIL` to use your verified Resend domain:
```python
FROM_EMAIL = "LFG Tool <noreply@yourdomain.com>"
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run locally

```bash
uvicorn main:app --reload
```

API will be at `http://localhost:8000`. Auto-docs at `http://localhost:8000/docs`.

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variables in Railway's Variables panel (same as your `.env`)
4. Deploy — Railway detects `railway.toml` automatically

Your middleware URL will be something like `https://lfg-tool.up.railway.app`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/validate-riot-id` | Validate Riot ID + get stats |
| POST | `/listings` | Post yourself as available |
| POST | `/listings/browse` | Browse compatible players |
| POST | `/requests/send` | Send a play request |
| POST | `/requests/respond` | Approve or deny a request |
| GET | `/requests/pending/{id}` | See pending requests for your listing |
| POST | `/listings/fulfill` | Mark your listing as done |
| DELETE | `/cleanup` | Remove expired listings (run on schedule) |
| GET | `/regions` | List supported regions |

## Security notes

- Service role key is **only** in this middleware, never the client
- All Supabase queries use parameterized values via the SDK (no raw SQL injection risk)
- Rate limiting via Upstash Redis on all mutation endpoints
- Riot IDs only revealed after mutual approval — never in browse results
- TODO (v2): encrypt `riot_id` and `email` columns at rest with pgcrypto

## Next step

Once this is deployed and working, build the C# WPF client that calls these endpoints.
