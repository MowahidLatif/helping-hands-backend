# Release & Schema Freeze

## v1.0.0 – Schema Freeze

As of v1.0.0, the database schema is considered frozen for the v1 API. New migrations should preserve backward compatibility where possible.

### Pre-release checklist

1. **Run migrations**: `poetry run alembic upgrade head`
2. **Smoke test**: Start app, hit key endpoints
3. **Tag**: `git tag -a v1.0.0 -m "Release v1.0.0 - schema freeze"`
4. **Push**: `git push origin v1.0.0`

### Schema baseline (v1)

- organizations, users, org_users
- campaigns, campaign_media
- donations, email_receipts
- giveaway_logs, stripe_events
- org_email_settings
- campaign_comments, campaign_updates

See [er-diagram.md](er-diagram.md) for full schema.

### Future migrations

- Prefer additive changes (new columns with defaults, new tables)
- Avoid destructive changes without a major version bump
- Document breaking changes in migration messages
