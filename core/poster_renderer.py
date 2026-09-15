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
    canvas = Image.new('RGB', (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(canvas)

    # Frame perbatasan vintage ekspedisi / field guide ganda
    draw.rectangle((24, 24, WIDTH - 24, HEIGHT - 24), outline=accent, width=2)
    draw.rectangle((32, 32, WIDTH - 32, HEIGHT - 32), outline=accent, width=1)

    # Garis aksen header atas
    draw.rectangle((64, SAFE_TOP + 10, 200, SAFE_TOP + 18), fill=accent)

    # Render Judul & Subtitle Aforisme
    subtitle = safe_trim_words(plan.get('subtitle') or '', 120)
    if subtitle:
        boxes = [draw_text_box(draw, plan['title'], (64, SAFE_TOP + 36, 1376, SAFE_TOP + 196), 78, ink, True, 44)]
        boxes.append(draw_text_box(draw, subtitle, (64, SAFE_TOP + 204, 1376, SAFE_TOP + 280), 38, accent, True, 24))
    else:
        boxes = [draw_text_box(draw, plan['title'], (64, SAFE_TOP + 52, 1376, SAFE_TOP + 274), 86, ink, True, 48)]

    ART_TOP, ART_H = SAFE_TOP + 320, 1180
    if artwork:
        with Image.open(artwork) as source:
            art = ImageOps.fit(source.convert('RGB'), (1312, ART_H), Image.Resampling.LANCZOS)
        canvas.paste(art, (64, ART_TOP))
        # Bingkai tipis aksen di sekeliling ilustrasi
        draw.rectangle((64, ART_TOP, 64 + 1312, ART_TOP + ART_H), outline=accent, width=2)
        if plan.get('layout') == 'GAMIFICATION_QUIZ':
            left, top = 64, ART_TOP
            for i, letter in enumerate('ABCD'):
                x, y = left + (i % 2) * art.width // 2 + 24, top + (i // 2) * art.height // 2 + 24
                draw.rounded_rectangle((x, y, x + 76, y + 76), radius=12, fill=bg, outline=accent, width=3)
                draw.text((x + 22, y + 13), letter, font=font(43, True), fill=ink)
    else:
        # A clearly editorial fallback, not invented geology or a recycled topic image.
        draw.rounded_rectangle((64, ART_TOP, 1376, ART_TOP + ART_H), radius=28, outline=accent, width=3)
        boxes.append(draw_text_box(draw, 'FIELD OBSERVATIONS', (112, ART_TOP + 60, 1328, ART_TOP + 146), 42, accent, True))
        points = plan.get('fallback_points', [])[:4]
        for i, point in enumerate(points):
            top = ART_TOP + 196 + i * 244
            draw.ellipse((112, top + 12, 128, top + 28), fill=accent)
            boxes.append(draw_text_box(draw, point, (160, top, 1320, top + 210), 45, ink, minimum=28))

    # Pill badge bernomor untuk label petunjuk (Reader Key)
    # Pastikan grid 2x2 selalu seimbang dengan 4 label terisi rapi
    raw_labels = [str(lbl).strip() for lbl in plan.get('labels', []) if str(lbl).strip()]
    default_strata = [
        "Surface Water Flow",
        "Stratified River Gravel",
        "Black Sand Paystreak",
        "Bedrock Crevice Trap"
    ]
    if raw_labels:
        if len(raw_labels) == 1:
            labels = [raw_labels[0], default_strata[1], default_strata[2], default_strata[3]]
        elif len(raw_labels) == 2:
            labels = [raw_labels[0], default_strata[1], raw_labels[1], default_strata[3]]
        elif len(raw_labels) == 3:
            labels = [raw_labels[0], raw_labels[1], raw_labels[2], default_strata[3]]
        else:
            labels = raw_labels[:4]
    elif artwork:
        labels = default_strata
    else:
        labels = []

    r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
    is_light = (0.299 * r + 0.587 * g + 0.114 * b) > 128
    card_fill = '#ebe2cd' if is_light else '#162228'
    badge_fill = accent
    badge_text = bg

    for i, label in enumerate(labels):
        col, row = i % 2, i // 2
        x, y = 64 + col * 672, SAFE_BOTTOM - 250 + row * 120
        draw.rounded_rectangle((x, y + 8, x + 64, y + 52), radius=10, fill=badge_fill)
        draw.text((x + 16, y + 14), f"0{i+1}", font=font(26, True), fill=badge_text)
        boxes.append(draw_text_box(draw, label, (x + 78, y + 6, x + 620, y + 104), 48, ink, True, minimum=24))

    # Kartu Pertanyaan Diskusi Lapangan (Field Insight Card)
    draw.rounded_rectangle((64, SAFE_BOTTOM + 16, 1376, SAFE_BOTTOM + 284), radius=20, fill=card_fill, outline=accent, width=3)
    boxes.append(draw_text_box(draw, 'FIELD PROSPECTING INSIGHT', (100, SAFE_BOTTOM + 34, 1340, SAFE_BOTTOM + 68), 24, accent, True, minimum=20))
    boxes.append(draw_text_box(draw, plan['question'], (100, SAFE_BOTTOM + 76, 1340, SAFE_BOTTOM + 266), 46, ink, True, 28))

    # Footer Watermark & Seri Panduan
    wm_text = (watermark[:60] + '  •  FIELD GUIDE SERIES') if watermark else 'GOLDGEN FIELD GUIDE'
    boxes.append(draw_text_box(draw, wm_text, (64, SAFE_BOTTOM + 304, 1376, SAFE_BOTTOM + 350), 28, ink, minimum=20))
    canvas.save(output, 'PNG')
    return boxes
