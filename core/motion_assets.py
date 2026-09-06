"""Isolated asset registry for Motion Studio."""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.motion_studio import MOTION_ASSETS_DIR, MOTION_DATA_DIR

ASSET_DB_PATH = MOTION_DATA_DIR / "assets.db"


def init_asset_storage():
    MOTION_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ASSET_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, source_path TEXT NOT NULL, asset_type TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
            sha256 TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
        if "source_path" not in columns:
            conn.execute("ALTER TABLE assets ADD COLUMN source_path TEXT NOT NULL DEFAULT ''")


def register_asset(path, asset_type="graphic", tags=(), status="draft"):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    asset_id = digest[:16]
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(ASSET_DB_PATH) as conn:
        conn.execute("""INSERT OR REPLACE INTO assets
            (id, filename, source_path, asset_type, tags, status, sha256, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, source.name, str(source.resolve()), asset_type, ",".join(tags), status, digest, now))
    return asset_id


def search_assets(query="", asset_type=None, approved_only=False):
    clauses, values = [], []
    if query:
        clauses.append("(filename LIKE ? OR tags LIKE ?)")
        values.extend([f"%{query}%", f"%{query}%"])
    if asset_type:
        clauses.append("asset_type = ?")
        values.append(asset_type)
    if approved_only:
        clauses.append("status = 'approved'")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with sqlite3.connect(ASSET_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM assets {where} ORDER BY created_at DESC", values).fetchall()
    return [dict(row) for row in rows]


def scan_existing_images(root):
    """Register existing GoldGen images without copying or modifying them."""
    root = Path(root)
    if not root.is_dir():
        return []
    registered = []
    for path in root.rglob("*"):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and path.is_file():
            registered.append(register_asset(path, asset_type="existing-image", tags=("goldgen", "reusable"), status="approved"))
    return registered
