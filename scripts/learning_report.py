#!/usr/bin/env python3
"""
Laporan pembelajaran bot: layout, editor AI, dan jam posting.

Pakai:
    python scripts/learning_report.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG_PATH  # noqa: E402
from learning_insights import full_report  # noqa: E402


def bar(value, scale):
    return '█' * max(0, min(30, int(value / scale))) if scale > 0 else ''


def main():
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    for page in full_report(config.get('fanspages', [])):
        print("=" * 78)
        print(f"📘 {page['page_name']}   (jadwal saat ini: {page['schedule_hours']})")
        print("=" * 78)

        # --- Layout ---
        print("\n🎨 LAYOUT — diurut dari yang paling terbukti (bukan sekadar rata-rata tertinggi)")
        if not page['layouts']:
            print("   belum ada data")
        else:
            scale = max((l['avg'] for l in page['layouts']), default=1) / 25 or 1
            print(f"   {'LAYOUT':<26}{'RATA2':>8}{'SAMPEL':>8}{'SKOR YAKIN':>12}")
            for l in page['layouts'][:8]:
                print(f"   {l['layout'][:25]:<26}{l['avg']:>8.0f}{l['n']:>8}{l['confident_score']:>12.0f}  {bar(l['confident_score'], scale)}")
            print("   * skor yakin = rata-rata dipotong sesuai ketidakpastian sampel kecil")

        # --- Editor ---
        e = page['editor']
        print(f"\n🕵️  EDITOR AI — {e['verdict']}")
        if e['r'] is not None:
            print(f"   korelasi skor vs engagement: {e['r']:+.2f} (dari {e['n']} post)")
            if e['avg_high'] is not None and e['avg_low'] is not None:
                print(f"   caption skor >=8 : {e['avg_high']:.0f} engagement")
                print(f"   caption skor <8  : {e['avg_low']:.0f} engagement")

        # --- Kepatuhan hook ---
        hc = page['hook_compliance']
        if hc['n'] == 0:
            print("\n🎯 KEPATUHAN HOOK — belum ada data "
                  "(kolom requested_hook baru terisi mulai posting berikutnya)")
        else:
            persen = hc['rasio'] * 100
            nilai = 'BAIK' if persen >= 70 else ('SEDANG' if persen >= 40 else 'BURUK — instruksi hook diabaikan')
            print(f"\n🎯 KEPATUHAN HOOK — {hc['patuh']}/{hc['n']} sesuai ({persen:.0f}%) — {nilai}")
            for c in hc['contoh']:
                print(f"   {'✅' if c['cocok'] else '❌'} diminta {c['diminta']:<12} -> keluar {c['keluar']}")

        # --- Jam posting ---
        print("\n⏰ JAM POSTING")
        if not page['timing']:
            print("   belum ada data")
        else:
            scale = max((t['avg'] for t in page['timing']), default=1) / 25 or 1
            for t in page['timing']:
                tanda = '⭐' if t['hour'] in (page['schedule_hours'] or []) else '  '
                print(f"   {tanda} {t['hour']:02d}:00  rata2 {t['avg']:>6.0f}  ({t['n']} post)  {bar(t['avg'], scale)}")
            rec = [h['hour'] for h in page['best_hours']]
            print(f"\n   ⭐ = jam yang sedang dijadwalkan")
            print(f"   Rekomendasi jam terbaik: {rec if rec else 'data belum cukup'}")
        print()


if __name__ == '__main__':
    main()
