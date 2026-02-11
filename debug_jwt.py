#!/usr/bin/env python3
"""Debug JWT token validation"""

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token, decode_token
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv(
    "JWT_SECRET_KEY", "dev-secret-key-change-in-production"
)

jwt = JWTManager(app)

# Create a test token
with app.app_context():
    test_token = create_access_token(
        identity="test-user-id",
        additional_claims={"org_id": "test-org-id", "role": "owner"},
    )
    print("Test Token:")
    print(test_token)
    print("\nDecoded:")
    decoded = decode_token(test_token)
    print(decoded)
