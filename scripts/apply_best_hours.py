#!/usr/bin/env python3
"""
Terapkan rekomendasi jam posting ke data/config.json.

CATATAN PENTING soal keterbatasan data:
Bot hanya punya data untuk jam-jam yang memang pernah dipakai posting. Jam yang
tidak pernah dicoba tidak punya bukti apa pun — bukan berarti jelek. Karena itu
script ini hanya MENUKAR jam terburuk dengan jam terbaik yang sudah terbukti,
dan tidak akan menghapus semua jam sekaligus.

Jumlah slot per page tidak berubah, jadi frekuensi posting tetap sama.

Pakai:
    python scripts/apply_best_hours.py            # tampilkan usulan saja
    python scripts/apply_best_hours.py --apply    # tulis ke config.json
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG_PATH  # noqa: E402
from learning_insights import timing_report  # noqa: E402

MIN_SAMPLES = 3   # jam dengan sampel di bawah ini belum bisa dinilai
MAX_CHANGES = 1   # ubah maksimal 1 slot per page per eksekusi — perubahan bertahap


def main():
    apply_changes = '--apply' in sys.argv

    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    changed = False

    for page in config.get('fanspages', []):
        name = page.get('name', '?')
        schedule = sorted(page.get('schedule_hours') or [])
        print("=" * 70)
        print(f"📘 {name}  — jadwal sekarang: {schedule}")

        if not schedule:
            print("   (memakai interval_hours, bukan jadwal per jam — dilewati)")
            continue

        stats = {t['hour']: t for t in timing_report(page['page_id']) if t['n'] >= MIN_SAMPLES}
        if len(stats) < 2:
            print(f"   data belum cukup (butuh >= {MIN_SAMPLES} post per jam)")
            continue

        candidates = [h for h in stats if h not in schedule]
        if not candidates:
            print("   tidak ada jam alternatif yang punya data — jadwal dipertahankan")
            continue

        best = max(candidates, key=lambda h: stats[h]['confident_score'])
        scheduled_with_data = [h for h in schedule if h in stats]

        if scheduled_with_data:
            worst = min(scheduled_with_data, key=lambda h: stats[h]['confident_score'])
            if stats[best]['confident_score'] <= stats[worst]['confident_score']:
                print(f"   jadwal sudah optimal menurut data "
                      f"(terburuk {worst:02d}:00 = {stats[worst]['confident_score']:.0f} "
                      f"masih >= kandidat terbaik {best:02d}:00 = {stats[best]['confident_score']:.0f})")
                continue
            alasan_buang = f"skor {stats[worst]['confident_score']:.0f}, {stats[worst]['n']} post"
        else:
            # Kasus paling sering & paling berharga: jam yang dijadwalkan sekarang
            # belum punya bukti sama sekali (mis. jadwal baru diubah), sementara
            # ada jam lain yang sudah terbukti bagus dari riwayat.
            worst = schedule[0]
            alasan_buang = "belum ada bukti untuk jam ini"

        print(f"   USULAN: buang {worst:02d}:00 ({alasan_buang})")
        print(f"           pakai {best:02d}:00 (skor {stats[best]['confident_score']:.0f}, "
              f"{stats[best]['n']} post, rata-rata {stats[best]['avg']:.0f})")

        if apply_changes:
            new_schedule = sorted([h for h in schedule if h != worst] + [best])
            page['schedule_hours'] = new_schedule[:len(schedule)] if len(new_schedule) > len(schedule) else new_schedule
            print(f"   ✅ jadwal baru: {page['schedule_hours']}")
            changed = True

    if apply_changes and changed:
        backup = Path(str(CONFIG_PATH) + f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy(CONFIG_PATH, backup)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        print("=" * 70)
        print(f"✅ config.json diperbarui (cadangan: {backup.name})")
    elif not apply_changes:
        print("=" * 70)
        print("(usulan saja — tambahkan --apply untuk menerapkan)")


if __name__ == '__main__':
    main()
