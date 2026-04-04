# app/__init__.py
import os
import json
import time
import uuid
import logging
from flask import Flask, request, g
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from datetime import timedelta
from flask_cors import CORS

from app.routes import (
    auth_bp,
    core,
    orgs,
    campaigns,
    media_bp,
    donations_bp,
    webhooks_bp,
    public,
    admin_bp,
    contact_bp,
)
from app.routes.platform_routes import platform_bp
from app.realtime import init_socketio
from app.utils.metrics import REQUEST_COUNT, REQUEST_DURATION_SECONDS, RATE_LIMIT_HITS

load_dotenv(dotenv_path=".env")

_DEV_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _is_production() -> bool:
    env = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development").lower()
    return env in {"prod", "production"}


def _parse_cors_origins() -> list[str]:
    raw = (os.getenv("CORS_ALLOWED_ORIGINS") or "").strip()
    if not raw:
        return _DEV_CORS_ORIGINS
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


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
    logger = logging.getLogger("app.request")
    cors_origins = _parse_cors_origins()
    CORS(
        app,
        resources={r"/api/*": {"origins": cors_origins}},
        supports_credentials=True,
    )
    app.url_map.strict_slashes = False
    is_production = _is_production()

    if is_production and cors_origins == _DEV_CORS_ORIGINS:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must be set in production (comma-separated origins)."
        )

    if server_name:
        app.config["SERVER_NAME"] = server_name
        if not is_production:
            print(f"*** SERVER_NAME is {app.config['SERVER_NAME']!r}")

    # JWT
    jwt_secret = os.getenv("JWT_SECRET", "dev-secret")
    if is_production and (jwt_secret == "dev-secret" or len(jwt_secret) < 32):
        raise RuntimeError(
            "JWT_SECRET must be set to a strong value (>= 32 chars) in production."
        )
    app.config["JWT_SECRET_KEY"] = jwt_secret
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
    def _request_start():
        g.request_started_at = time.time()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    @app.before_request
    def _rate_limit():
        if os.getenv("RATE_LIMIT_ENABLED", "1") != "1" or default_limit <= 0:
            return
        if request.path == "/webhooks/stripe":
            return  # exempt Stripe webhooks
        key = f"global:{rate_limit_key()}"
        if is_rate_limited(key, default_limit):
            RATE_LIMIT_HITS.labels(path=request.path).inc()
            return rate_limit_exceeded_response(default_limit)

    @app.after_request
    def _request_end(response):
        started_at = getattr(g, "request_started_at", None)
        if started_at is not None:
            duration = max(0.0, time.time() - started_at)
            REQUEST_DURATION_SECONDS.labels(
                method=request.method, path=request.path
            ).observe(duration)
        REQUEST_COUNT.labels(
            method=request.method, path=request.path, status=str(response.status_code)
        ).inc()
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")

        if os.getenv("STRUCTURED_LOGGING", "1") == "1":
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": getattr(g, "request_id", None),
                        "method": request.method,
                        "path": request.path,
                        "status": response.status_code,
                        "remote_addr": request.remote_addr,
                        "duration_ms": (
                            round((time.time() - started_at) * 1000, 2)
                            if started_at is not None
                            else None
                        ),
                    }
                )
            )
        return response

    if os.getenv("REQUEST_DEBUG_LOGGING", "0") == "1":

        @app.before_request
        def _dbg_host():
            print(f"DBG host={request.host!r} path={request.path!r}")

    @app.get("/__ping")
    def __ping():
        return {"ok": True, "server_name": app.config.get("SERVER_NAME")}, 200

    app.register_blueprint(core)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(orgs)
    app.register_blueprint(campaigns, url_prefix="/api/campaigns")
    app.register_blueprint(media_bp)
    app.register_blueprint(donations_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(public)
    app.register_blueprint(admin_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(platform_bp)

    if os.getenv("PRINT_URL_MAP", "0") == "1":
        print("\n=== URL MAP ===")
        for rule in app.url_map.iter_rules():
            print(
                f"{rule!s:40} | endpoint={rule.endpoint:30} | subdomain={getattr(rule, 'subdomain', None)}"
            )
        print("================\n")

    init_socketio(app)
    return app
