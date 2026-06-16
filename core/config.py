import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
IMAGES_DIR = BASE_DIR / "generated_images"

DB_PATH = DATA_DIR / "posts.db"
CONFIG_PATH = DATA_DIR / "config.json"

# Application configuration
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN", "888888")
SECRET_KEY = os.getenv("SECRET_KEY", "goldgen-dashboard-secret-key-2026")
