#!/usr/bin/env python3
"""
Buang topik yang lahir dari pencemaran label hook.

Latar belakang: sebelum perbaikan pemisahan hook/topik, preferensi audiens
terisi penuh oleh label seperti "hook: fact". Label itu ikut dikirim sebagai
benih ke generator topik, sehingga AI diminta mengarang topik tentang kata
"hook" — dan ia menurut. Hasilnya topik seperti "The Unknown Hook: Unlocking
Hidden Gold Pockets", yang bagi audiens tidak berarti apa-apa.

Sumbernya sudah ditutup (generator kini hanya menerima kata kunci topik nyata),
tapi topik cacat yang terlanjur lahir masih mengendap di kolam dan masih bisa
terpilih — satu di antaranya benar-benar tayang pada 31 Agustus.

Pakai:
    python scripts/purge_hook_topics.py            # tampilkan saja
    python scripts/purge_hook_topics.py --apply    # tulis perubahan
"""

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TOPICS_PATH = Path(__file__).parent.parent / 'data' / 'topics.json'

# "hook" sebagai kata utuh: istilah copywriting yang bocor ke permukaan.
# Nama hook ("mythbuster", "fear") juga bukan materi konten.
POLA = re.compile(r'\bhooks?\b|\bmythbuster\b', re.I)


def tercemar(topic):
    teks = ' '.join(str(topic.get(k) or '') for k in ('headline', 'angle', 'description'))
    return bool(POLA.search(teks))


def main():
    apply_changes = '--apply' in sys.argv

    with open(TOPICS_PATH, 'r', encoding='utf-8') as f:
        topics = json.load(f)

    dibuang = [t for t in topics if tercemar(t)]
    disimpan = [t for t in topics if not tercemar(t)]

    print(f"Total topik       : {len(topics)}")
    print(f"Tercemar istilah  : {len(dibuang)}")
    print(f"Sisa setelah bersih: {len(disimpan)}\n")

    for t in dibuang:
        print(f"   BUANG  {(t.get('headline') or '')[:70]}")

    if not apply_changes:
        print("\n(tampilan saja — tambahkan --apply untuk menulis perubahan)")
        return

    if not dibuang:
        print("Tidak ada yang perlu dibuang.")
        return

    cadangan = Path(str(TOPICS_PATH) + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy(TOPICS_PATH, cadangan)

    with open(TOPICS_PATH, 'w', encoding='utf-8') as f:
        json.dump(disimpan, f, indent=4, ensure_ascii=False)

    print(f"\nOK topics.json dibersihkan: {len(topics)} -> {len(disimpan)} topik")
    print(f"   Cadangan: {cadangan.name}")


if __name__ == '__main__':
    main()
