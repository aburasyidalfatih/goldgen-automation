"""Publication checks shared by automatic and on-demand AI generation."""
import math
import re

# Limited reference context, not a claim that all generated geology is verified.
FACT_CONTEXT = '''Reference: USGS Gold, https://pubs.usgs.gov/gip/prospect1/goldgip.html
Placer gold is concentrated by gravity after erosion of source rock. Stream gold
can accumulate near bedrock. Magnetite is common in black sands alongside other
heavy minerals. These general observations do not identify a deposit at a specific site.
Reference: USGS Prospecting for Gold,
https://pubs.usgs.gov/gip/prospect2/prospectgip.html
Panning separates gold from stream silt, sand and gravel; prospecting success is uncertain.
Editorial limits: More black sand alone does not establish greater gold yield.
One or two pans do not establish a pay streak or economic viability. Recommend
further comparable sampling, not immediate excavation based on black sand alone.
Do not depict entering deep or fast-moving water as a routine prospecting step.
Never assert a universal gold-bearing depth or show every soil layer as gold-rich.
Depth labels in hypothetical profiles must be explicitly illustrative, not survey results.
Do not confuse density relative to water with density relative to river rock.
Do not invent first-person prospecting experiences or guaranteed financial rewards.
Visual guidance: use one dominant explanatory diagram, 3-5 concise callouts,
readable labels and arrows tied to actual features. Avoid paragraphs of tiny text.
Use magnified insets only when they explain the topic; do not add unrelated microbes.
'''


class ContentQualityError(ValueError):
    pass


# Vision reviewers commonly return half-point scores. Treating 6.5 as a hard
# failure while displaying it as 7/10 caused otherwise usable posts to be
# reported as "7/10" but rejected. Keep a meaningful floor and make the rule
# explicit and consistent with the displayed score.
IMAGE_MIN_SCORE = 6.5

# Frasa yang tidak boleh muncul di permintaan gambar. Dipindai oleh
# _preflight_image_plan di auto_poster.py.
#
# Dijadikan satu konstanta agar bisa diuji terhadap katalog layout. Dulu daftar
# ini tertanam di dalam fungsi, dan tidak ada yang menyadari bahwa deskripsi
# THE PROSPECTOR'S MAP memuat salah satunya — sehingga layout itu selalu
# menjegal dirinya sendiri sampai gagal terbit.
FORBIDDEN_IMAGE_TERMS = ('guaranteed gold', 'guaranteed deposit', 'chemical extraction')

# Model teks menulis dalam Markdown karena itu kebiasaannya, sementara Facebook
# tidak merender apa pun: "**learn to read the**" terbit apa adanya, lengkap
# dengan bintangnya. Model gambar juga menerima teks yang sama, dan di poster ia
# menafsirkan bintang itu sebagai perintah menebalkan sebagian kalimat.
#
# Tanda diurutkan dari yang paling panjang: ** harus diproses sebelum *, kalau
# tidak, aturan miring akan memakan separuh penanda tebal dan menyisakan bintang
# tunggal yang justru lebih berantakan.
_MARKDOWN = (
    (re.compile(r'\*\*(?=\S)([^*]+?)(?<=\S)\*\*'), r'\1'),
    (re.compile(r'__(?=\S)([^_]+?)(?<=\S)__'), r'\1'),
    # (?=\S) menjaga "5 * 3" dan butir daftar "* item" tetap utuh: keduanya
    # punya spasi tepat setelah bintang.
    (re.compile(r'\*(?=\S)([^*\n]+?)(?<=\S)\*'), r'\1'),
    (re.compile(r'(?<![A-Za-z0-9_])_(?=\S)([^_\n]+?)(?<=\S)_(?![A-Za-z0-9_])'), r'\1'),
    (re.compile(r'`{1,3}([^`]+)`{1,3}'), r'\1'),
    (re.compile(r'^\s{0,3}#{1,6}\s+', re.M), ''),
    (re.compile(r'\[([^\]]+)\]\([^)]*\)'), r'\1'),
    # Sisa penanda yang tidak berpasangan. Tidak ada caption Facebook yang
    # benar-benar bermaksud menampilkan dua bintang berturut-turut.
    (re.compile(r'\*\*+'), ''),
)


def strip_markdown(text):
    """Buang penanda Markdown dari teks yang akan dilihat manusia."""
    hasil = str(text or '')
    for pola, ganti in _MARKDOWN:
        hasil = pola.sub(ganti, hasil)
    return hasil


def valid_score(value):
    if isinstance(value, bool):
        return None
    try:
        score = float(value)
        return score if math.isfinite(score) and 1 <= score <= 10 else None
    except (TypeError, ValueError):
        return None


def caption_issues(caption, review, requested_hook):
    issues = []
    # Score and hook are learning signals, not publication requirements.
    # Missing structured checks must not silently approve a failed reviewer.
    if review.get('factual_issues') != []:
        issues.append('klaim faktual belum lolos pemeriksaan: ' + str(review.get('factual_issues'))[:300])
    if len(caption) < 100 or len(caption) > 1400:
        issues.append('panjang caption harus 100–1400 karakter')
    if re.search(r'\b\d+(?:\.\d+)?\s*(?:%|percent\b|times\b)|\b(?:retirement fund|mortgage payment)\b', caption, re.I):
        issues.append('hapus statistik hasil atau janji kekayaan yang tidak terverifikasi')
    if re.search(r"\b(?:I|we)[’']?ll\s+(?:reveal|check|announce)|\b(?:reveal|answer)\b.{0,45}\b(?:later|tomorrow|tonight)\b", caption, re.I):
        issues.append('jangan menjanjikan tindak lanjut yang belum dijadwalkan')
    if re.search(r"found the pay\s?streak|signal to start digging|waist.deep.{0,35}(?:rushing|creek|river)", caption, re.I):
        issues.append('hapus kesimpulan deposit tanpa bukti atau skenario masuk air dalam')
    return issues


def require_publishable(topic):
    if topic.get('caption_approved') is not True:
        raise ContentQualityError('DITAHAN KUALITAS: caption belum lolos pemeriksaan')
    # Sebuah infografis tanpa grafis bukan konten yang layak tayang.
    #
    # Pada 15 September, gerbang keamanan pra-generate menolak rencana visual
    # yang memuat "guaranteed gold" — itu benar. Tapi penanganannya jatuh ke
    # fallback PIL yang hanya menggambar kotak teks, lalu postingan tetap
    # diterbitkan sebagai sukses. Yang tayang di Miners 24 adalah dinding teks
    # 155 KB tanpa satu pun ilustrasi. Gerbang keamanan berubah menjadi
    # penerbit konten buruk.
    if topic.get('image_fallback') is True:
        raise ContentQualityError(
            'DITAHAN KUALITAS: ilustrasi gagal dibuat; poster teks tanpa gambar tidak diterbitkan')
    score = valid_score(topic.get('image_score'))
    if score is None:
        raise ContentQualityError('DITAHAN KUALITAS: gambar menunggu pemeriksaan; ulangi pemeriksaan gambar yang tersimpan')
    if score < IMAGE_MIN_SCORE:
        raise ContentQualityError(f'DITAHAN KUALITAS: skor gambar {score:g} di bawah {IMAGE_MIN_SCORE:g}; generate ulang')
    # A successful HTTP response is not an approval of the resulting artwork.
