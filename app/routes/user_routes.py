from flask import Blueprint, request, jsonify
from app.services.user_service import (
    create_user,
    update_user,
    reset_password,
    get_user_by_id,
    fetch_users,
)

user = Blueprint("user", __name__)


@user.route("/users", methods=["GET"])
def list_users():
    users = fetch_users()
    return jsonify(users)


@user.route("/users", methods=["POST"])
def register_user():
    data = request.json
    return create_user(data)


@user.route("/users/<int:user_id>", methods=["PUT"])
def edit_user(user_id):
    data = request.json
    return update_user(user_id, data)


@user.route("/users/<int:user_id>/reset-password", methods=["PUT"])
def user_reset_password(user_id):
    data = request.json
    return reset_password(user_id, data)


@user.route("/users/<int:user_id>", methods=["GET"])
def fetch_user(user_id):
    return get_user_by_id(user_id)
