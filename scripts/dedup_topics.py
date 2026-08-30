#!/usr/bin/env python3
"""
Gabungkan topik duplikat di data/topics.json.

Latar belakang: generator topik dinamis dipanggil setiap kali kandidat yang
cocok kebetulan baru dipakai, sehingga ia terus menciptakan ulang topik yang
sebenarnya sudah ada. Pemeriksaan produksi menemukan topics.json membengkak
101 -> 199 dengan 63 pasang topik berkemiripan >=50%, beberapa identik.

Dampaknya bukan sekadar file gemuk: kalau hampir tiap postingan memakai topik
unik, tidak ada topik yang pernah mengumpulkan cukup sampel untuk dipelajari —
pembelajaran topik jadi mustahil.

Script ini menyimpan topik yang muncul PERTAMA dan membuang kembarannya.
Topik asli (101 pertama) tidak pernah dibuang.

Pakai:
    python scripts/dedup_topics.py            # tampilkan saja
    python scripts/dedup_topics.py --apply    # tulis perubahan
"""

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TOPICS_PATH = Path(__file__).parent.parent / 'data' / 'topics.json'
AMBANG = 0.5          # kemiripan >= 50% dianggap kembar
JUMLAH_ASLI = 101     # topik kurasi awal, selalu dipertahankan

STOPWORDS = {'the', 'of', 'a', 'an', 'to', 'for', 'in', 'on', 'and', 'your',
             'how', 'that', 'is', 'with', 'you', 'why', 'what'}


def kata_kunci(teks):
    return frozenset(w for w in re.findall(r'[a-z]+', (teks or '').lower())
                     if w not in STOPWORDS and len(w) > 3)


def main():
    apply_changes = '--apply' in sys.argv

    with open(TOPICS_PATH, 'r', encoding='utf-8') as f:
        topics = json.load(f)

    print(f"Total topik saat ini : {len(topics)}")
    print(f"Topik kurasi awal    : {min(JUMLAH_ASLI, len(topics))} (tidak akan dibuang)\n")

    disimpan = []
    dibuang = []

    for i, t in enumerate(topics):
        judul = t.get('headline') or ''
        if i < JUMLAH_ASLI:
            disimpan.append(t)
            continue

        kunci = kata_kunci(judul)
        kembar_dari = None
        for s in disimpan:
            lain = kata_kunci(s.get('headline'))
            if kunci and lain:
                gabungan = len(kunci | lain)
                if gabungan and len(kunci & lain) / gabungan >= AMBANG:
                    kembar_dari = s.get('headline')
                    break

        if kembar_dari:
            dibuang.append((judul, kembar_dari))
        else:
            disimpan.append(t)

    print(f"Topik kembar ditemukan : {len(dibuang)}")
    print(f"Sisa setelah dirapikan : {len(disimpan)}\n")

    for judul, asal in dibuang[:12]:
        print(f"   BUANG  {judul[:52]}")
        print(f"     sama dengan  {asal[:52]}")
    if len(dibuang) > 12:
        print(f"   ... dan {len(dibuang) - 12} lainnya")

    if not apply_changes:
        print("\n(tampilan saja — tambahkan --apply untuk menulis perubahan)")
        return

    if not dibuang:
        print("Tidak ada yang perlu dirapikan.")
        return

    cadangan = Path(str(TOPICS_PATH) + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy(TOPICS_PATH, cadangan)

    with open(TOPICS_PATH, 'w', encoding='utf-8') as f:
        json.dump(disimpan, f, indent=4, ensure_ascii=False)

    print(f"\n✅ topics.json dirapikan: {len(topics)} -> {len(disimpan)} topik")
    print(f"   Cadangan: {cadangan.name}")


if __name__ == '__main__':
    main()
