#!/usr/bin/env python3
"""
Perbaiki fb_post_id lama: ID FOTO -> ID POSTINGAN.

Latar belakang:
Endpoint /photos mengembalikan 'id' (objek foto) dan 'post_id' (postingan di
feed). Versi lama menyimpan 'id', padahal semua pembacaan balik memakai /posts
yang mengembalikan format "PAGEID_POSTID". Akibatnya join selalu gagal:
Vision AI tidak pernah dapat gambar, hook_type selalu "Unknown", dan sebagian
baris engagement_cache jadi yatim.

Script ini menanyakan page_story_id tiap foto ke Facebook, lalu memperbarui:
  1. posts.fb_post_id
  2. engagement_cache.fb_post_id  (ikut dipetakan supaya data pembelajaran
     layout yang sudah terkumpul TIDAK hilang)

Pakai:
    python scripts/backfill_post_ids.py            # periksa saja (dry run)
    python scripts/backfill_post_ids.py --apply    # tulis perubahan
"""

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG_PATH, DB_PATH  # noqa: E402
from core.database import get_db_connection  # noqa: E402


def looks_like_photo_id(value):
    """ID postingan selalu berbentuk PAGEID_POSTID; ID foto tidak punya '_'"""
    return bool(value) and '_' not in str(value)


def main():
    apply_changes = '--apply' in sys.argv

    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    tokens = {p['page_id']: p.get('access_token') for p in config.get('fanspages', [])}

    conn = get_db_connection()
    rows = conn.execute('''
        SELECT id, page_id, page_name, fb_post_id
        FROM posts
        WHERE status = 'success' AND fb_post_id IS NOT NULL
        ORDER BY id DESC
    ''').fetchall()

    targets = [r for r in rows if looks_like_photo_id(r['fb_post_id'])]
    print(f"Total post sukses      : {len(rows)}")
    print(f"Masih memakai ID foto  : {len(targets)}")
    print(f"Sudah benar            : {len(rows) - len(targets)}\n")

    if not targets:
        print("✅ Tidak ada yang perlu diperbaiki.")
        conn.close()
        return

    if apply_changes:
        backup = Path(str(DB_PATH) + f".backup_postid_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy(DB_PATH, backup)
        print(f"🛟 Cadangan database: {backup.name}\n")

    mapping = {}
    gagal = 0

    for i, row in enumerate(targets, 1):
        token = tokens.get(row['page_id'])
        if not token:
            gagal += 1
            continue
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v18.0/{row['fb_post_id']}",
                params={'access_token': token, 'fields': 'page_story_id'},
                timeout=30
            ).json()
            story_id = resp.get('page_story_id')
            if story_id:
                mapping[row['fb_post_id']] = story_id
            else:
                gagal += 1
                err = (resp.get('error') or {}).get('message', 'tidak ada page_story_id')
                if gagal <= 3:
                    print(f"   ⚠️  {row['fb_post_id']}: {str(err)[:70]}")
        except Exception as e:
            gagal += 1
            if gagal <= 3:
                print(f"   ⚠️  {row['fb_post_id']}: {type(e).__name__}")

        if i % 25 == 0:
            print(f"   ... {i}/{len(targets)} diperiksa")
        time.sleep(0.15)  # jangan menghajar Graph API

    print(f"\nBerhasil dipetakan : {len(mapping)}")
    print(f"Gagal / dilewati   : {gagal}")

    if mapping:
        contoh = list(mapping.items())[:3]
        print("\nContoh pemetaan:")
        for photo_id, story_id in contoh:
            print(f"   {photo_id}  ->  {story_id}")

    if not apply_changes:
        print("\n(dry run — tambahkan --apply untuk menulis perubahan)")
        conn.close()
        return

    diperbarui_posts = 0
    diperbarui_cache = 0

    for photo_id, story_id in mapping.items():
        # 1. Tabel posts
        conn.execute('UPDATE posts SET fb_post_id = ? WHERE fb_post_id = ?', (story_id, photo_id))
        diperbarui_posts += 1

        # 2. engagement_cache — ikut dipetakan supaya data layout tidak hilang.
        #    Kalau baris tujuan sudah ada (diisi dari /posts), gabungkan dengan
        #    mengambil angka tertinggi, lalu buang baris duplikatnya.
        lama = conn.execute('SELECT likes, comments FROM engagement_cache WHERE fb_post_id = ?', (photo_id,)).fetchone()
        if lama:
            baru = conn.execute('SELECT likes, comments FROM engagement_cache WHERE fb_post_id = ?', (story_id,)).fetchone()
            if baru:
                conn.execute('''
                    UPDATE engagement_cache SET likes = ?, comments = ?, cached_at = CURRENT_TIMESTAMP
                    WHERE fb_post_id = ?
                ''', (max(lama['likes'] or 0, baru['likes'] or 0),
                      max(lama['comments'] or 0, baru['comments'] or 0), story_id))
                conn.execute('DELETE FROM engagement_cache WHERE fb_post_id = ?', (photo_id,))
            else:
                conn.execute('UPDATE engagement_cache SET fb_post_id = ? WHERE fb_post_id = ?', (story_id, photo_id))
            diperbarui_cache += 1

    conn.commit()

    total = conn.execute('SELECT COUNT(*) FROM engagement_cache').fetchone()[0]
    cocok = conn.execute('''
        SELECT COUNT(*) FROM engagement_cache ec JOIN posts p ON p.fb_post_id = ec.fb_post_id
    ''').fetchone()[0]
    conn.close()

    print(f"\n✅ posts diperbarui           : {diperbarui_posts}")
    print(f"✅ engagement_cache dipetakan : {diperbarui_cache}")
    print(f"📊 engagement_cache cocok     : {cocok}/{total} (sebelumnya banyak yang yatim)")


if __name__ == '__main__':
    main()
