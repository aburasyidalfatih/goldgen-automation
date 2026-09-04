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
            print(f"   {'LAYOUT':<26}{'RATA2':>8}{'SAMPEL':>8}{'RELATIF':>10}{'YAKIN':>8}")
            for l in page['layouts'][:8]:
                print(f"   {l['layout'][:25]:<26}{l['avg']:>8.0f}{l['n']:>8}"
                      f"{l['relatif']:>9.2f}x{l['confident_score']:>8.2f}  {bar(l['confident_score'], 0.05)}")
            print("   * relatif 1.00x = sebaik rata-rata page pada periode yang sama")
            print("   * skor yakin = relatif dipotong sesuai ketidakpastian sampel kecil")

        # --- Topik ---
        print("\n📚 TOPIK — isi konten yang paling disukai audiens page ini")
        if not page['topics']:
            print("   belum ada data (topik baru mulai dicatat pada postingan berikutnya)")
        else:
            print(f"   {'TOPIK':<46}{'RATA2':>8}{'SAMPEL':>8}{'RELATIF':>10}")
            for t in page['topics']:
                print(f"   {t['topik'][:45]:<46}{t['avg']:>8.0f}{t['n']:>8}{t['relatif']:>9.2f}x")

        # --- Hook ---
        print("\n🎣 HOOK — gaya pembuka yang benar-benar berbuah di page ini")
        if not page.get('hooks'):
            print("   belum ada data")
        else:
            print(f"   {'HOOK':<16}{'RATA2':>8}{'SAMPEL':>8}{'RELATIF':>10}{'YAKIN':>8}")
            for h in page['hooks']:
                rel = f"{h['relatif']:.2f}x" if h['relatif'] is not None else '-'
                print(f"   {h['hook']:<16}{h['avg']:>8.0f}{h['n']:>8}{rel:>10}{h['confident_score']:>8.2f}")
            print("   * hook kini diundi Thompson Sampling, bukan dipilih serakah")

        # --- Rasio klik ---
        k = page['clicks']
        print("\n🖱️  KLIK — daya tarik yang sudah dinormalkan terhadap paparan")
        if k['n'] == 0:
            print("   belum ada data klik (terekam pada snapshot 48 jam berikutnya)")
        else:
            print(f"   {k['n']} post berdata | klik rata-rata {k['klik_rata']} | rasio engagement/klik {k['rasio']}%")
            for t in k['terbaik']:
                print(f"      {t['rasio']:>5.1f}%  klik {t['klik']:<5} eng {t['engagement']:<4} {t['topik']}")

        # --- Unsur caption ---
        cf = page['caption_features']
        print("\n✍️  UNSUR CAPTION — apakah aturan prompt kita benar-benar berbuah?")
        if not cf['cukup']:
            print(f"   data belum cukup ({cf['n']} post)")
        elif not cf['fitur']:
            print("   variasi antar caption belum cukup untuk dibandingkan")
        else:
            for f in cf['fitur']:
                arah = "lebih tinggi" if f['selisih_persen'] > 0 else "lebih rendah"
                print(f"   {f['fitur']:<18} {f['label_ya']:<14} {f['rata_ya']:>6.0f} (n={f['n_ya']})"
                      f"  vs {f['label_tidak']:<14} {f['rata_tidak']:>6.0f} (n={f['n_tidak']})"
                      f"  -> {abs(f['selisih_persen']):.0f}% {arah}")

        # --- Editor ---
        e = page['editor']
        print(f"\n🕵️  EDITOR AI — {e['verdict']}")
        if e['r'] is not None:
            print(f"   korelasi skor vs engagement: {e['r']:+.2f} (dari {e['n']} post)")
            if e['avg_high'] is not None and e['avg_low'] is not None:
                print(f"   caption skor >=8 : {e['avg_high']:.0f} engagement")
                print(f"   caption skor <8  : {e['avg_low']:.0f} engagement")
            if e.get('contoh_skor_tinggi_sepi'):
                print("   Dinilai BAGUS tapi sepi:")
                for c in e['contoh_skor_tinggi_sepi']:
                    print(f"      [{c['skor']:.0f}/10, eng {c['engagement']:.0f}] {c['pembuka']}")
            if e.get('contoh_skor_rendah_ramai'):
                print("   Dinilai JELEK tapi ramai:")
                for c in e['contoh_skor_rendah_ramai']:
                    print(f"      [{c['skor']:.0f}/10, eng {c['engagement']:.0f}] {c['pembuka']}")

        # --- Kritikus gambar ---
        g = page.get('image_critic') or {}
        print(f"\n🖼️  KRITIKUS GAMBAR — {g.get('verdict', 'belum ada data')}")
        if g.get('r') is not None:
            print(f"   korelasi skor gambar vs engagement: {g['r']:+.2f} (dari {g['n']} post)")
            if g.get('avg_high') is not None and g.get('avg_low') is not None:
                print(f"   gambar skor >=8 : {g['avg_high']:.0f} engagement")
                print(f"   gambar skor <8  : {g['avg_low']:.0f} engagement")

        # --- Audiens & jangkauan ---
        a = page['audience']
        if a['pengikut_terkini']:
            baris = f"\n👥 AUDIENS — {a['pengikut_terkini']:,} pengikut"
            if a['pertumbuhan'] is not None:
                baris += f" ({a['pertumbuhan']:+.2f}% sejak mulai dicatat)"
            print(baris)
            if a['engagement_per_1000'] is not None:
                print(f"   engagement per 1.000 pengikut: {a['engagement_per_1000']}")
            if a['klik_tersedia']:
                print(f"   klik rata-rata per postingan: {a['klik_rata']}")
            else:
                print("   klik per postingan: terekam mulai snapshot berikutnya")
            if a['interaksi_harian']:
                print("   interaksi harian halaman (sinyal jangkauan):")
                for h in a['interaksi_harian'][:5]:
                    print(f"      {h['tanggal']}  interaksi {h['interaksi']:<6} kunjungan {h['kunjungan']}")
        else:
            print("\n👥 AUDIENS — belum ada data (terekam mulai siklus riset berikutnya)")

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
