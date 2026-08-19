#!/usr/bin/env python3
"""
Bersihkan topic_preferences dari data sampah warisan lama.

Yang dihapus:
  1. Baris dengan page_id NULL (sisa era sebelum preferensi dipisah per page —
     tidak pernah terbaca lagi karena semua query memfilter per page_id)
  2. Hook yang tidak dikenali sistem, mis. "hook: unknown",
     "hook: unknown (high engagement outliers)", "hook: viral success".
     Label seperti ini tidak bisa dieksekusi AI dan hanya menggeser sinyal asli.
  3. Nilai placeholder seperti "none identified" / "n/a"

Kode sekarang sudah menyaring semua ini saat membaca DAN saat menulis, jadi
pembersihan ini opsional — gunanya membuat tabel & dashboard enak dibaca.

Pakai:
    python scripts/cleanup_preferences.py           # tampilkan saja (dry run)
    python scripts/cleanup_preferences.py --apply   # benar-benar hapus
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comment_analyzer import _is_meaningful, normalize_hook  # noqa: E402
from core.database import get_db_connection  # noqa: E402


def main():
    apply_changes = '--apply' in sys.argv

    conn = get_db_connection()
    rows = conn.execute(
        'SELECT id, page_id, topic_keyword, boost_score FROM topic_preferences'
    ).fetchall()

    doomed = []
    for r in rows:
        kw = r['topic_keyword'] or ''
        if r['page_id'] is None:
            doomed.append((r, 'page_id kosong (tidak pernah terbaca)'))
        elif not _is_meaningful(kw):
            doomed.append((r, 'nilai placeholder'))
        elif kw.lower().startswith('hook:') and not normalize_hook(kw):
            doomed.append((r, 'hook tidak dikenali'))

    print(f"Total preferensi : {len(rows)}")
    print(f"Akan dihapus     : {len(doomed)}")
    print(f"Tersisa          : {len(rows) - len(doomed)}\n")

    if doomed:
        print(f"{'SKOR':<6}{'PAGE':<18}{'KEYWORD':<48} ALASAN")
        print("-" * 100)
        for r, why in sorted(doomed, key=lambda x: -(x[0]['boost_score'] or 0)):
            page = str(r['page_id'])[:16]
            print(f"{str(r['boost_score']):<6}{page:<18}{(r['topic_keyword'] or '')[:46]:<48} {why}")

    if not apply_changes:
        print("\n(dry run — tambahkan --apply untuk benar-benar menghapus)")
        conn.close()
        return

    if doomed:
        conn.executemany(
            'DELETE FROM topic_preferences WHERE id = ?',
            [(r['id'],) for r, _ in doomed]
        )
        conn.commit()
        print(f"\n✅ {len(doomed)} baris dihapus.")
    else:
        print("\n✅ Tidak ada yang perlu dibersihkan.")

    conn.close()


if __name__ == '__main__':
    main()
