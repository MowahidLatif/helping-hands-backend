from flask import Flask
import os
from dotenv import load_dotenv
from app.routes.user_routes import user_bp

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

    app.register_blueprint(user_bp, url_prefix="/api")

    return app
