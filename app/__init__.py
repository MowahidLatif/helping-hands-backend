# app/__init__.py
import os
from flask import Flask, request
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from datetime import timedelta
from flask_cors import CORS

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
    admin_bp,
)
from app.realtime import init_socketio

load_dotenv(dotenv_path=".env")


def create_app():
    # SERVER_NAME must match request Host or Flask returns 404.
    server_name = os.getenv("SERVER_NAME")
    # If helpinghands.local, use 127.0.0.1:PORT so requests to localhost work without -H Host
    if server_name and "helpinghands.local" in server_name:
        port = os.getenv("PORT", "5050")
        server_name = f"127.0.0.1:{port}"
    # if "." in server_name:
    #     app = Flask(
    #         __name__,
    #         host_matching=True,
    #         static_host=server_name
    #     )
    # else:
    #     app = Flask(__name__)

    app = Flask(__name__, subdomain_matching=True)
    CORS(
        app,
        resources={
            r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}
        },
        supports_credentials=True,
    )
    app.url_map.strict_slashes = False
    if server_name:
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

    # Rate limiting middleware (in-memory; see app.utils.rate_limit)
    from app.utils.rate_limit import (
        rate_limit_key,
        is_rate_limited,
        rate_limit_exceeded_response,
    )

    default_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "200"))

    @app.before_request
    def _rate_limit():
        if os.getenv("RATE_LIMIT_ENABLED", "1") != "1" or default_limit <= 0:
            return
        if request.path == "/webhooks/stripe":
            return  # exempt Stripe webhooks
        key = f"global:{rate_limit_key()}"
        if is_rate_limited(key, default_limit):
            return rate_limit_exceeded_response(default_limit)

    @app.before_request
    def _dbg_host():
        print(f"DBG host={request.host!r} path={request.path!r}")

    @app.get("/__ping")
    def __ping():
        return {"ok": True, "server_name": app.config.get("SERVER_NAME")}, 200

    app.register_blueprint(core)
    app.register_blueprint(user, url_prefix="/api/users")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(orgs)
    app.register_blueprint(campaigns, url_prefix="/api/campaigns")
    app.register_blueprint(media_bp)
    app.register_blueprint(donations_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(public)
    app.register_blueprint(admin_bp)

    print("\n=== URL MAP ===")
    for rule in app.url_map.iter_rules():
        print(
            f"{rule!s:40} | endpoint={rule.endpoint:30} | subdomain={getattr(rule, 'subdomain', None)}"
        )
    print("================\n")

    init_socketio(app)
    return app
