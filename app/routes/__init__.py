# from app.routes.campaign_routes import campaign
# from app.routes.donation_routes import donation
# from app.routes.media_routes import media

# __all__ = ["user", "campaign", "donation", "media", "auth"]


# from app.routes.auth_routes import auth_bp
# from app.routes.core_routes import core
# from app.routes.user_routes import user
# __all__ = ["user", "auth_bp", "core"]

# from app.routes.auth_routes import auth_bp
# from app.routes.core_routes import core
# from app.routes.user_routes import user

# keep for now but if the new one works, delete all.
# from .auth_routes import auth_bp
# from .user_routes import user
# from .core_routes import core

# __all__ = ["auth_bp", "user", "core"]

from .auth_routes import auth_bp
from .user_routes import user
from .core_routes import core
from .org_routes import orgs

__all__ = ["auth_bp", "user", "core", "orgs"]
