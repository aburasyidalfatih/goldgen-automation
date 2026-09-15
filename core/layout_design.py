"""Versioned visual execution for every catalog layout, including old volumes."""
DESIGN_VERSION = 'editorial-v3'
# Exact names are intentional: MODERN VECTOR must never match INDUSTRIAL.
DESIGNS = {
 'DEEP CUTAWAY EXPLAINER': ('#122228', '#f2e8d0', '#d8b058', 'Cinematic photorealistic 3D National Geographic deep stratigraphic cutaway render filling the frame edge to edge. Clear vertical depth profile showing natural surface mountain stream, stratified river gravels, dense black magnetite paystreak, and basal bedrock fracture traps with glistening raw gold nuggets. Rich earth tones, 8K photorealistic geological textures, dramatic natural lighting.'),
 'CROSS-SECTION CUTAWAY': ('#f5eedb', '#1c2826', '#b38728', 'Expedition Field Guide style: One sweeping photorealistic 3D river cross-section filling the frame edge to edge. Crystal-clear running water with caustics, graded river gravel strata, dense dark magnetite black sand paystreak, and fractured metamorphic bedrock interface trapping natural gold flakes. Dramatic daylight, photorealistic 8K geological textures.'),
 'VISUAL CHECKLIST': ('#f0e7d5', '#29382e', '#aa792e', 'One large field scene with three visually distinct observation details arranged around it. This is a visual inspection guide, not a wall of bullets or an unrelated before/after comparison.'),
 'STEP-BY-STEP PROCESS': ('#f3ead8', '#263a35', '#b28636', 'Three connected stages of the approved mechanism with equal visual rhythm, one clear direction and consistent viewpoint. Do not invent a final gold discovery.'),
 'GAMIFICATION_QUIZ': ('#f4eddf', '#273831', '#a97b2f', 'Four equally sized observation panels in a precise 2x2 grid. Use consistent lighting and scale; depict only the alternatives described by the caption. No answer revealed by exaggerated glow.'),
 'FIELD SIGNS GRID': ('#ede6d5', '#26342e', '#a8752a', 'A disciplined 2x2 grid of four meaningful field details, matched magnification and lighting. Eliminate ornamental borders and unrelated specimens.'),
 'THE GOLDEN PATH': ('#153339', '#f1e8cf', '#ddb95d', 'One continuous source-to-deposition visual journey. Use an elegant curved flow line and at most three focal stops, not separate disconnected diagrams.'),
 'THE MAGNIFYING GLASS': ('#182b31', '#f3e8d3', '#d2ab57', 'One dominant specimen and one magnified inset showing a specific caption-supported feature. Keep the outer image sharp enough for context; no invented microscopic deposits.'),
 'BEFORE & AFTER': ('#eee6d4', '#23352f', '#ad7e34', 'Two balanced views of the SAME location from the SAME camera angle, separated vertically into left and right panels. Only caption-supported differences; matching scale, horizon and lighting.'),
 "THE GEOLOGIST'S NOTEBOOK": ('#f4ecdc', '#22332a', '#ad7d32', 'Vintage expedition journal on aged parchment paper. Highly detailed watercolor and ink scientific illustration of river deposition or mineral contact zones. Authentic naturalist plate aesthetic.'),
 '3D BLOCK DIAGRAM': ('#f4eedd', '#1f2d27', '#b58832', 'Cinematic photorealistic 3D National Geographic environmental cutaway render filling the frame edge to edge. Crystal-clear flowing mountain stream with sunlight caustics, stratified gravel and cobbles, deep black magnetite sand paystreak layer, and fractured bedrock traps containing gleaming raw gold nuggets. Rich cinematic daylight, 8K realistic textures, high dynamic range. Absolutely NO floating white background cubes, NO line art, NO flat vector sketches.'),
 # "guaranteed deposits" DIHAPUS dari kalimat ini dengan sengaja. Frasa itu
 # persis salah satu istilah terlarang yang dipindai _preflight_image_plan,
 # sehingga layout ini menjegal dirinya sendiri: arahan seni ditolak, prompt
 # dasar ditolak, lalu jatuh ke poster PIL yang kini ditahan gerbang publikasi.
 # Akibatnya setiap postingan THE PROSPECTOR'S MAP gagal total.
 "THE PROSPECTOR'S MAP": ('#eae6d0', '#263d35', '#af7a2b', 'One readable conceptual terrain map with a dominant blue stream, restrained contours and sparse observation locations. No invented coordinates, treasure X marks, or claims that a spot is proven.'),
 'TOOLKIT FLATLAY': ('#e8e0cd', '#263932', '#aa7a30', 'Premium overhead field-tool arrangement with one hero item and at most four supporting objects actually relevant to the topic. Natural soft shadows, orderly spacing, no decorative gear border.'),
 'VICTORIAN WOODCUT': ('#f0e2c4', '#302e24', '#ac7935', 'One strong historical engraved geological scene. Dense hatching only in shadow areas, open highlights, crisp silhouettes and very restrained gold accents. Avoid uniform visual noise.'),
 'MODERN INDUSTRIAL': ('#e9ebe5', '#23343a', '#c5752c', 'One clean technical editorial scene about the APPROVED TOPIC. Use graphite, mineral neutrals and restrained orange accents. Include machinery only if the caption actually discusses it; no generic equipment montage or SAFETY header.'),
 'DARK MAXIMALIST': ('#101518', '#f5e8c8', '#d4af37', 'Luxury dark collector edition: Moody charcoal-black background with subtle ornate filigree border accents. High-contrast, hyper-detailed mineral specimens or dramatic river cutaway with glowing metallic gold highlights under focused studio lighting.'),
 'MODERN VECTOR': ('#edf0e4', '#173a3d', '#b57f2f', 'A precise FLAT VECTOR educational illustration. Solid mineral colors, clear silhouettes, consistent stroke widths and simple geometry. One dominant mechanism and at most three supporting forms. No photography, 3D machinery or grunge.'),
}


