#!/usr/bin/env python3
"""
Terapkan rekomendasi jam posting ke data/config.json.

Aturannya ada di core/schedule_tuning.py dan juga dijalankan otomatis oleh
worker setiap Senin 08:30 WIB (matikan dengan "auto_best_hours": false).

Pakai:
    python scripts/apply_best_hours.py            # tampilkan usulan saja
    python scripts/apply_best_hours.py --apply    # tulis ke config.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG_PATH  # noqa: E402
from core.schedule_tuning import apply_best_hours  # noqa: E402


def main():
    apply_changes = '--apply' in sys.argv
    for entry in apply_best_hours(CONFIG_PATH, apply=apply_changes):
        print("=" * 70)
        print(f"📘 {entry['page']}  — jadwal sekarang: {entry['before']}")
        print(f"   {entry['reason']}")
        if entry['after']:
            print(f"   ✅ jadwal baru: {entry['after']}")
    print("=" * 70)
    if not apply_changes:
        print("(usulan saja — tambahkan --apply untuk menerapkan)")


if __name__ == '__main__':
    main()
