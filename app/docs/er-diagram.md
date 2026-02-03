# Entity-Relationship Diagram

## Overview

This document describes the database schema for the Donations Platform.

## Mermaid ER Diagram

```mermaid
erDiagram
    organizations {
        uuid id PK
        text name
        text subdomain
        timestamptz created_at
        timestamptz updated_at
    }

    users {
        uuid id PK
        citext email UK
        text password_hash
        text name
        timestamptz created_at
        timestamptz updated_at
    }

    org_users {
        uuid org_id PK,FK
        uuid user_id PK,FK
        org_user_role role
        timestamptz created_at
    }

    campaigns {
        uuid id PK
        uuid org_id FK
        text title
        text slug
        numeric goal
        campaign_status status
        text custom_domain UK
        numeric total_raised
        timestamptz created_at
        timestamptz updated_at
    }

    campaign_media {
        uuid id PK
        uuid org_id FK
        uuid campaign_id FK
        media_type type
        text s3_key
        text content_type
        bigint size_bytes
        text url
        text description
        int sort
        timestamptz created_at
        timestamptz updated_at
    }

    donations {
        uuid id PK
        uuid org_id FK
        uuid campaign_id FK
        int amount_cents
        text currency
        citext donor_email
        donation_status status
        text stripe_payment_intent_id UK
        timestamptz created_at
        timestamptz updated_at
    }

    email_receipts {
        uuid id PK
        uuid donation_id UK,FK
        text to_email
        text subject
        text body_text
        text body_html
        text provider
        text provider_msg_id
        timestamptz sent_at
        text last_error
        timestamptz created_at
        timestamptz updated_at
    }

    giveaway_logs {
        uuid id PK
        uuid org_id FK
        uuid campaign_id FK
        uuid winner_donation_id FK
        citext winner_email
        text mode
        int population_count
        text population_hash
        uuid created_by_user_id FK
        text notes
        timestamptz created_at
    }

    stripe_events {
        text event_id PK
        text type
        jsonb raw
        timestamptz created_at
    }

    org_email_settings {
        uuid org_id PK,FK
        text from_name
        text from_email
        text reply_to
        text bcc_to
        text receipt_subject
        text receipt_text
        text receipt_html
        timestamptz created_at
        timestamptz updated_at
    }

    organizations ||--o{ org_users : "has members"
    users ||--o{ org_users : "member of"
    organizations ||--o{ campaigns : "owns"
    campaigns ||--o{ campaign_media : "has"
    campaigns ||--o{ donations : "receives"
    organizations ||--o{ donations : "owns"
    donations ||--o| email_receipts : "receipt"
    campaigns ||--o{ giveaway_logs : "draw"
    donations ||--o| giveaway_logs : "winner"
    users ||--o{ giveaway_logs : "created by"
    organizations ||--o| org_email_settings : "config"
```

## Enums

| Enum | Values |
|------|--------|
| org_user_role | owner, admin, member |
| campaign_status | draft, active, paused, completed, archived |
| donation_status | initiated, requires_payment, processing, succeeded, failed, refunded, canceled |
| media_type | image, video, doc, other |

## Table Descriptions

| Table | Purpose |
|-------|---------|
| organizations | Campaign-creating entities (nonprofits, teams) |
| users | Authenticated users |
| org_users | Membership with role (owner/admin/member) |
| campaigns | Fundraising campaigns with goal, status, slug |
| campaign_media | Media attachments (images, videos, docs) per campaign |
| donations | Individual donations linked to campaign and Stripe |
| email_receipts | Stored receipt content; one per donation |
| giveaway_logs | Audit log for random draws among donors |
| stripe_events | Deduplicated webhook events |
| org_email_settings | Per-org email templates and sender config |
