# Donations Backend

Flask API for the donations platform (campaigns, donations, Stripe, email, real-time).

## Quick start

```bash
docker compose --env-file .env.docker up -d
poetry install
poetry run alembic upgrade head
PORT=5050 poetry run python run.py
```

> **Note:** For local dev, leave `SERVER_NAME` unset so requests to `127.0.0.1:5050` work. If you set `SERVER_NAME` (e.g. for subdomain testing), it must match the request Host exactly or Flask will return 404.

## Testing

### 1. Seed test data

```bash
poetry run python scripts/seed.py
# or --force to reset and re-seed
poetry run python scripts/seed.py --force
```

### 2. Run API test script

With the server running (`PORT=5050 poetry run python run.py`):

```bash
poetry run python scripts/test_api.py
# or with custom base URL:
poetry run python scripts/test_api.py --base http://127.0.0.1:5050
```

Covers: login, campaigns, donation checkout with message, media signed-url validation, embed validation (YouTube OK, localhost rejected).

### 3. Manual testing

- **Campaign stub UI**: http://127.0.0.1:5050/campaign-stub
- **curl** (after login to get token):
  ```bash
  TOKEN=$(curl -s -X POST http://127.0.0.1:5050/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"demo@example.com","password":"demo123456"}' | jq -r '.access_token')
  curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5050/api/campaigns
  ```

## AI site generation

Optional OpenAI-powered JSON “recipe” for public campaign pages (`campaigns.ai_site_recipe`).

- `OPENAI_API_KEY` — required for `POST /api/campaigns/<id>/ai-site/generate`
- `OPENAI_AI_SITE_MODEL` — optional (default `gpt-4o-mini`)
- `OPENAI_AI_SITE_MAX_ASSETS` — max media rows included in the AI prompt (default `32`, clamped 1–80). Selection is **round-robin by type** (image / video / doc / embed) so mixed uploads are represented.
- `OPENAI_AI_SITE_ASSETS_JSON_MAX` — max characters for the JSON block of assets in the user message (default `20000`)
- `REQUIRE_PLATFORM_PAYMENT_FOR_AI` — set to `1` or `true` to require a completed Stripe platform PaymentIntent before generation
- `STRIPE_AI_GENERATION_AMOUNT_CENTS` — platform fee amount in cents (default `500`)
- `AI_SITE_MEDIA_URL_HOSTS` — comma-separated extra hostnames allowed in recipe media URLs (CDN / public asset domain). Hosts are also derived from `S3_ENDPOINT` and optional `PUBLIC_MEDIA_BASE_URL`. Production URLs must use `https:` (HTTP only for localhost / `*.local`).
- `PUBLIC_MEDIA_BASE_URL` — optional canonical public base URL for assets; its hostname is added to the recipe URL allowlist
- `MAX_CAMPAIGN_IMAGES` / `MAX_CAMPAIGN_VIDEOS` / `MAX_CAMPAIGN_DOCS` — optional per-campaign upload caps (defaults 50 / 10 / 25)

The frontend should set `VITE_MEDIA_URL_HOSTS` to the same hostnames for defense-in-depth rendering (see `frontend/.env.example`).

After `alembic upgrade head`, jobs are stored in `ai_generation_jobs`.

## Release (v1+)

See [app/docs/RELEASE.md](app/docs/RELEASE.md) for schema freeze and tagging.
