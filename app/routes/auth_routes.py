from flask import Blueprint, request, jsonify
from app.services.auth_service import login_user, signup_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    response = login_user(data)
    return jsonify(response), (200 if 'token' in response else 401)


@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.json
    response = signup_user(data)
    return jsonify(response), (201 if 'id' in response else 400)
