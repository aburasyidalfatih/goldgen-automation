"""Cadangan harian database dan konfigurasi.

Seluruh riwayat posting dan data pembelajaran ada di satu file SQLite. Tanpa
cadangan, satu migrasi yang salah atau file yang rusak menghapus bukti
berbulan-bulan. Cadangan disimpan di volume data yang sama (data/backups):
melindungi dari kerusakan file dan kesalahan aplikasi, BUKAN dari hilangnya
server. Salin folder itu ke tempat lain secara berkala bila perlu.
"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

KEEP_DAYS = 7


def backup_database(db_path, config_path=None, dest_dir=None, keep=KEEP_DAYS, now=None):
    """Salin database memakai backup API SQLite (aman saat DB sedang dipakai)."""
    db_path = Path(db_path)
    dest_dir = Path(dest_dir or db_path.parent / 'backups')
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime('%Y%m%d')
    target = dest_dir / f'posts-{stamp}.db'
    temporary = target.with_suffix('.db.tmp')
    source = sqlite3.connect(str(db_path))
    try:
        copy = sqlite3.connect(str(temporary))
        try:
            source.backup(copy)
        finally:
            copy.close()
    finally:
        source.close()
    temporary.replace(target)
    if config_path and Path(config_path).is_file():
        shutil.copy2(config_path, dest_dir / f'config-{stamp}.json')
    for pattern in ('posts-*.db', 'config-*.json'):
        for old in sorted(dest_dir.glob(pattern))[:-keep]:
            old.unlink(missing_ok=True)
    return target
