#!/usr/bin/env python3
"""Quick test script to verify auth flow"""

import requests
import json

BASE_URL = "http://127.0.0.1:5050"


def test_signup():
    print("Testing signup...")
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "User",
            "org_name": "Test Org",
            "org_subdomain": "testorg",
        },
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 201:
        data = response.json()
        token = data.get("access_token")
        return token
    return None


def test_login():
    print("\nTesting login...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "testuser@example.com", "password": "testpass123"},
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        return token
    return None


def test_campaigns(token):
    print("\nTesting campaigns list...")
    response = requests.get(
        f"{BASE_URL}/api/campaigns", headers={"Authorization": f"Bearer {token}"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


if __name__ == "__main__":
    # Try signup first
    token = test_signup()

    # If signup fails (user exists), try login
    if not token:
        token = test_login()

    # Test campaigns with token
    if token:
        test_campaigns(token)
    else:
        print("\nFailed to get token!")
