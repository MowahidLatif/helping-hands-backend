from app.models.user import (
    get_all_users,
    insert_user,
    update_user_data,
    update_password,
    get_user,
)


def fetch_users():
    users = get_all_users()
    return users


def create_user(data):
    return insert_user(data)


def update_user(user_id, data):
    return update_user_data(user_id, data)


def reset_password(user_id, data):
    return update_password(user_id, data.get("new_password"))


def get_user_by_id(user_id):
    return get_user(user_id)
