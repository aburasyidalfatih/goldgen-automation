"""Isolated asset registry for Motion Studio."""

import hashlib
import sqlite3
import mimetypes
import json
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path

from core.motion_studio import MOTION_ASSETS_DIR, MOTION_DATA_DIR

ASSET_DB_PATH = MOTION_DATA_DIR / "assets.db"
EXTERNAL_ASSET_HOSTS = {"pexels.com", "www.pexels.com", "unsplash.com", "images.unsplash.com", "pixabay.com", "commons.wikimedia.org", "upload.wikimedia.org"}
COMMERCIAL_LICENSES = {"cc0", "pdm", "by", "by-sa"}


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
        for name in ("source_url", "license_name", "creator", "attribution", "origin"):
            if name not in columns:
                conn.execute(f"ALTER TABLE assets ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")


def register_asset(path, asset_type="graphic", tags=(), status="draft", source_url="", license_name="", creator="", attribution="", origin="local"):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    asset_id = digest[:16]
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(ASSET_DB_PATH) as conn:
        conn.execute("""INSERT OR REPLACE INTO assets
            (id, filename, source_path, asset_type, tags, status, sha256, created_at, source_url, license_name, creator, attribution, origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, source.name, str(source.resolve()), asset_type, ",".join(tags), status, digest, now, source_url, license_name, creator, attribution, origin))
    return asset_id


def import_external_asset(source_url, license_name, creator="", attribution="", tags=(), asset_type="external-image"):
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(host == allowed or host.endswith("." + allowed) for allowed in EXTERNAL_ASSET_HOSTS):
        raise ValueError("Sumber aset harus HTTPS dari provider yang diizinkan")
    if not license_name.strip():
        raise ValueError("Lisensi wajib diisi")
    request = Request(source_url, headers={"User-Agent": "GoldGen-Motion-AssetImporter/1.0"})
    with urlopen(request, timeout=20) as response:
        content_type = (response.headers.get_content_type() or "").lower()
        if not content_type.startswith("image/"):
            raise ValueError("URL bukan aset gambar")
        data = response.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Ukuran aset melebihi batas 10 MB")
    extension = mimetypes.guess_extension(content_type) or ".bin"
    digest = hashlib.sha256(data).hexdigest()
    destination = MOTION_ASSETS_DIR / f"external-{digest[:16]}{extension}"
    destination.write_bytes(data)
    asset_id = register_asset(destination, asset_type=asset_type, tags=tags, status="review", source_url=source_url, license_name=license_name.strip(), creator=creator.strip(), attribution=attribution.strip(), origin=host)
    return search_assets(approved_only=False)[0] if asset_id else None


def search_openverse(query, page_size=12):
    if not query.strip():
        return []
    params = urlencode({"q": query.strip(), "page_size": min(max(int(page_size), 1), 20), "mature": "false"})
    request = Request(f"https://api.openverse.org/v1/images/?{params}", headers={"User-Agent": "GoldGen-Motion/1.0"})
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    normalized = [{
        "id": item.get("id"), "title": item.get("title") or "Untitled",
        "thumbnail": item.get("thumbnail"), "url": item.get("url"),
        "landing_url": item.get("foreign_landing_url"), "creator": item.get("creator") or "",
        "license": item.get("license") or "unknown", "license_version": item.get("license_version") or "",
        "license_url": item.get("license_url") or "", "provider": item.get("provider") or "Openverse",
        "attribution": item.get("attribution") or ""
    } for item in payload.get("results", []) if item.get("url") and item.get("license", "").lower() in COMMERCIAL_LICENSES]
    return normalized


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
