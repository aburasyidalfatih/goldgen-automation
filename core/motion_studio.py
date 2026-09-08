"""Isolated Motion Studio persistence and read-only topic access.

This module deliberately uses its own SQLite database and filesystem paths.
It does not import or mutate the image poster database, topic rotation state,
or auto-poster queues.
"""

import json
import sqlite3
from contextlib import contextmanager
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import BASE_DIR

MOTION_DIR = BASE_DIR / "motion_studio"
MOTION_DATA_DIR = MOTION_DIR / "data"
MOTION_ASSETS_DIR = MOTION_DIR / "assets"
MOTION_RENDERS_DIR = MOTION_DIR / "renders"
MOTION_DB_PATH = MOTION_DATA_DIR / "motion_jobs.db"

def motion_db(path):
    """Buka SQLite, selesaikan transaksinya, lalu TUTUP koneksinya.

    `with sqlite3.connect(path) as conn` hanya menutup transaksi — koneksinya
    tetap terbuka. Di Windows handle yang menganggur itu membuat berkas
    database tidak bisa dihapus, sehingga tes Motion Studio gagal di sana
    (WinError 32) padahal lulus di Linux. Di worker yang berjalan lama, setiap
    pemanggilan meninggalkan satu handle menggantung.
    """
    return _motion_db(path)


@contextmanager
def _motion_db(path):
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()

TOPICS_PATH = BASE_DIR / "data" / "topics.json"


def init_motion_storage():
    """Create only Motion Studio storage; safe to call during app startup."""
    for path in (MOTION_DATA_DIR, MOTION_ASSETS_DIR, MOTION_RENDERS_DIR):
        path.mkdir(parents=True, exist_ok=True)
    with motion_db(MOTION_DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS motion_jobs (
                id TEXT PRIMARY KEY,
                topic_id INTEGER NOT NULL,
                topic_headline TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 60,
                aspect_ratio TEXT NOT NULL DEFAULT '9:16',
                output_path TEXT,
                error_message TEXT,
                progress_percent INTEGER NOT NULL DEFAULT 0,
                current_stage TEXT NOT NULL DEFAULT 'draft',
                current_detail TEXT,
                scene_current INTEGER NOT NULL DEFAULT 0,
                scene_total INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(motion_jobs)").fetchall()}
        migrations = {
            "progress_percent": "ALTER TABLE motion_jobs ADD COLUMN progress_percent INTEGER NOT NULL DEFAULT 0",
            "current_stage": "ALTER TABLE motion_jobs ADD COLUMN current_stage TEXT NOT NULL DEFAULT 'draft'",
            "current_detail": "ALTER TABLE motion_jobs ADD COLUMN current_detail TEXT",
            "scene_current": "ALTER TABLE motion_jobs ADD COLUMN scene_current INTEGER NOT NULL DEFAULT 0",
            "scene_total": "ALTER TABLE motion_jobs ADD COLUMN scene_total INTEGER NOT NULL DEFAULT 0",
        }
        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)
    from core.motion_assets import init_asset_storage
    init_asset_storage()


def list_topics():
    """Read the existing topic catalog without writing to it.

    Gerbang kurasi yang sama dengan pipeline Facebook. Sebelumnya seluruh isi
    topics.json dikembalikan mentah — 142 topik, sementara hanya 136 yang lolos
    `allowed()`. Akibatnya Motion Studio bisa membuat video dari topik yang
    justru sudah ditolak untuk diposting.
    """
    with TOPICS_PATH.open("r", encoding="utf-8") as handle:
        topics = json.load(handle)
    try:
        from core.topic_catalog import allowed
        topics = [topic for topic in topics if allowed(topic)]
    except Exception:
        # Katalog yang tidak bisa dibaca tidak boleh mengosongkan studio
        pass
    return [
        {
            "id": topic.get("id"),
            "headline": topic.get("headline", "Untitled topic"),
            "subtitle": topic.get("subtitle", ""),
            "list_points": topic.get("list_points", []),
            "reference_url": topic.get("reference_url"),
        }
        for topic in topics
    ]


def create_job(topic_id):
    topic = next((item for item in list_topics() if item["id"] == topic_id), None)
    if not topic:
        raise ValueError("Topic tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    job_id = uuid.uuid4().hex
    with motion_db(MOTION_DB_PATH) as conn:
        conn.execute(
            """INSERT INTO motion_jobs
               (id, topic_id, topic_headline, status, created_at, updated_at)
               VALUES (?, ?, ?, 'draft', ?, ?)""",
            (job_id, topic["id"], topic["headline"], now, now),
        )
    return get_job(job_id)


def list_jobs(limit=20):
    with motion_db(MOTION_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM motion_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_job(job_id):
    with motion_db(MOTION_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM motion_jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job(job_id, **fields):
    allowed = {'status', 'output_path', 'error_message', 'progress_percent', 'current_stage', 'current_detail', 'scene_current', 'scene_total'}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_job(job_id)
    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    assignments = ', '.join(f'{key} = ?' for key in updates)
    values = list(updates.values()) + [job_id]
    with motion_db(MOTION_DB_PATH) as conn:
        conn.execute(f'UPDATE motion_jobs SET {assignments} WHERE id = ?', values)
    return get_job(job_id)


def queue_draft_jobs(limit=20):
    now = datetime.now(timezone.utc).isoformat()
    with motion_db(MOTION_DB_PATH) as conn:
        rows = conn.execute("SELECT id FROM motion_jobs WHERE status = 'draft' ORDER BY created_at ASC LIMIT ?", (limit,)).fetchall()
        if rows:
            conn.executemany("UPDATE motion_jobs SET status = 'queued', updated_at = ? WHERE id = ?", [(now, row[0]) for row in rows])
    return [get_job(row[0]) for row in rows]
