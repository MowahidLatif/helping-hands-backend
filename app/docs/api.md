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
