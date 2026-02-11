# Frontend Integration Status

## Overview

The React frontend has been successfully connected to all backend APIs. This document tracks the integration status and provides testing guidance.

## Completed Integrations

### ✅ Authentication
- **Sign Up** (`POST /api/auth/register`)
  - Frontend: `/signup` page
  - Creates user + organization
  - Returns JWT token
  - Auto-login after registration

- **Sign In** (`POST /api/auth/login`)
  - Frontend: `/signin` page
  - Returns JWT token
  - Stores token in localStorage
  - Auto-attaches to all requests

- **Token Management**
  - Axios interceptor adds `Authorization: Bearer {token}` header
  - 401 responses trigger auto-logout

### ✅ Campaign Management
- **List Campaigns** (`GET /api/campaigns`)
  - Frontend: Dashboard sidebar
  - Shows all campaigns for authenticated user's org
  - Displays title, goal, raised amount, status

- **Create Campaign** (`POST /api/campaigns`)
  - Frontend: `/campaign/new` page
  - Fields: title, goal, status, giveaway_prize_cents
  - Redirects to layout builder on success

- **Get Campaign** (`GET /api/campaigns/{id}`)
  - Frontend: Dashboard campaign details panel
  - Shows full campaign info

- **Campaign Progress** (`GET /api/campaigns/{id}/progress`)
  - Frontend: Dashboard campaign details panel
  - Shows goal, raised, percent, donations count
  - Includes platform fee info if goal reached

### ✅ Page Layout Builder
- **Get Layout** (`GET /api/campaigns/{id}/page-layout`)
  - Frontend: `/campaign/page-layout/{id}` page
  - Loads existing layout or starts empty

- **Save Layout** (`PUT /api/campaigns/{id}/page-layout`)
  - Frontend: `/campaign/page-layout/{id}` page
  - Saves block configuration as JSONB
  - Validates against schema

- **Get Schema** (`GET /api/page-layout/schema`)
  - Frontend: Can fetch block types and props schema
  - Used for validation and UI generation

### ✅ Media Upload (Partial)
- **Media Routes** exist but not yet fully wired
  - `GET /api/media/signed-url` - Get S3 presigned URL
  - `POST /api/media` - Persist media record
  - Frontend has UI at `/campaign/layout-builder/{id}` but needs S3 integration

## API Endpoints Reference

### Auth Endpoints
```
POST /api/auth/register
  Body: { email, password, first_name, last_name, org_name, org_subdomain? }
  Returns: { access_token, user }

POST /api/auth/login
  Body: { email, password }
  Returns: { access_token, user }

POST /api/auth/refresh
  Headers: Authorization: Bearer {refresh_token}
  Returns: { access_token }
```

### Campaign Endpoints
```
GET /api/campaigns
  Headers: Authorization: Bearer {token}
  Returns: [{ id, title, slug, goal, status, total_raised, ... }]

POST /api/campaigns
  Headers: Authorization: Bearer {token}
  Body: { title, goal, status?, giveaway_prize_cents? }
  Returns: { id, title, slug, ... }

GET /api/campaigns/{id}
  Headers: Authorization: Bearer {token}
  Returns: { id, title, slug, goal, status, ... }

GET /api/campaigns/{id}/progress
  Returns: { goal, total_raised, percent, donations_count, platform_fee_cents?, ... }
```

### Page Layout Endpoints
```
GET /api/campaigns/{id}/page-layout
  Headers: Authorization: Bearer {token}
  Returns: { page_layout: [{ id, type, props }] }

PUT /api/campaigns/{id}/page-layout
  Headers: Authorization: Bearer {token}
  Body: { page_layout: [{ id, type, props }] }
  Returns: { page_layout: [...] }

GET /api/page-layout/schema
  Returns: { block_types: [...], block_schema: {...} }
```

## Testing the Integration

### 1. Start Backend
```bash
cd /Users/mowahidlatif/Code/donation-backend
docker compose --env-file .env.docker up -d
poetry run python run.py
```

Backend should be running at `http://127.0.0.1:5050`

### 2. Start Frontend
```bash
cd /Users/mowahidlatif/Code/frontend
npm install
npm run dev
```

Frontend should be running at `http://localhost:5173`

### 3. Test Flow
1. **Sign Up**: Go to `/signup`
   - Create account with email, password, name, org name
   - Should auto-login and redirect to `/dashboard`

2. **Create Campaign**: Click "Add Campaign" or go to `/campaign/new`
   - Fill in title, goal, optional giveaway prize
   - Submit → redirects to page layout builder

3. **Edit Page Layout**: At `/campaign/page-layout/{id}`
   - Add blocks from left panel (hero, text, donate_button, etc.)
   - Click block to edit properties in right panel
   - Save layout

4. **View Dashboard**: Go to `/dashboard`
   - See campaign in sidebar
   - Click campaign to view details
   - See progress, goal, raised amount

## Known Issues / TODO

- [ ] Media upload needs S3 presigned URL integration
- [ ] Donation checkout flow not yet wired
- [ ] Preview page needs implementation
- [ ] Organization settings page not wired
- [ ] Giveaway winner drawing UI not implemented
- [ ] Email settings UI not implemented

## Frontend Environment

Create `/Users/mowahidlatif/Code/frontend/.env`:
```
VITE_API_BASE_URL=http://127.0.0.1:5050
```

## CORS Configuration

Backend already has CORS enabled for `http://localhost:5173` in `app/__init__.py`:
```python
CORS(app, origins=["http://localhost:5173", ...])
```

## Next Steps

1. **Media Upload**: Wire S3 presigned URL flow
2. **Donation Flow**: Implement Stripe checkout integration
3. **Preview Page**: Render campaign with layout
4. **Analytics**: Add charts and stats to dashboard
5. **Settings**: Wire organization settings page
6. **Giveaway**: Add winner drawing UI
