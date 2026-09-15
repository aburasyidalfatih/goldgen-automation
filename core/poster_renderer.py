"""Deterministic poster typography, independent of image-model lettering."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from core.layout_design import design

WIDTH, HEIGHT = 1440, 2560


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
    draw.rectangle((64, 58, 164, 66), fill=accent)
    boxes = [draw_text_box(draw, plan['title'], (64, 100, 1376, 322), 86, ink, True, 48)]
    if artwork:
        with Image.open(artwork) as source:
            # Contain, never crop off scientific features. Fill spare space with palette.
            art = ImageOps.contain(source.convert('RGB'), (1312, 1550), Image.Resampling.LANCZOS)
        canvas.paste(art, (64+(1312-art.width)//2, 354+(1550-art.height)//2))
        if plan.get('layout') == 'GAMIFICATION_QUIZ':
            left, top = 64+(1312-art.width)//2, 354+(1550-art.height)//2
            for i, letter in enumerate('ABCD'):
                x, y = left+(i % 2)*art.width//2+24, top+(i//2)*art.height//2+24
                draw.rounded_rectangle((x, y, x+76, y+76), radius=12, fill=bg, outline=accent, width=3)
                draw.text((x+22, y+13), letter, font=font(43, True), fill=ink)
    else:
        # A clearly editorial fallback, not invented geology or a recycled topic image.
        draw.rounded_rectangle((64, 354, 1376, 1904), radius=28, outline=accent, width=3)
        boxes.append(draw_text_box(draw, 'FIELD OBSERVATIONS', (112, 414, 1328, 500), 42, accent, True))
        points = plan.get('fallback_points', [])[:4]
        for i, point in enumerate(points):
            top = 550+i*302
            draw.ellipse((112, top+12, 128, top+28), fill=accent)
            boxes.append(draw_text_box(draw, point, (160, top, 1320, top+264), 45, ink, minimum=28))
    labels = plan.get('labels', [])[:4]
    for i, label in enumerate(labels):
        col, row = i % 2, i // 2
        x, y = 64+col*672, 1940+row*102
        draw.line((x, y, x+56, y), fill=accent, width=3)
        boxes.append(draw_text_box(draw, label, (x, y+12, x+628, y+94), 34, ink, minimum=26))
    draw.rounded_rectangle((64, 2190, 1376, 2470), radius=24, outline=accent, width=3)
    boxes.append(draw_text_box(draw, plan['question'], (100, 2226, 1340, 2438), 49, ink, True, 36))
    if watermark:
        boxes.append(draw_text_box(draw, watermark[:80], (64, 2490, 1376, 2540), 26, ink, minimum=20))
    canvas.save(output, 'PNG')
    return boxes
