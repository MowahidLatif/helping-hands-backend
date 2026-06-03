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

## Production environment requirements

Set these env vars before running in production:

- `APP_ENV=production` (or `FLASK_ENV=production`) to enable production startup guards
- `JWT_SECRET` (strong random value, minimum 32 chars)
- `CORS_ALLOWED_ORIGINS` (comma-separated frontend origins allowed by browsers)
- `SOCKETIO_CORS_ORIGINS` (optional; defaults to `CORS_ALLOWED_ORIGINS`)
- `FRONTEND_URL` (base URL used for password reset links)
- Stripe configuration:
  - `STRIPE_SECRET_NAME` (preferred, AWS Secrets Manager) or plain `STRIPE_SECRET_KEY`
  - webhook signing secret via `STRIPE_SECRET_NAME` JSON or plain `STRIPE_WEBHOOK_SECRET`
- OpenAI configuration:
  - `OPENAI_SECRET_NAME` (preferred, AWS Secrets Manager) or plain `OPENAI_API_KEY`
- Email provider configuration:
  - SendGrid: `EMAIL_PROVIDER=sendgrid` and `SENDGRID_SECRET_NAME` (preferred) or `SENDGRID_API_KEY`
  - SES: `EMAIL_PROVIDER=ses` and valid AWS credentials/role with SES send permissions

Startup safety checks:

- App startup will fail in production if `JWT_SECRET` is weak/missing.
- App startup will fail in production if `CORS_ALLOWED_ORIGINS` is missing.
- App startup will fail in production if Socket.IO CORS falls back to localhost defaults.
- App startup will fail in production if `FRONTEND_URL` is missing.
- App startup will fail in production if Stripe/OpenAI/email config is missing.
- App startup will fail in production if `DEV_EMAIL_LOG_ONLY=1` or `DEV_STRIPE_NO_VERIFY=1`.

## Secrets Manager (AWS-first for local + prod)

This backend supports AWS-first secret resolution. For each integration, set `*_SECRET_NAME` to the
Secrets Manager entry, and keep plain API keys as fallback for offline/local-only development.

Recommended secret mappings:

- `STRIPE_SECRET_NAME` -> JSON with `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- `OPENAI_SECRET_NAME` -> plain string or JSON containing `OPENAI_API_KEY`
- `SENDGRID_SECRET_NAME` -> plain string or JSON containing `SENDGRID_API_KEY`
- `DB_SECRET_NAME` -> JSON containing `password` (RDS-managed format)

To use AWS Secrets Manager in both local and prod, your runtime identity needs:

- `secretsmanager:GetSecretValue` permission for the referenced secrets
- correct `AWS_REGION`

Recommended verification after deploy:

1. Call `POST /api/auth/forgot-password` for a test user and confirm the link uses your real frontend domain.
2. Confirm browser API requests from your frontend origin succeed (no CORS errors).
3. Confirm one test email is sent successfully (receipt or password reset).
4. Confirm Stripe webhook signatures are being verified (do not enable `DEV_STRIPE_NO_VERIFY`).

## Stripe Billing (org subscriptions)

Monthly plans are billed via Stripe Checkout and managed in Settings:

- `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_GROW`, `STRIPE_PRICE_SCALE` — price IDs from Stripe Dashboard
- `STRIPE_BILLING_SUCCESS_URL`, `STRIPE_BILLING_CANCEL_URL`, `STRIPE_BILLING_PORTAL_RETURN_URL`
- Webhook events: `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`

Owners upgrade/downgrade via `POST /api/orgs/{id}/billing/change-tier`, cancel immediately via `POST /api/orgs/{id}/billing/cancel`, and manage payment methods via Customer Portal (`POST /api/orgs/{id}/billing/portal`). Enable subscription cancellation and plan changes in the Stripe Customer Portal settings as a fallback.

Run migrations after pulling: `poetry run alembic upgrade head` (includes `0030_subscription_cancel_fields`).

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
