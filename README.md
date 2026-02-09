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

## Release (v1+)

See [app/docs/RELEASE.md](app/docs/RELEASE.md) for schema freeze and tagging.
