# Donation Checkout Testing Guide

This guide walks you through testing the donor checkout flow end-to-end.

## Prerequisites

- Docker (for Postgres, Redis, MinIO)
- Node.js and npm (for frontend)
- Python with Poetry (for backend)

---

## Part 1: Start Services

### 1. Start Docker services

```bash
cd donation-backend
docker compose --env-file .env.docker up -d
```

Verify containers are running:

```bash
docker compose ps
```

### 2. Run database migrations (if needed)

```bash
cd donation-backend
poetry run alembic upgrade head
```

### 3. Start the backend

```bash
cd donation-backend
PORT=5050 poetry run python run.py
```

Backend should be running at `http://127.0.0.1:5050`.

### 4. Start the frontend (in a new terminal)

```bash
cd frontend
npm run dev
```

Frontend should be running at `http://localhost:5173`.

---

## Part 2: Create a Test Campaign

1. Open `http://localhost:5173/signup` (or sign in at `/signin` if you have an account).

2. Sign up with:
   - First Name, Last Name, Email, Password
   - Organization Name: e.g. "Test Org"
   - Organization Subdomain: e.g. "testorg"

3. After signup you should land on the Dashboard.

4. Click **"➕ Add Campaign"** or go to `/campaign/new`.

5. Create a campaign:
   - Title: "Help Build a School"
   - Goal: 1000
   - Status: active
   - Click Create

6. You’ll be redirected to the layout builder. You can click **"Save"** or go back to the Dashboard.

7. In the Dashboard sidebar, click your campaign to select it.

8. Click **"Preview & Publish"** to open the preview page.

---

## Part 3: Test the Donation Flow

### Option A: Without Stripe Keys (form flow only)

If `STRIPE_SECRET_KEY` is not set in the backend `.env`, the checkout API returns a fake `clientSecret`. You can verify the form and API flow, but payment confirmation will fail.

1. Ensure backend `.env` does **not** contain `STRIPE_SECRET_KEY` (or leave it empty).

2. In the frontend `.env`, you can use any placeholder:
   ```
   VITE_STRIPE_PUBLISHABLE_KEY=pk_test_
   ```
   Stripe Elements may not load fully; that’s expected.

3. From the Preview page, click **"Donate Now"** (this navigates to the donate page with the correct campaign ID), or go directly to:
   ```
   http://localhost:5173/donate/<campaign-id>
   ```
   **Tip:** To find the campaign ID: after creating a campaign, the URL when editing layout is `/campaign/page-layout/<campaign-id>`. Or open DevTools → Network tab, select a campaign in the Dashboard, and check the response of `GET /api/campaigns` for the `id` field.

4. On the donate page:
   - Choose an amount (preset or custom)
   - Optionally enter email and message
   - Click **"Donate $X.XX"**

5. Expected behavior:
   - The checkout API should succeed and return `donation_id` and `clientSecret`.
   - If Stripe Elements load, you’ll see the payment form.
   - Confirming payment will fail with a Stripe error (invalid secret).
   - You’ve validated: campaign load, form submission, checkout API, and error handling.

---

### Option B: With Stripe Test Keys (full end-to-end)

1. Create a Stripe account at [stripe.com](https://stripe.com) and use **Test mode**.

2. In Stripe Dashboard → Developers → API keys, copy:
   - **Publishable key** (starts with `pk_test_`)
   - **Secret key** (starts with `sk_test_`)

3. Backend `.env`:
   ```
   STRIPE_SECRET_KEY=sk_test_your_key_here
   STRIPE_CURRENCY=usd
   ```
   Optionally:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```
   (Only needed if you run the webhook listener below.)

4. Frontend `.env`:
   ```
   VITE_STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
   ```

5. Restart both backend and frontend so they pick up the new env vars.

6. Go to the donate page: from the Dashboard, select your campaign and click **"Preview & Publish"**, then **"Donate Now"**. Or open `http://localhost:5173/donate/<campaign-id>` directly.

7. Fill in the form:
   - Amount: e.g. $25
   - Email: any test email
   - Message: optional

8. Click **"Donate $25"** → Stripe payment form should appear.

9. Use Stripe test card:
   - Card: `4242 4242 4242 4242`
   - Expiry: any future date (e.g. 12/34)
   - CVC: any 3 digits (e.g. 123)
   - ZIP: any 5 digits (e.g. 12345)

10. Click **"Pay $25"**.

11. Expected behavior:
    - Stripe processes the payment
    - Redirect to thank-you page: `/donate/<campaign-id>/thank-you?donation_id=...`
    - Thank-you page shows amount and campaign name
    - Share buttons (X, Facebook, Copy link) appear

12. In the Dashboard, select the campaign and confirm:
    - Raised amount increased
    - Donations count increased

---

## Part 4: Optional – Webhook Testing

To test webhook handling (DB update, email receipt, real-time events):

1. Install Stripe CLI: [stripe.com/docs/stripe-cli](https://stripe.com/docs/stripe-cli)

2. Log in:
   ```bash
   stripe login
   ```

3. Forward webhooks to your backend:
   ```bash
   stripe listen --forward-to http://127.0.0.1:5050/webhooks/stripe
   ```

4. Copy the `whsec_...` signing secret and add to backend `.env`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

5. Restart the backend and run a donation as in Option B.

---

## Quick Reference: URLs

| URL | Purpose |
|-----|---------|
| `http://localhost:5173/signup` | Create account |
| `http://localhost:5173/signin` | Sign in |
| `http://localhost:5173/dashboard` | Dashboard (campaigns) |
| `http://localhost:5173/campaign/new` | Create campaign |
| `http://localhost:5173/preview` | Preview (needs `campaignId` in state from Dashboard) |
| `http://localhost:5173/donate/<campaign-id>` | Donor donation page |

---

## Troubleshooting

### "Payment is not configured"
- Ensure `VITE_STRIPE_PUBLISHABLE_KEY` in frontend `.env` starts with `pk_test_` or `pk_live_`.
- Restart the frontend dev server.

### "Campaign not found"
- Check that the campaign ID in the URL is correct.
- Use the ID from the Dashboard when you click a campaign (or from `/campaign/page-layout/<id>`).

### CORS errors
- Backend should allow `http://localhost:5173` and `http://127.0.0.1:5173`.
- Check CORS config in `donation-backend/app/__init__.py`.

### Checkout returns 400
- Ensure `campaign_id` and `amount` are sent in the request body.
- Amount must be a positive number.

### Stripe "Invalid API Key"
- Confirm `STRIPE_SECRET_KEY` and `VITE_STRIPE_PUBLISHABLE_KEY` are correct and in test mode.
- No extra spaces or quotes in `.env`.
