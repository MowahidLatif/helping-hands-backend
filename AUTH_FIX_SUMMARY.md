# Auth 401 Error Fix Summary

## Issues Found and Fixed

### 1. Backend Auth Service Field Mapping
**Problem:** The backend's `signup_user()` function expected different field names than what the frontend was sending.

**Fixed in:** `app/services/auth_service.py`

**Changes:**
- Now accepts both `first_name`/`last_name` AND the old `name` field
- Now accepts both `org_name` AND `organization_name`
- Now properly handles `org_subdomain` parameter
- Returns user's `name` in the response for both login and signup

### 2. Frontend Token Storage
**Problem:** Frontend was trying to extract a `user` object from the response, but the backend returns individual fields.

**Fixed in:**
- `src/pages/SignIn/SignIn.tsx`
- `src/pages/SignUp/SignUp.tsx`

**Changes:**
- Now properly extracts `id`, `email`, `name` from response
- Constructs user object correctly before storing in localStorage

## Testing the Fix

### Step 1: Start the Backend

```bash
cd /Users/mowahidlatif/Code/donation-backend

# Start Docker services (Postgres, Redis, MinIO)
docker compose --env-file .env.docker up -d

# Start Flask backend
poetry run python run.py
```

Backend should be running at `http://127.0.0.1:5050`

### Step 2: Start the Frontend

```bash
cd /Users/mowahidlatif/Code/frontend

# Install dependencies (if not already done)
npm install

# Start dev server
npm run dev
```

Frontend should be running at `http://localhost:5173`

### Step 3: Test the Flow

1. **Sign Up**: Navigate to `http://localhost:5173/signup`
   - Fill in: First Name, Last Name, Email, Password, Org Name
   - Optional: Org Subdomain (e.g., "myorg")
   - Click "Sign Up"
   - Should auto-login and redirect to `/dashboard`

2. **Check Token**: Open browser DevTools → Application → Local Storage
   - Should see `token` with JWT value
   - Should see `user` with JSON object containing `id`, `email`, `name`, `org_id`

3. **View Dashboard**: Should now see campaigns sidebar loading
   - No more 401 errors
   - Empty list if no campaigns yet

4. **Create Campaign**: Click "Add Campaign"
   - Fill in title, goal
   - Submit
   - Should redirect to page layout builder

### Step 4: Verify API Calls

Open browser DevTools → Network tab:

1. **POST /api/auth/register** should return:
   ```json
   {
     "id": "...",
     "email": "...",
     "name": "First Last",
     "org_id": "...",
     "access_token": "...",
     "refresh_token": "..."
   }
   ```

2. **GET /api/campaigns** should return:
   - Status: 200 OK
   - Headers: `Authorization: Bearer <token>`
   - Response: `[]` (empty array if no campaigns)

## What Was Wrong

The 401 error was happening because:

1. **Signup was failing** (500 error) due to field name mismatch
2. **No token was being stored** because the response parsing was incorrect
3. **Campaigns API call had no token** because signup/login never stored it properly

## JWT Token Flow

The JWT token contains these claims:
```json
{
  "sub": "user_id",
  "org_id": "organization_id",
  "role": "owner"
}
```

The `@require_org_role()` decorator extracts `org_id` from the JWT claims, so it's critical that:
1. Login/signup adds `org_id` to the token ✅ (already working)
2. Frontend stores the token ✅ (now fixed)
3. Frontend sends token in `Authorization` header ✅ (already working via axios interceptor)

## Files Modified

### Backend
- `app/services/auth_service.py` - Field mapping and response structure

### Frontend
- `src/pages/SignIn/SignIn.tsx` - Token extraction and storage
- `src/pages/SignUp/SignUp.tsx` - Token extraction and storage

## Next Steps

After testing:
1. Delete the test script: `rm /Users/mowahidlatif/Code/donation-backend/test_auth.py`
2. Test creating a campaign
3. Test editing page layout
4. Verify all dashboard features work
