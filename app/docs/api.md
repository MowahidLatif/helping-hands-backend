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

## Page Layout (drag-and-drop builder)
- GET /campaigns/{id}/page-layout   # get saved layout
- PUT /campaigns/{id}/page-layout   # save layout { "page_layout": { "blocks": [...] } }

Block types: hero, campaign_info, donate_button, media_gallery, text, embed, footer.
Public campaign JSON includes page_layout. Donor page: {subdomain}.domain/donate/{slug}

## Media
- GET /media/signed-url   # presigned PUT (key, content-type, max-bytes)
- POST /media              # persist metadata
- GET /campaigns/{id}/media

## Donations
- POST /donations/checkout   # create PaymentIntent, return clientSecret
- GET  /donations/{id}

## Processing fees (per campaign, not HHF revenue)

Each campaign chooses who covers **Stripe processing fees** (2.9% + $0.30):

- `donor_pays` (default): donor is grossed up at checkout so the org receives the full intended donation amount.
- `platform_absorbs`: Stripe fee is deducted from the donation before payout (micro-donations under $10 still pass Stripe fee to the donor).

HelpingHandsFund does **not** take a percentage of donations. HHF revenue is monthly subscription billing ($10 / $40 / $100 tiers), separate from donation flow.

Set `fee_option` on campaign create (draft) or patch before publish. Locked after campaign is active.

Checkout and donation records expose `fee_preview` / accounting fields. `platform_fee_cents` is always `0` under fee policy v3. Historical v2 donations may have non-zero values.

## Org tiers (subscription features)

- Tier 1 Starter — $10/mo: 1 active campaign, 1 admin, 3 AI gens/month
- Tier 2 Grow — $40/mo: 3 active campaigns, 5 members, 15 AI gens/month, iframe embed, tasks, analytics
- Tier 3 Scale — $100/mo: unlimited campaigns/members/AI, full feature set

- GET /orgs/{orgId}/tier-info
- PATCH /orgs/{orgId}/tier

Tiers gate features only; they do not affect donation payout math.

## Stripe Billing (org subscriptions)

- POST /orgs/{orgId}/billing/setup — create platform Customer + Connect Express account
- POST /orgs/{orgId}/billing/checkout — body `{ tier: 1|2|3 }`, returns `{ url }` for Stripe Checkout
- POST /orgs/{orgId}/billing/change-tier — upgrade/downgrade existing subscription (or checkout if none)
- POST /orgs/{orgId}/billing/portal — returns Customer Portal `{ url }`
- GET /orgs/{orgId}/billing/status — subscription + Connect payout status

Webhook events (same POST /webhooks/stripe endpoint): `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`, `account.updated`.

Configure `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_GROW`, `STRIPE_PRICE_SCALE` and billing redirect URLs in env.

## Webhooks
- POST /webhooks/stripe

## Public Read
- GET /campaigns/{id}/progress
- GET /campaigns/{id}/media

## Realtime
- WS /ws/campaign/{id}

## Giveaway
- POST /campaigns/{id}/draw-winner

Optional cash prize: campaigns can have `giveaway_prize_cents` (e.g. 100000 = $1000). Set via `POST /campaigns` or `PATCH /campaigns/{id}`. When a winner is drawn, the prize is included in the response and winner email.

## Comments & Updates
- CRUD /campaigns/{id}/comments
- CRUD /campaigns/{id}/updates

## Exports & Metrics
- GET /campaigns/{id}/export.csv
- GET /admin/metrics