def design(name):
    return DESIGNS.get(name, DESIGNS['CROSS-SECTION CUTAWAY'])


def execution(topic):
    bg, ink, accent, composition = design(topic.get('layout'))
    mode = ''
    if topic.get('layout') == 'DEEP CUTAWAY EXPLAINER':
        mode = {'micro': 'Make one mineral specimen the main subject instead of a landscape; show schematic microscopic details only.',
                'journey': 'Show a connected source-to-slope-to-valley section.',
                'cutaway': 'Show the surface in the upper fifth of the illustration and a dominant section below.'}.get(topic.get('visual_mode', 'cutaway'), '')
    # Palet {bg}/{ink}/{accent} SENGAJA tidak dikirim ke model gambar. Itu palet
    # POSTER-nya, yang digambar PIL (lihat design() di core/poster_renderer.py).
    # Menyuruh model memakai latar krem membuat ilustrasinya ikut pucat dan
    # seragam, padahal ia hanya menempati kotak di tengah poster.
    #
    # Larangan "jangan mengarang kedalaman, skala, koordinat, angka recovery"
    # juga dibuang dari sini: semuanya berupa TEKS, dan gambar ini memang tidak
    # boleh memuat teks sama sekali.
    return f'''VISUAL EXECUTION ({DESIGN_VERSION}):
{composition}
{mode}
Keep one dominant focal subject and a clear reading path.
Use gold only where the topic supports it, at illustrative abundance.
'''


def artwork_prompt(topic, plan):
    import json
    from core.prospecting_style import artwork_style
    # Arahan gaya MENGGANTIKAN instruksi "cinematic photorealistic 3D" yang
    # dulu ada di sini, bukan menumpuknya. Dua arahan estetika yang
    # bertentangan dalam satu prompt membuat model memilih salah satu secara
    # acak — persis kegagalan yang dulu terjadi saat daftar hook generik
    # tampil berdampingan dengan hook yang diwajibkan.
    # Blok ini dipangkas dari 14 baris menjadi 5. Yang dibuang bukan aturan
    # sembarangan, melainkan aturan yang mengurusi TEKS pada gambar yang sudah
    # dilarang bertekst:
    #
    # - "jangan menyisakan panel teks kosong", "label muncul di reader key" —
    #   sudah tercakup oleh NO TEXT
    # - "jangan menambahkan instruksi ekstraksi kimia" — itu urusan caption, dan
    #   menyebutnya di sini malah memasukkan gagasan itu ke konteks visual
    # - aturan urutan kuis A-D — dikirim ke SEMUA layout padahal
    #   GAMIFICATION_QUIZ sudah dipensiunkan, dan ia menyuruh model berpikir
    #   dalam empat panel, persis melawan "one dominant focal subject"
    # - dua kalimat "fill edge to edge" yang saling menduplikasi
    return execution(topic) + '\n' + artwork_style() + '''
Create ONLY the illustration; the application typesets the poster on top of it afterwards.
NO TEXT anywhere: no letters, numbers, labels, watermarks, legends, pointer lines,
callout boxes or fake handwriting.
Fill the tall vertical frame edge to edge with one complete scene in a real
environment with depth, lighting and texture. The illustration IS the poster
background: no empty border, no object floating on blank ground.
Typography is laid over the top eighth and the bottom quarter, so put the dominant
subject in the middle and keep those two bands quieter.
Use the content below only as reference for what to paint.
''' + json.dumps({'topic': topic.get('headline'), 'caption': topic.get('approved_caption'),
                 'points': topic.get('list_points'), 'visual_mode': topic.get('visual_mode'),
                 # Dinamai "features_to_depict", bukan "reader_key": ini daftar
                 # benda yang harus TAMPAK, bukan legenda yang harus ditulis.
                 'features_to_depict': plan.get('labels', []),
                 'art_direction': plan.get('art_direction', {})}, ensure_ascii=True)
