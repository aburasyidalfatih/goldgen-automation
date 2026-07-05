import json
from goldgen_service import GoldGenService

service = GoldGenService('dummy')

# Mock topics with different layouts
topics = [
    {
        "headline": "Spotting Placer Gold",
        "subtitle": "Where rivers hide their treasure",
        "list_points": [
            "Inside bends of rivers",
            "Behind large boulders",
            "Where water suddenly slows down"
        ],
        "layout": "MAP",
        "composition": "Top-down view of a winding river showing deposition zones."
    },
    {
        "headline": "Ruby Companions",
        "subtitle": "Garnets signal heavy ground",
        "list_points": [
            "Deep red color",
            "Glassy luster",
            "Often dodecahedral shape",
            "Found with black sand"
        ],
        "layout": "3D BLOCK",
        "composition": "Cross-section showing garnets accumulating in bedrock crevices."
    },
    {
        "headline": "The Pyrite Deception",
        "subtitle": "Fool's Gold vs Real Gold",
        "list_points": [
            "Pyrite is brittle, gold is malleable",
            "Pyrite has black streak, gold is yellow",
            "Pyrite forms sharp crystals"
        ],
        "layout": "NOTEBOOK",
        "composition": "Geologist notes comparing two mineral samples."
    }
]

for idx, t in enumerate(topics):
    prompt = service.generate_image_prompt(t)
    print(f"--- PROMPT {idx + 1}: {t['layout']} ---")
    print(prompt)
    print("\n" + "="*50 + "\n")
