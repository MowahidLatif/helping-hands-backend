from flask import Flask
import os
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from datetime import timedelta
from app.routes import auth_bp, core, user, orgs

# from app.routes import user, campaign, donation, media, auth

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)

    JWTManager(app)

    @app.errorhandler(422)
    def handle_unprocessable(e):
        return {"error": "unprocessable request"}, 422

    @app.errorhandler(401)
    def handle_unauth(e):
        # flask-jwt-extended will also add its own messages; this keeps it clean
        return {"error": "unauthorized"}, 401

    app.config["DB_SETTINGS"] = {
        "host": os.getenv("DB_HOST"),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": os.getenv("DB_PORT"),
    }

    # app.register_blueprint(user, url_prefix="/api/users")

    # app.register_blueprint(campaign, url_prefix="/api/campaigns")
    # app.register_blueprint(donation, url_prefix="/api/donations")
    # app.register_blueprint(media, url_prefix="/api/media")

    # app.register_blueprint(auth_bp, url_prefix="/api/auth")
    # app.register_blueprint(core)

    app.register_blueprint(core)
    app.register_blueprint(user, url_prefix="/api/users")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(orgs)

    return app
