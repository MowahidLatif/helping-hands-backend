#!/usr/bin/env python3
"""
Manual API test script for donation-backend.

Usage:
  poetry run python scripts/test_api.py [--base URL]

  Ensure the server is running first:
    PORT=5050 poetry run python run.py

  And the DB is seeded:
    poetry run python scripts/seed.py --force  # if needed
"""
import argparse
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "http://127.0.0.1:5050"


def req(method: str, path: str, data=None, token=None) -> tuple[dict | None, int]:
    url = f"{BASE.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    try:
        r = urlopen(Request(url, data=body, headers=headers, method=method), timeout=10)
        out = json.loads(r.read().decode()) if r.length and r.length > 0 else {}
        return out, r.status
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            out = json.loads(body) if body else {}
        except json.JSONDecodeError:
            out = {"error": body or str(e)}
        return out, e.code
    except URLError as e:
        print(f"Connection error: {e}")
        return None, 0


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base", default=BASE, help="Base URL (default: http://127.0.0.1:5050)"
    )
    args = ap.parse_args()
    BASE = args.base.rstrip("/")

    ok = 0
    fail = 0

    # 1. Login
    print("1. Login as demo@example.com ...")
    resp, code = req(
        "POST",
        "/api/auth/login",
        {"email": "demo@example.com", "password": "demo123456"},
    )
    if code != 200 or "access_token" not in resp:
        print(f"   FAIL {code} {resp}")
        fail += 1
        sys.exit(1)
    token = resp["access_token"]
    print("   OK token obtained")
    ok += 1

    # 2. List campaigns
    print("2. List campaigns ...")
    resp, code = req("GET", "/api/campaigns", token=token)
    if code != 200 or not isinstance(resp, list):
        print(f"   FAIL {code} {resp}")
        fail += 1
    else:
        campaigns = [c for c in resp if c.get("status") == "active"]
        print(f"   OK {len(resp)} campaigns ({len(campaigns)} active)")
        ok += 1
        if not campaigns:
            print(
                "   No active campaign; seed may not have run. Run: poetry run python scripts/seed.py --force"
            )
            sys.exit(1)
        campaign_id = campaigns[0]["id"]

    # 3. Donation checkout with message
    print("3. Donation checkout with message ...")
    resp, code = req(
        "POST",
        "/api/donations/checkout",
        {
            "campaign_id": campaign_id,
            "amount": 5.00,
            "donor_email": "test@example.com",
            "message": "Great cause!",
        },
        token=token,
    )
    if code not in (200, 201):
        print(f"   FAIL {code} {resp}")
        fail += 1
    else:
        did = resp.get("donation_id")
        print(f"   OK donation_id={did}")
        ok += 1

        # 4. GET donation (should include message)
        if did:
            print("4. GET donation (check message) ...")
            r2, c2 = req("GET", f"/api/donations/{did}", token=token)
            if c2 != 200:
                print(f"   FAIL {c2} {r2}")
                fail += 1
            elif r2.get("message") != "Great cause!":
                print(f"   FAIL message missing or wrong: {r2.get('message')}")
                fail += 1
            else:
                print(f"   OK message={r2.get('message')!r}")
                ok += 1

    # 5. Media signed-url: valid filename
    print("5. Media signed-url (valid photo.jpg) ...")
    r5, c5 = req(
        "GET",
        f"/api/media/signed-url?campaign_id={campaign_id}&filename=photo.jpg&content_type=image/jpeg",
        token=token,
    )
    if c5 != 200:
        print(f"   FAIL {c5} {r5}")
        fail += 1
    else:
        print(f"   OK key={r5.get('key', '')[:50]}...")
        ok += 1

    # 6. Media signed-url: invalid extension
    print("6. Media signed-url (invalid x.exe) ...")
    r6, c6 = req(
        "GET",
        f"/api/media/signed-url?campaign_id={campaign_id}&filename=x.exe&content_type=image/jpeg",
        token=token,
    )
    if c6 != 400:
        print(f"   FAIL expected 400, got {c6} {r6}")
        fail += 1
    else:
        print(f"   OK rejected: {r6.get('error', r6)}")
        ok += 1

    # 7. Media signed-url: missing filename
    print("7. Media signed-url (missing filename) ...")
    r7, c7 = req(
        "GET",
        f"/api/media/signed-url?campaign_id={campaign_id}",
        token=token,
    )
    if c7 != 400:
        print(f"   FAIL expected 400, got {c7} {r7}")
        fail += 1
    else:
        print(f"   OK rejected: {r7.get('error', r7)}")
        ok += 1

    # 8. Embed: valid YouTube
    print("8. Add embed (YouTube) ...")
    r8, c8 = req(
        "POST",
        "/api/media",
        {
            "campaign_id": campaign_id,
            "type": "embed",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        },
        token=token,
    )
    if c8 not in (200, 201):
        print(f"   FAIL {c8} {r8}")
        fail += 1
    else:
        print(f"   OK embed created id={r8.get('id')}")
        ok += 1

    # 9. Embed: invalid localhost
    print("9. Add embed (invalid localhost) ...")
    r9, c9 = req(
        "POST",
        "/api/media",
        {
            "campaign_id": campaign_id,
            "type": "embed",
            "url": "https://localhost/video/123",
        },
        token=token,
    )
    if c9 != 400:
        print(f"   FAIL expected 400, got {c9} {r9}")
        fail += 1
    else:
        print(f"   OK rejected: {r9.get('error', r9)}")
        ok += 1

    # Summary
    print(f"\n--- {ok} passed, {fail} failed ---")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
