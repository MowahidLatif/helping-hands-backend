from .auth_routes import auth_bp
from .core_routes import core
from .org_routes import orgs
from .campaign_routes import campaigns
from .media_routes import media_bp
from .donation_routes import donations_bp
from .webhook_routes import webhooks_bp
from .public_routes import public
from .admin_routes import admin_bp
from .contact_routes import contact_bp

__all__ = [
    "auth_bp",
    "core",
    "orgs",
    "campaigns",
    "media_bp",
    "donations_bp",
    "webhooks_bp",
    "public",
    "admin_bp",
    "contact_bp",
]
