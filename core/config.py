import os
import secrets
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
IMAGES_DIR = BASE_DIR / "generated_images"

DB_PATH = DATA_DIR / "posts.db"
CONFIG_PATH = DATA_DIR / "config.json"
SECRET_KEY_PATH = DATA_DIR / "secret.key"

# Application configuration
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN", "888888")
if DASHBOARD_PIN == "888888":
    # Sengaja tanpa emoji: modul ini diimpor paling awal, dan konsol non-UTF8
    # (mis. cp1252 di Windows) akan melempar UnicodeEncodeError saat import.
    print("WARNING: DASHBOARD_PIN masih memakai nilai default. "
          "Set environment variable DASHBOARD_PIN untuk mengamankan dashboard.")


def _load_or_create_secret_key():
    """Secret key dari environment; kalau tidak ada, generate sekali lalu simpan.

    Tidak lagi memakai nilai hardcoded — session cookie yang ditandatangani dengan
    kunci yang ada di source code bisa dipalsukan siapa saja.
    """
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key

    try:
        if SECRET_KEY_PATH.exists():
            key = SECRET_KEY_PATH.read_text().strip()
            if key:
                return key

        key = secrets.token_hex(32)
        DATA_DIR.mkdir(exist_ok=True)
        SECRET_KEY_PATH.write_text(key)
        try:
            SECRET_KEY_PATH.chmod(0o600)
        except Exception:
            pass  # Windows / filesystem tanpa dukungan chmod
        print(f"Secret key baru dibuat di {SECRET_KEY_PATH}")
        return key
    except Exception as e:
        # Fallback terakhir: kunci acak per-proses (session hilang saat restart)
        print(f"WARNING: Gagal menyimpan secret key ({e}), memakai kunci acak sementara")
        return secrets.token_hex(32)


SECRET_KEY = _load_or_create_secret_key()
