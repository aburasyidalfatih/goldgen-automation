"""Versioned visual execution for every catalog layout, including old volumes."""
DESIGN_VERSION = 'editorial-v2'
# Exact names are intentional: MODERN VECTOR must never match INDUSTRIAL.
DESIGNS = {
 'DEEP CUTAWAY EXPLAINER': ('#14252d', '#f3e8cf', '#d5ac55', 'One dominant geological cutaway; 2-3 circular detail insets connected by thin leader lines. Clearly distinguish rock, sediment and mineral textures.'),
 'CROSS-SECTION CUTAWAY': ('#f3ead8', '#25342e', '#ac792f', 'One sweeping river cross-section with a coherent flow direction, realistic bedrock and sediment interfaces. At most two detail insets; avoid repeating the main diagram.'),
 'VISUAL CHECKLIST': ('#f0e7d5', '#29382e', '#aa792e', 'One large field scene with three visually distinct observation details arranged around it. This is a visual inspection guide, not a wall of bullets or an unrelated before/after comparison.'),
 'STEP-BY-STEP PROCESS': ('#f3ead8', '#263a35', '#b28636', 'Three connected stages of the approved mechanism with equal visual rhythm, one clear direction and consistent viewpoint. Do not invent a final gold discovery.'),
 'GAMIFICATION_QUIZ': ('#f4eddf', '#273831', '#a97b2f', 'Four equally sized observation panels in a precise 2x2 grid. Use consistent lighting and scale; depict only the alternatives described by the caption. No answer revealed by exaggerated glow.'),
 'FIELD SIGNS GRID': ('#ede6d5', '#26342e', '#a8752a', 'A disciplined 2x2 grid of four meaningful field details, matched magnification and lighting. Eliminate ornamental borders and unrelated specimens.'),
 'THE GOLDEN PATH': ('#153339', '#f1e8cf', '#ddb95d', 'One continuous source-to-deposition visual journey. Use an elegant curved flow line and at most three focal stops, not separate disconnected diagrams.'),
 'THE MAGNIFYING GLASS': ('#182b31', '#f3e8d3', '#d2ab57', 'One dominant specimen and one magnified inset showing a specific caption-supported feature. Keep the outer image sharp enough for context; no invented microscopic deposits.'),
 'BEFORE & AFTER': ('#eee6d4', '#23352f', '#ad7e34', 'Two balanced views of the SAME location from the SAME camera angle, separated vertically into left and right panels. Only caption-supported differences; matching scale, horizon and lighting.'),
 "THE GEOLOGIST'S NOTEBOOK": ('#f1e5cb', '#303d30', '#a87530', 'A clean field-journal plate: one precise ink-and-watercolor study and two small detail sketches. Rich mineral colors, crisp lines and disciplined negative space. No fake handwriting or coffee-stain clutter.'),
 '3D BLOCK DIAGRAM': ('#e6e9df', '#263b37', '#ae833b', 'One large isometric geological block with physically coherent faces and layers. Use directional light to separate surfaces. At most two detail callouts; no exploded-layer collage.'),
 "THE PROSPECTOR'S MAP": ('#eae6d0', '#263d35', '#af7a2b', 'One readable conceptual terrain map with a dominant blue stream, restrained contours and sparse observation locations. No invented coordinates, treasure X marks or guaranteed deposits.'),
 'TOOLKIT FLATLAY': ('#e8e0cd', '#263932', '#aa7a30', 'Premium overhead field-tool arrangement with one hero item and at most four supporting objects actually relevant to the topic. Natural soft shadows, orderly spacing, no decorative gear border.'),
 'VICTORIAN WOODCUT': ('#f0e2c4', '#302e24', '#ac7935', 'One strong historical engraved geological scene. Dense hatching only in shadow areas, open highlights, crisp silhouettes and very restrained gold accents. Avoid uniform visual noise.'),
 'MODERN INDUSTRIAL': ('#e9ebe5', '#23343a', '#c5752c', 'One clean technical editorial scene about the APPROVED TOPIC. Use graphite, mineral neutrals and restrained orange accents. Include machinery only if the caption actually discusses it; no generic equipment montage or SAFETY header.'),
 'DARK MAXIMALIST': ('#101e25', '#f4e5c2', '#dbb360', 'One dramatic geological hero on deep charcoal with controlled metallic highlights. Achieve richness through material detail and directional light, not ornate frames, glowing rivers or piles of treasure. At most two subordinate insets.'),
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
    return execution(topic) + '''
Create ONLY the illustration for a professionally typeset vertical educational poster.
NO TEXT anywhere: no letters, numbers, labels, symbols resembling writing, titles,
watermarks, legends or fake handwriting. The application adds all text afterwards.
Fill the square image edge to edge with the illustration; keep key objects inside 5% safe margins.
Use the content below ONLY as semantic reference, never copy its words into the image.
Do not reserve blank text panels. Labels will appear in a separate reader key below.
Depict only caption-supported mechanisms; never add chemical extraction instructions.
Quiz alternatives must match the approved caption, in reading order: top-left,
top-right, bottom-left, bottom-right. The application adds A-D markers afterwards.
''' + json.dumps({'topic': topic.get('headline'), 'caption': topic.get('approved_caption'),
                 'points': topic.get('list_points'), 'visual_mode': topic.get('visual_mode'),
                 'reader_key': plan.get('labels', []),
                 'art_direction': plan.get('art_direction', {})}, ensure_ascii=True)
