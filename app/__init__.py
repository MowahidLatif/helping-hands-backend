from flask import Flask
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)

    # DB Connection
    app.config['DB_CONNECTION'] = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )

    # Import routes
    from .routes import main
    app.register_blueprint(main)

    return app
