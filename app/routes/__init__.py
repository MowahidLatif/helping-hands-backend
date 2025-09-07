from .auth_routes import auth_bp
from .user_routes import user
from .core_routes import core
from .org_routes import orgs
from .campaign_routes import campaigns

__all__ = ["auth_bp", "user", "core", "orgs", "campaigns"]
