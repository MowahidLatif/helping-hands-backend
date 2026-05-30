# Security Review Checklist

## CORS

- [x] CORS configured via `CORS_ALLOWED_ORIGINS` with localhost defaults only in development
- [x] `supports_credentials=True` for cookie/auth
- [x] Production startup check enforces non-localhost API CORS origins
- [x] Socket.IO CORS defaults to API CORS and is guarded in production

## JWT

- [x] JWT_ACCESS_TOKEN_EXPIRES = 15 minutes
- [x] JWT_REFRESH_TOKEN_EXPIRES = 30 days
- [x] Tokens in Authorization header (Bearer)
- [x] Production startup check enforces strong `JWT_SECRET` (>= 32 chars)
- [ ] Consider shorter refresh token expiry for sensitive apps

## S3 / MinIO

- [x] Presigned PUT URLs for uploads (no direct key exposure)
- [x] Bucket created with download policy for public read
- [ ] Production: restrict bucket policy, avoid public read if possible
- [ ] Use ACL `private` + presigned GET for reads
- [ ] Ensure S3 keys (AWS_ACCESS_KEY_ID, etc.) are not in repo

## Auth & Authorization

- [x] Password hashing via bcrypt
- [x] Org role checks (owner, admin, member) via `require_org_role`
- [x] Admin-only routes protected (draw-winner, export, receipts)
- [ ] Consider rate limiting on forgot-password if added
- [ ] Audit login failure logging (avoid logging passwords)

## Stripe Webhooks

- [x] Webhook signature verification when STRIPE_WEBHOOK_SECRET set
- [x] Event deduplication via stripe_events table
- [x] Webhook route exempt from rate limiting
- [x] Production startup check requires Stripe API + webhook secrets

## Rate Limiting

- [x] Global rate limit (200/min per IP) via RATE_LIMIT_PER_MINUTE
- [x] Auth endpoints stricter (10/min) via RATE_LIMIT_AUTH_PER_MINUTE
- [x] Webhooks exempt
- [ ] Production: consider Redis-backed rate limit for multi-instance

## Input Validation

- [x] UUID validation for campaign_id, donation_id
- [x] Amount validation in checkout
- [ ] Add request body size limits
- [ ] Sanitize user content (comments, updates) for XSS if rendered in HTML

## Secrets & Env

- [ ] Ensure .env not committed
- [ ] Rotate API keys periodically
- [x] AWS Secrets Manager support for DB/Stripe/OpenAI/SendGrid via `*_SECRET_NAME`
- [x] Production startup checks enforce required secrets and reject unsafe DEV flags

## API Exposure

- [ ] Admin/metrics: restrict to internal network or auth
- [ ] Consider API key for programmatic access
- [ ] Document which endpoints are public vs authenticated
