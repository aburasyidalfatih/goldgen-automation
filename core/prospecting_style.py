"""Arahan gaya khas prospeksi emas untuk poster dan judul.

Diadopsi dari panduan editorial pemilik (Gold_Prospecting_Knowledge.md dan
Gold_Prospecting_Custom_GPT_Instructions.md). Yang diambil hanya bagian yang
belum ada di pipeline:

- identitas visual (panduan lapangan Amerika lama, bukan template modern)
- rumus judul
- gaya label pendek, termasuk cara menyebut petunjuk yang BELUM pasti
- disiplin "satu gagasan per gambar"

Yang SENGAJA TIDAK diadopsi:

- Rasio 2:3 / 4:5 yang disarankan dokumen. Kanvas 9:16 di sini disengaja:
  Facebook memotongnya di feed sehingga pembaca harus mengetuk untuk melihat
  utuh, dan ketukan itu sinyal positif bagi algoritma. Lihat SAFE_TOP di
  core/poster_renderer.py.
- Perintah percakapan ("buatkan konten", "lebih viral"). Pipeline ini otomatis;
  tidak ada yang mengetik perintah.
- "Jangan buat caption kecuali diminta". Bot ini selalu butuh caption.
"""

# Identitas visual — SENGAJA netral terhadap gaya render.
#
# Gaya render dimiliki per layout oleh DESIGNS di core/layout_design.py, dan di
# sana memang berbeda-beda: CROSS-SECTION CUTAWAY fotorealistik, VICTORIAN
# WOODCUT ukiran. Menuliskan "kertas lapuk, engraving" di sini akan bertabrakan
# dengan separuh katalog dan membuat model memilih salah satu secara acak.
#
# Jadi blok ini hanya memuat yang BERLAKU UNTUK SEMUA gaya: kekayaan tekstur
# dan standar mutu.
#
# Daftar "avoid" sengaja pendek. Larangan yang menumpuk justru menurunkan mutu:
# tiap kalimat negatif memakan perhatian model tanpa memberi tahu apa yang harus
# digambar, dan menyebut benda yang dilarang tetap memunculkan benda itu.
VISUAL_DNA = """SUBJECT MATERIAL — render real prospecting matter, whatever the style:
river rock, quartz, bedrock, black sand, clay, moss, iron staining, gravel,
gold flakes, pans, sluices, crevice tools. Dramatic but believable lighting.
The result must feel like a collectible field-guide page worth saving, detailed
enough to reward zooming — not a generic modern template.
Avoid: plastic-looking nuggets, treasure-chest fantasy, corporate icons, neon colour."""

# Pertanyaan yang harus terjawab dalam satu detik pertama. Ini alat uji
# komposisi yang paling berguna dari panduan itu.
ONE_SECOND_TEST = """THE ONE-SECOND TEST — someone scrolling past must grasp one of
these without reading: where is the gold, why does it collect there, what am I
looking at, which side is better. Teach exactly ONE idea."""

# Petunjuk geologi hampir tidak pernah membuktikan adanya emas. Menyebutnya
# sebagai kepastian adalah kesalahan faktual yang paling mudah terjadi, karena
# label pendek terdengar seperti pernyataan mutlak.
#
# Blok ini dipakai oleh PERENCANA LABEL, bukan oleh model gambar. Model gambar
# dilarang menulis apa pun, jadi mengajarinya memilih kata hanya membuang
# perhatian — dan menyebut "black sand, quartz, iron staining" di prompt
# ilustrasi justru menyuruhnya menggambar benda-benda itu, apa pun topiknya.
UNCERTAINTY_WORDS = """UNCERTAIN INDICATORS — black sand, quartz, iron staining,
sulfides and altered rock are reasons to sample, never proof of a deposit.
When labelling them, use hedged wording: "CLUE", "SIGN", "CHECK HERE",
"SAMPLE ZONE", "POSSIBLE INDICATOR". Never present them as a certainty."""

# Contoh label yang panjang dan bentuknya benar. Model jauh lebih patuh pada
# contoh konkret daripada pada aturan abstrak.
LABEL_EXAMPLES = ('"LOW-PRESSURE EDDY", "BEDROCK CREVICE", "INSIDE BEND", '
                  '"BLACK SAND CLUE", "FALSE BEDROCK CLAY", "PAYSTREAK", '
                  '"QUARTZ CONTACT", "IRON-STAINED FRACTURE"')

# Rumus judul. Dipakai saat sistem mengarang judul baru, bukan saat memakai
# judul katalog yang sudah dikurasi.
HEADLINE_FORMULAS = """THE [NOUN] RULE
READ THE [RIVER/ROCK/BEDROCK]
WHERE GOLD [DROPS/HIDES/SETTLES]
THE HIDDEN [PAYSTREAK/TRAP/CHANNEL]
FOLLOW THE [IRON/BLACK SAND/HEAVY STUFF]
WHY GOLD [STOPS/DROPS] HERE
THE [NUMBER] SIGNS OF [TOPIC]
GOLD LOVES [SLOW WATER/CREVICES]
DON'T IGNORE THE [CONTACT/CLAY/BLACK SAND]
BEHIND THE [BOULDER/RIFFLE/BEND]"""

# Angka yang aman dipakai. Sengaja sedikit: tiap angka tambahan adalah peluang
# model mengarang statistik hasil.
DENSITY_FACTS = ("Gold specific gravity is about 19.3; quartz about 2.65; "
                 "magnetite about 5.2. Heavy particles tend to concentrate where "
                 "stream energy drops, but real placer behaviour also depends on "
                 "grain size, shape, turbulence and bed roughness.")


def artwork_style():
    """Blok gaya untuk prompt ilustrasi.

    Hanya memuat hal yang KELIHATAN di gambar. Aturan tentang kata — gaya label
    dan kehati-hatian istilah — pindah ke label_style(), karena model gambar
    memang dilarang menulis apa pun.
    """
    return VISUAL_DNA + '\n\n' + ONE_SECOND_TEST


def label_style():
    """Blok gaya untuk perencana label (AI Art Director), bukan model gambar.

    Contoh sengaja disertai peringatan eksplisit agar tidak disalin mentah.
    Sebelumnya perencana diberi empat contoh tanpa peringatan, dan ketika topik
    tidak memberi bahan, keempat contoh itu terbit apa adanya sebagai label
    poster.
    """
    return (UNCERTAINTY_WORDS + '\n\nLABEL STYLE — short, concrete, all caps. Every '
            'label must name something actually visible in THIS topic\'s approved '
            'caption. The following show the required shape only and must never be '
            'copied as answers: ' + LABEL_EXAMPLES)


def headline_style():
    """Blok rumus judul untuk pembuatan topik baru."""
    return ('HEADLINE FORMULAS — short, curiosity-driven, educational. Vary them; '
            'do not reuse one formula repeatedly:\n' + HEADLINE_FORMULAS)
