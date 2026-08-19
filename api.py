#!/usr/bin/env python3
"""
Web Dashboard for GoldGen Auto Poster
Simple Flask API Entrypoint
"""

import os

from flask import Flask
from flask_cors import CORS

from controllers.routes import bp
from core.config import SECRET_KEY
from core.database import init_db

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = SECRET_KEY

app.register_blueprint(bp)

# Initialize database tables
init_db()

# Start internal job worker (APScheduler)
from core.worker import start_worker
start_worker()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 18794))
    host = os.getenv('HOST', '0.0.0.0')

    # Flask dev server bukan untuk produksi; pakai waitress kalau tersedia.
    # Single process — penting supaya APScheduler tidak jalan dobel.
    try:
        from waitress import serve
        print(f"🚀 GoldGen dashboard berjalan di http://{host}:{port} (waitress)")
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        print("⚠️  waitress belum terpasang, fallback ke Flask dev server")
        app.run(host=host, port=port, debug=False)
