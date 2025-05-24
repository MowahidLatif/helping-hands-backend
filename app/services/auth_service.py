import jwt
import datetime
import bcrypt
from app.models.user import get_user_by_email, insert_user
from app.utils.jwt_helpers import generate_token

def login_user(data):
    email = data.get("email")
    password = data.get("password")

    user = get_user_by_email(email)
    if not user:
        return {"error": "User not found"}

    stored_hash = user[2] 
    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return {"error": "Invalid credentials"}

    token = generate_token(user[0]) 
    return {"token": token, "user_id": user[0]}


def signup_user(data):
    password = data.get("password")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    user_data = {
        "username": data.get("username"),
        "email": data.get("email"),
        "password_hash": hashed,
        "custom_domain": data.get("custom_domain")
    }

    return insert_user(user_data)
