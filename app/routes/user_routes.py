from flask import Blueprint, jsonify
from app.services.user_service import fetch_users

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
def list_users():
    users = fetch_users()
    return jsonify(users)
