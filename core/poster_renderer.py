"""Deterministic poster typography, independent of image-model lettering."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from core.layout_design import design

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
    draw.rectangle((64, SAFE_TOP + 10, 164, SAFE_TOP + 18), fill=accent)
    boxes = [draw_text_box(draw, plan['title'], (64, SAFE_TOP + 52, 1376, SAFE_TOP + 274), 86, ink, True, 48)]
    ART_TOP, ART_H = SAFE_TOP + 320, 1180
    if artwork:
        with Image.open(artwork) as source:
            # Isi slot penuh, bukan disisipkan dengan margin.
            #
            # `contain` menyisakan celah di kiri-kanan, dan latar krem yang
            # dihasilkan model tidak pernah sama persis dengan palet poster —
            # hasilnya tepi kotak yang terlihat seperti gambar tempelan.
            # Sumbernya kini 1:1 ke slot 1312x1180, jadi `fit` hanya memangkas
            # sekitar 5% sisi atas-bawah; prompt ilustrasi memang sudah
            # mensyaratkan objek penting berada di dalam margin aman 5%.
            art = ImageOps.fit(source.convert('RGB'), (1312, ART_H), Image.Resampling.LANCZOS)
        canvas.paste(art, (64, ART_TOP))
        if plan.get('layout') == 'GAMIFICATION_QUIZ':
            left, top = 64, ART_TOP
            for i, letter in enumerate('ABCD'):
                x, y = left+(i % 2)*art.width//2+24, top+(i//2)*art.height//2+24
                draw.rounded_rectangle((x, y, x+76, y+76), radius=12, fill=bg, outline=accent, width=3)
                draw.text((x+22, y+13), letter, font=font(43, True), fill=ink)
    else:
        # A clearly editorial fallback, not invented geology or a recycled topic image.
        draw.rounded_rectangle((64, ART_TOP, 1376, ART_TOP+ART_H), radius=28, outline=accent, width=3)
        boxes.append(draw_text_box(draw, 'FIELD OBSERVATIONS', (112, ART_TOP+60, 1328, ART_TOP+146), 42, accent, True))
        points = plan.get('fallback_points', [])[:4]
        for i, point in enumerate(points):
            top = ART_TOP + 196 + i*244
            draw.ellipse((112, top+12, 128, top+28), fill=accent)
            boxes.append(draw_text_box(draw, point, (160, top, 1320, top+210), 45, ink, minimum=28))
    # Label ikut di dalam zona aman: ia memberi konteks yang membantu orang
    # memutuskan mengetuk. Ukurannya dinaikkan dari 34 ke 52 karena pada 34px
    # teks ini hanya ~10px di layar ponsel — tidak terbaca, apalagi dipelajari.
    labels = plan.get('labels', [])[:4]
    for i, label in enumerate(labels):
        col, row = i % 2, i // 2
        x, y = 64+col*672, SAFE_BOTTOM-250+row*120
        draw.line((x, y, x+56, y), fill=accent, width=3)
        boxes.append(draw_text_box(draw, label, (x, y+14, x+628, y+110), 52, ink, minimum=34))
    # Di bawah garis potong: hanya terlihat setelah gambar diketuk.
    draw.rounded_rectangle((64, SAFE_BOTTOM+20, 1376, SAFE_BOTTOM+280), radius=24, outline=accent, width=3)
    boxes.append(draw_text_box(draw, plan['question'], (100, SAFE_BOTTOM+56, 1340, SAFE_BOTTOM+248), 49, ink, True, 36))
    if watermark:
        boxes.append(draw_text_box(draw, watermark[:80], (64, SAFE_BOTTOM+300, 1376, SAFE_BOTTOM+350), 26, ink, minimum=20))
    canvas.save(output, 'PNG')
    return boxes
