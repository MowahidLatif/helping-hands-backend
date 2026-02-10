# Donations Platform API (v1)

## Conventions
- Auth: Bearer JWT
- Dates: RFC3339 UTC (`timestamptz`)
- Money: integer cents
- Pagination: cursor (`?after=`) + `limit`

## Auth
- POST /auth/register
- POST /auth/login
- POST /auth/refresh

## Organizations
- GET /orgs
- POST /orgs
- GET /orgs/{orgId}
- PATCH /orgs/{orgId}
- GET /orgs/{orgId}/members
- POST /orgs/{orgId}/members
- DELETE /orgs/{orgId}/members/{userId}

## Campaigns
- GET /campaigns
- POST /campaigns
- GET /campaigns/{id}
- PATCH /campaigns/{id}
- DELETE /campaigns/{id}

## Media
- GET /media/signed-url   # presigned PUT (key, content-type, max-bytes)
- POST /media              # persist metadata
- GET /campaigns/{id}/media

## Donations
- POST /donations/checkout   # create PaymentIntent, return clientSecret
- GET  /donations/{id}

## Platform Fees
When a campaign reaches its goal, a platform fee is charged to the organization (campaign host):
- 0 - 50,000: 5%
- 50,000 - 500,000: 4%
- 500,000 - 1,000,000: 3%
- 1,000,000+: 2.5%

Fee is recorded once (first time goal is reached). Exposed in `GET /campaigns/{id}`, `GET /campaigns/{id}/progress` via `platform_fee_cents`, `platform_fee_percent`, `net_to_org_cents`.

## Webhooks
- POST /webhooks/stripe

## Public Read
- GET /campaigns/{id}/progress
- GET /campaigns/{id}/media

## Realtime
- WS /ws/campaign/{id}

## Giveaway
- POST /campaigns/{id}/draw-winner

## Comments & Updates
- CRUD /campaigns/{id}/comments
- CRUD /campaigns/{id}/updates

## Exports & Metrics
- GET /campaigns/{id}/export.csv
- GET /admin/metrics
