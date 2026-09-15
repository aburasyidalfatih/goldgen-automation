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
 "THE PROSPECTOR'S MAP": ('#eae6d0', '#263d35', '#af7a2b', 'One readable conceptual terrain map with a dominant blue stream, restrained contours and sparse observation locations. No invented coordinates, treasure X marks or guaranteed deposits.'),
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
    return f'''VISUAL EXECUTION ({DESIGN_VERSION}):
{composition}
{mode}
Palette: background {bg}, dark/light contrast {ink}, restrained accent {accent}.
Keep one dominant focal subject and a clear reading path. No redundant panels.
Use gold only where supported by the topic, at illustrative abundance, never in every layer.
Do not invent numerical depths, scale bars, coordinates, recovery rates or guarantees.
Respect topic-specific limitations. Simplify decoration before shrinking meaningful detail.
'''


def artwork_prompt(topic, plan):
    import json
    from core.prospecting_style import artwork_style
    # Arahan gaya MENGGANTIKAN instruksi "cinematic photorealistic 3D" yang
    # dulu ada di sini, bukan menumpuknya. Dua arahan estetika yang
    # bertentangan dalam satu prompt membuat model memilih salah satu secara
    # acak — persis kegagalan yang dulu terjadi saat daftar hook generik
    # tampil berdampingan dengan hook yang diwajibkan.
    return execution(topic) + '\n' + artwork_style() + '''
Create ONLY the illustration for a professionally typeset vertical educational poster.
Fill the entire square image edge to edge with a complete scene.
NEVER render an isolated object floating in empty whitespace, blank white background, or floating isolated cubes.
Always embed the cutaway or subject within a full natural environment with real depth, lighting and texture.
NO TEXT anywhere: no letters, numbers, labels, symbols resembling writing, titles,
subtitles, watermarks, legends, pointer lines, arrows, callout boxes, or fake handwriting.
The application adds all typography, numbered badges, and labels in post-processing.
Fill the square image edge to edge with the illustration; keep key objects inside 5% safe margins.
Use the content below ONLY as semantic reference for visual features to paint, never copy words into the image.
Do not reserve blank text panels. Labels will appear in a separate reader key below.
Depict only caption-supported mechanisms; never add chemical extraction instructions.
Quiz alternatives must match the approved caption, in reading order: top-left,
top-right, bottom-left, bottom-right. The application adds A-D markers afterwards.
''' + json.dumps({'topic': topic.get('headline'), 'caption': topic.get('approved_caption'),
                 'points': topic.get('list_points'), 'visual_mode': topic.get('visual_mode'),
                 'reader_key': plan.get('labels', []),
                 'art_direction': plan.get('art_direction', {})}, ensure_ascii=True)
