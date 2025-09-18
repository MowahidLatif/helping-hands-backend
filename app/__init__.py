# app/__init__.py
import os
from flask import Flask, request
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from datetime import timedelta

# from datetime_timedelta import timedelta

from app.routes import (
    auth_bp,
    core,
    user,
    orgs,
    campaigns,
    media_bp,
    donations_bp,
    webhooks_bp,
    public,
)
from app.realtime import init_socketio

# load_dotenv()
load_dotenv(dotenv_path=".env")


def create_app():
    server_name = os.getenv("SERVER_NAME") or "helpinghands.local"
    # if "." in server_name:
    #     app = Flask(
    #         __name__,
    #         host_matching=True,
    #         static_host=server_name
    #     )
    # else:
    #     app = Flask(__name__)

    app = Flask(__name__, subdomain_matching=True)

    app.url_map.strict_slashes = False
    app.config["SERVER_NAME"] = server_name
    print(f"*** SERVER_NAME is {app.config['SERVER_NAME']!r}")

    # JWT
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "dev-secret")
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
    JWTManager(app)

    @app.before_request
    def _dbg_host():
        print(f"DBG host={request.host!r} path={request.path!r}")

    @app.get("/__ping")
    def __ping():
        return {"ok": True, "server_name": app.config["SERVER_NAME"]}, 200

    app.register_blueprint(core)
    app.register_blueprint(user, url_prefix="/api/users")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(orgs)
    app.register_blueprint(campaigns, url_prefix="/api/campaigns")
    app.register_blueprint(media_bp)
    app.register_blueprint(donations_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(public)  # relies on subdomain

    print("\n=== URL MAP ===")
    for rule in app.url_map.iter_rules():
        print(
            f"{rule!s:40} | endpoint={rule.endpoint:30} | subdomain={getattr(rule, 'subdomain', None)}"
        )
    print("================\n")

    init_socketio(app)
    return app


# import os
# from flask import Flask
# from dotenv import load_dotenv
# from flask_jwt_extended import JWTManager
# from datetime import timedelta
# from app.routes import (auth_bp, core, user, orgs, campaigns, media_bp, donations_bp, webhooks_bp, public)
# from app.realtime import init_socketio

# load_dotenv()

# def create_app():
#     server_name = os.getenv("SERVER_NAME", "helpinghands.local:5050")

#     # ✅ provide static_host when host_matching=True
#     app = Flask(__name__, host_matching=True, static_host=server_name)
#     app.url_map.strict_slashes = False
#     app.config["SERVER_NAME"] = server_name

#     # ... (rest unchanged)
#     app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")
#     app.config["JWT_TOKEN_LOCATION"] = ["headers"]
#     app.config["JWT_HEADER_NAME"] = "Authorization"
#     app.config["JWT_HEADER_TYPE"] = "Bearer"
#     app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
#     app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
#     JWTManager(app)

#     @app.errorhandler(422)
#     def handle_unprocessable(e): return {"error": "unprocessable request"}, 422

#     @app.errorhandler(401)
#     def handle_unauth(e): return {"error": "unauthorized"}, 401

#     app.config["DB_SETTINGS"] = {
#         "host": os.getenv("DB_HOST"),
#         "database": os.getenv("DB_NAME"),
#         "user": os.getenv("DB_USER"),
#         "password": os.getenv("DB_PASSWORD"),
#         "port": os.getenv("DB_PORT"),
#     }

#     app.register_blueprint(core)
#     app.register_blueprint(user, url_prefix="/api/users")
#     app.register_blueprint(auth_bp, url_prefix="/api/auth")
#     app.register_blueprint(orgs)
#     app.register_blueprint(campaigns, url_prefix="/api/campaigns")
#     app.register_blueprint(media_bp)
#     app.register_blueprint(donations_bp)
#     app.register_blueprint(webhooks_bp)

#     # subdomain routes
#     app.register_blueprint(public)

#     init_socketio(app)
#     return app


# keep in case you need it for day 1 fixes later
# @app.get("/__ping")
# def __ping():
#     return {"ok": True, "server_name": app.config["SERVER_NAME"]}, 200
