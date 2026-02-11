#!/bin/bash
# Quick script to create a test user via API

echo "Creating test user..."

curl -X POST http://127.0.0.1:5050/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "first_name": "Test",
    "last_name": "User",
    "org_name": "Test Organization",
    "org_subdomain": "testorg"
  }' | python3 -m json.tool

echo ""
echo "Test account created!"
echo "Email: test@example.com"
echo "Password: password123"
echo ""
echo "You can now sign in at: http://localhost:5173/signin"
