from app.models.user import get_all_users

def fetch_users():
    users = get_all_users()
    return users
