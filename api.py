#!/usr/bin/env python3
"""
Web Dashboard for GoldGen Auto Poster
Simple Flask API Entrypoint
"""

from flask import Flask
from flask_cors import CORS
from controllers.routes import bp
from core.database import init_db

app = Flask(__name__)
CORS(app)
app.secret_key = 'goldgen-dashboard-secret-key-2026'

app.register_blueprint(bp)

# Initialize database tables
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18794, debug=False)
