# Security Review Checklist

## CORS

- [x] CORS configured for known origins (`http://localhost:3000`, `http://127.0.0.1:3000`)
- [x] `supports_credentials=True` for cookie/auth
- [ ] Production: add deployed frontend origins to CORS config
- [ ] Ensure no `Access-Control-Allow-Origin: *` with credentials

## JWT

- [x] JWT_ACCESS_TOKEN_EXPIRES = 15 minutes
- [x] JWT_REFRESH_TOKEN_EXPIRES = 30 days
- [x] Tokens in Authorization header (Bearer)
- [ ] Production: set strong JWT_SECRET (min 32 bytes, random)
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
- [ ] Production: always set STRIPE_WEBHOOK_SECRET

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
- [ ] Use secret manager (e.g. AWS Secrets Manager) in production

## API Exposure

- [ ] Admin/metrics: restrict to internal network or auth
- [ ] Consider API key for programmatic access
- [ ] Document which endpoints are public vs authenticated
