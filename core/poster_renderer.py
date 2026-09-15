"""Deterministic poster typography, independent of image-model lettering."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from core.layout_design import design
from core.visual_plan import safe_trim_words

WIDTH, HEIGHT = 1440, 2560

# Zona aman feed Facebook.
#
# Kanvas 9:16 disengaja: Facebook memotongnya di feed, sehingga pembaca harus
# mengetuk gambar untuk melihat utuh — dan ketukan itu sinyal positif bagi
# algoritma. Tapi potongannya CENTER-weighted, jadi bagian atas dan bawah
# hilang dari feed. Sebelumnya JUDUL berada di y=100-322 dan kotak pertanyaan
# di y=2190-2470: keduanya di luar zona tampak, sehingga di feed orang hanya
# melihat ilustrasi tanpa satu kata pun yang menjelaskan isinya.
#
# Yang menentukan seseorang mengetuk justru judulnya, jadi judul dan label
# harus berada di dalam zona ini. Pertanyaan diskusi sengaja ditaruh di bawah
# garis potong sebagai imbalan bagi yang sudah mengetuk.
SAFE_TOP = (HEIGHT - WIDTH * 5 // 4) // 2      # 380
SAFE_BOTTOM = HEIGHT - SAFE_TOP                # 2180

# Ilustrasi mengisi SELURUH kanvas; teks duduk di atasnya.
#
# Sebelumnya ilustrasi ditempel sebagai kotak 1312x1180 di tengah poster —
# hanya 42% dari kanvas. Sisanya latar krem polos: 390px kosong di atas judul,
# 128px margin kiri-kanan, dan beberapa jeda antar blok. Tidak ada yang
# memaksanya demikian; ART_H = 1180 hanyalah angka yang ditulis tetap.
#
# Sekarang gambar dibentangkan penuh dan tipografi digambar di atas panel semi
# transparan. Tipografi tetap milik PIL, bukan model gambar: contoh infografis
# yang dijadikan acuan justru memperlihatkan akibatnya kalau model yang menulis
# — "SUWW POLY SAK", "SAMPLES PORTS with a historical flow patterns",
# "creatng natural trap and otther bouldls". Ejaan rusak seperti itu tidak bisa
# diperbaiki setelah gambar jadi.
PANEL_ALPHA = 224          # panel judul dan label
CARD_ALPHA = 238           # kartu pertanyaan, perlu kontras paling tinggi
MARGIN, TEXT_LEFT, TEXT_RIGHT = 48, 72, WIDTH - 72


def _rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _panel(draw, box, fill, alpha, outline=None, radius=24, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=_rgb(fill) + (alpha,),
                           outline=(_rgb(outline) + (255,)) if outline else None,
                           width=width if outline else 0)


def font(size, bold=False):
    paths = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
             if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"])
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def draw_text_box(draw, text, box, size, fill, bold=False, minimum=24):
    """Wrap even unbroken words and fit actual font metrics, never clip text."""
    x, y, right, bottom = box
    for pixels in range(size, minimum - 1, -1):
        face = font(pixels, bold)
        lines, line = [], ''
        for word in str(text).split():
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=face) <= right-x:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ''
            for char in word:
                if line and draw.textlength(line+char, font=face) > right-x:
                    lines.append(line); line = ''
                line += char
        if line:
            lines.append(line)
        ascent, descent = face.getmetrics()
        step = ascent + descent + int(pixels*.2)
        if len(lines)*step <= bottom-y:
            for i, value in enumerate(lines):
                draw.text((x, y+i*step), value, font=face, fill=fill, anchor='lt')
            return {'box': box, 'font_size': pixels, 'lines': lines}
    raise ValueError('Text exceeds its reserved poster area')


def compose_poster(artwork, plan, output, watermark=''):
    bg, ink, accent, _ = design(plan.get('layout'))

    # Ilustrasi dibentangkan ke seluruh kanvas, bukan ditempel sebagai kotak.
    if artwork:
        with Image.open(artwork) as source:
            canvas = ImageOps.fit(source.convert('RGB'), (WIDTH, HEIGHT),
                                  Image.Resampling.LANCZOS).convert('RGBA')
    else:
        canvas = Image.new('RGBA', (WIDTH, HEIGHT), _rgb(bg) + (255,))

    # Panel digambar di lapisan terpisah supaya benar-benar tembus pandang;
    # menggambar langsung ke kanvas hanya menghasilkan blok buram.
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    shade = ImageDraw.Draw(overlay)

    subtitle = safe_trim_words(plan.get('subtitle') or '', 120)
    TITLE_PANEL = (MARGIN, SAFE_TOP - 40, WIDTH - MARGIN, SAFE_TOP + 300)
    LABEL_PANEL = (MARGIN, SAFE_BOTTOM - 300, WIDTH - MARGIN, SAFE_BOTTOM - 16)
    QUESTION_CARD = (MARGIN, SAFE_BOTTOM + 16, WIDTH - MARGIN, SAFE_BOTTOM + 256)
    # Watermark dulu dicetak langsung di atas ilustrasi tanpa alas apa pun.
    # Di poster lama itu tidak kelihatan karena latarnya krem polos; begitu
    # gambar dibentangkan penuh, baris ini hilang ditelan teksturnya.
    FOOTER_PANEL = (MARGIN, SAFE_BOTTOM + 272, WIDTH - MARGIN, SAFE_BOTTOM + 340)

    r, g, b = _rgb(bg)
    is_light = (0.299 * r + 0.587 * g + 0.114 * b) > 128
    card_fill = '#ebe2cd' if is_light else '#162228'

    raw_labels = [str(lbl).strip() for lbl in plan.get('labels', []) if str(lbl).strip()]
    labels = raw_labels[:4] if raw_labels else []

    _panel(shade, TITLE_PANEL, bg, PANEL_ALPHA, accent)
    if labels:
        _panel(shade, LABEL_PANEL, bg, PANEL_ALPHA, accent)
    _panel(shade, QUESTION_CARD, card_fill, CARD_ALPHA, accent, radius=20, width=3)
    _panel(shade, FOOTER_PANEL, bg, PANEL_ALPHA, radius=16)

    canvas = Image.alpha_composite(canvas, overlay).convert('RGB')
    draw = ImageDraw.Draw(canvas)

    # Frame perbatasan vintage ekspedisi / field guide ganda
    draw.rectangle((24, 24, WIDTH - 24, HEIGHT - 24), outline=accent, width=2)
    draw.rectangle((32, 32, WIDTH - 32, HEIGHT - 32), outline=accent, width=1)

    # Garis aksen header atas
    draw.rectangle((TEXT_LEFT, SAFE_TOP - 14, TEXT_LEFT + 136, SAFE_TOP - 6), fill=accent)

    # Render Judul & Subtitle Aforisme
    if subtitle:
        boxes = [draw_text_box(draw, plan['title'], (TEXT_LEFT, SAFE_TOP + 16, TEXT_RIGHT, SAFE_TOP + 176), 78, ink, True, 44)]
        boxes.append(draw_text_box(draw, subtitle, (TEXT_LEFT, SAFE_TOP + 188, TEXT_RIGHT, SAFE_TOP + 272), 38, accent, True, 24))
    else:
        boxes = [draw_text_box(draw, plan['title'], (TEXT_LEFT, SAFE_TOP + 30, TEXT_RIGHT, SAFE_TOP + 272), 86, ink, True, 48)]

    if artwork and plan.get('layout') == 'GAMIFICATION_QUIZ':
        for i, letter in enumerate('ABCD'):
            x = TEXT_LEFT + (i % 2) * (WIDTH - 2 * TEXT_LEFT) // 2 + 24
            y = SAFE_TOP + 340 + (i // 2) * 580
            draw.rounded_rectangle((x, y, x + 76, y + 76), radius=12, fill=bg, outline=accent, width=3)
            draw.text((x + 22, y + 13), letter, font=font(43, True), fill=ink)
    elif not artwork:
        # A clearly editorial fallback, not invented geology or a recycled topic image.
        top_area = SAFE_TOP + 340
        draw.rounded_rectangle((MARGIN, top_area, WIDTH - MARGIN, SAFE_BOTTOM - 340), radius=28, outline=accent, width=3)
        boxes.append(draw_text_box(draw, 'FIELD OBSERVATIONS', (112, top_area + 44, 1328, top_area + 130), 42, accent, True))
        points = plan.get('fallback_points', [])[:4]
        for i, point in enumerate(points):
            top = top_area + 176 + i * 240
            draw.ellipse((112, top + 12, 128, top + 28), fill=accent)
            boxes.append(draw_text_box(draw, point, (160, top, 1320, top + 206), 45, ink, minimum=28))

    # Pill badge bernomor untuk label petunjuk (Reader Key).
    #
    # Grid tidak lagi dipaksa berisi empat. Dulu label yang kurang ditambal
    # dengan daftar tetap "Surface Water Flow / Stratified River Gravel /
    # Black Sand Paystreak / Bedrock Crevice Trap", dan tambalan itu terbit
    # sebagai keterangan geologi untuk gambar yang belum tentu memuatnya.
    # Tiga label yang benar lebih baik daripada empat yang satu di antaranya
    # karangan.
    kolom = (WIDTH - 2 * TEXT_LEFT) // 2
    for i, label in enumerate(labels):
        col, row = i % 2, i // 2
        x, y = TEXT_LEFT + col * kolom, SAFE_BOTTOM - 276 + row * 130
        draw.rounded_rectangle((x, y + 8, x + 64, y + 52), radius=10, fill=accent)
        draw.text((x + 16, y + 14), f"0{i+1}", font=font(26, True), fill=bg)
        boxes.append(draw_text_box(draw, label, (x + 78, y + 4, x + kolom - 24, y + 110), 48, ink, True, minimum=24))

    # Kartu Pertanyaan Diskusi Lapangan (Field Insight Card)
    boxes.append(draw_text_box(draw, 'FIELD PROSPECTING INSIGHT', (108, SAFE_BOTTOM + 32, 1332, SAFE_BOTTOM + 66), 24, accent, True, minimum=20))
    boxes.append(draw_text_box(draw, plan['question'], (108, SAFE_BOTTOM + 74, 1332, SAFE_BOTTOM + 240), 46, ink, True, 28))

    # Footer Watermark & Seri Panduan
    wm_text = (watermark[:60] + '  •  FIELD GUIDE SERIES') if watermark else 'GOLDGEN FIELD GUIDE'
    boxes.append(draw_text_box(draw, wm_text, (TEXT_LEFT, SAFE_BOTTOM + 288, TEXT_RIGHT, SAFE_BOTTOM + 328), 28, ink, minimum=20))
    canvas.save(output, 'PNG')
    return boxes
