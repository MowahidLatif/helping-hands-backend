# Donations Backend

Flask API for the donations platform (campaigns, donations, Stripe, email, real-time).

## Quick start

```bash
docker compose --env-file .env.docker up -d
poetry install
poetry run alembic upgrade head
PORT=5050 poetry run python run.py
```

## Release (v1+)

See [app/docs/RELEASE.md](app/docs/RELEASE.md) for schema freeze and tagging.
