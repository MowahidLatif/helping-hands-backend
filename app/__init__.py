from flask import Flask
import os
from dotenv import load_dotenv
from app.routes import user
# from app.routes import user, campaign, donation, media

load_dotenv()

def create_app():
    app = Flask(__name__)

    app.config['DB_SETTINGS'] = {
        'host': os.getenv('DB_HOST'),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'port': os.getenv('DB_PORT')
    }

    app.register_blueprint(user, url_prefix="/api/users")
    # app.register_blueprint(campaign, url_prefix="/api/campaigns")
    # app.register_blueprint(donation, url_prefix="/api/donations")
    # app.register_blueprint(media, url_prefix="/api/media")

    return app
