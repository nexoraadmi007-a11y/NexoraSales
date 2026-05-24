# NEXORA SALESLEAD

NEXORA SALESLEAD is a fresh, isolated FastAPI backend for weekday operational lead intelligence. It generates school and solar-company leads, scores them, writes a professional Excel report, and sends the report into Telegram Monday-Friday at exactly 9:00 AM Africa/Lagos.

## What It Does

- Generates 30 fresh weekday leads: 15 schools and 15 solar companies.
- Prioritizes Abeokuta, then Ogun State, then Lagos.
- Uses Apify-powered Google Maps scraping with strict industry filtering.
- Deduplicates leads using persistent Supabase fingerprints.
- Scores lead quality, operational complexity, and SaaS potential.
- Creates enterprise-formatted Excel with summary and lead sheets.
- Sends the Excel file to customer care and sends the admin a delivery summary only.
- Supports Telegram agent/admin commands and AI chat analysis.
- Stores conversations, follow-ups, activity logs, reports, scores, and vector memory.

## Setup

1. Create a Supabase project and run:

```sql
-- Supabase SQL editor
-- Paste and execute supabase/migrations/001_nexora_saleslead_schema.sql
```

2. Create `.env` from `.env.example`.

3. Optional interactive validation:

```bash
python -m src.config.setup_wizard
```

4. Install and run locally:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

5. Or run with Docker:

```bash
docker compose up --build
```

## Required Environment

All runtime services are isolated to this project:

- Telegram bot token, username, admin ID, admin channel ID, and customer-care Telegram ID.
- OpenAI API key.
- Apify API key.
- Supabase URL, anon key, and service role key.
- Redis URL.
- Optional Sentry DSN.

## Telegram Commands

Agent commands:

- `/start`
- `/help`
- `/my_leads`
- `/switch`
- `/analyze`
- `/done`

Admin commands:

- `/admin_report`
- `/pipeline`
- `/system_health`
- `/export`

## Weekday Delivery

The APScheduler job is registered as:

```text
nexora_daily_lead_delivery_0900_africa_lagos
```

Local APScheduler schedule:

```text
09:00 Monday-Friday, Africa/Lagos
```

Render cron schedule:

```text
0 8 * * 1-5
```

Render cron schedules run in UTC, so `08:00 UTC` equals `09:00 Africa/Lagos`.

Manual trigger:

```bash
curl -X POST http://localhost:8000/jobs/daily-leads/run
```

## Render Deployment

The repository includes:

- `Dockerfile`
- `docker-compose.yml`
- `render.yaml`
- `/health` endpoint for platform health checks
- Render cron job: `nexora-saleslead-weekday-leads`

On Render, create the services from `render.yaml`, then set all secret variables from `.env.example`. The weekday cron job runs:

```text
0 8 * * 1-5
```

That is 8:00 AM UTC, equal to 9:00 AM Africa/Lagos.
