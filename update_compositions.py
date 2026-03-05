#!/usr/bin/env python3
"""
Update compositions for new layouts
"""

layout_compositions = {
    "THE MAGNIFYING GLASS": "Extreme macro zoom style. Show a magnified view through a circular lens of rock texture with microscopic gold inclusions, sulfide crystals, or mineral grains. The magnifying glass frame is visible at edges. Ultra-detailed texture.",
    
    "BEFORE & AFTER": "Split vertical composition. Left side labeled 'BEFORE' shows normal river conditions. Right side labeled 'AFTER' shows post-flood changes with exposed bedrock, new gravel bars, and shifted gold deposits. Clear dividing line.",
    
    "THE GEOLOGIST'S NOTEBOOK": "Hand-drawn field journal style. Sketched illustrations of rocks, veins, or terrain features with handwritten annotations, arrows, circles highlighting key features. Aged paper texture with coffee stains and pencil marks.",
    
    "3D BLOCK DIAGRAM": "Isometric 3D cutaway block of earth layers. Show surface terrain on top, then soil layers, gravel, and bedrock below. Gold veins or deposits visible cutting through layers. Clean technical illustration with depth.",
    
    "THE PROSPECTOR'S MAP": "Topographic map view from above. Contour lines showing elevation, blue lines for streams, X marks for sample locations. Legend box in corner. Looks like a technical treasure map with grid coordinates."
}

import re

# Read file
with open('goldgen_service.py', 'r') as f:
    lines = f.readlines()

# Process line by line
output = []
current_layout = None
for i, line in enumerate(lines):
    # Detect layout
    if '"layout":' in line:
        match = re.search(r'"layout": "(.*?)"', line)
        if match:
            current_layout = match.group(1)
    
    # Replace composition if it's a new layout
    if '"composition":' in line and current_layout in layout_compositions:
        indent = len(line) - len(line.lstrip())
        new_comp = layout_compositions[current_layout]
        output.append(' ' * indent + f'"composition": "{new_comp}"\n')
    else:
        output.append(line)

# Write back
with open('goldgen_service.py', 'w') as f:
    f.writelines(output)

print("✅ Updated compositions for new layouts:")
for layout in layout_compositions:
    print(f"   - {layout}")
