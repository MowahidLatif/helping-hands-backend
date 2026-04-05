"""
Gunicorn configuration for production.

Flask-SocketIO requires eventlet worker class with a single worker process.
Scale horizontally (multiple containers) rather than vertically (more workers).
"""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5050')}"

# eventlet is required for Flask-SocketIO WebSocket support
worker_class = "eventlet"
workers = 1

timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

proc_name = "donation-backend"
