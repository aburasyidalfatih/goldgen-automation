import json

new_topics = [
    {
        "id": 81,
        "headline": "DRY WASHING",
        "subtitle": "Desert Prospecting Without Water",
        "list_header": "HOW IT WORKS",
        "list_points": [
            "Uses air bellows or fans",
            "Vibration mimics water flow",
            "Static electricity catches fine gold",
            "Requires bone-dry dirt"
        ]
    },
    {
        "id": 82,
        "headline": "METAL DETECTOR COILS",
        "subtitle": "DD vs Mono Coils",
        "list_header": "COIL CHOICE MATTERS",
        "list_points": [
            "Mono: Deeper punch, sharp target center",
            "DD: Better in mineralized ground",
            "Small coils: Great for tiny nuggets/crevices",
            "Large coils: Max depth for big targets"
        ]
    },
    {
        "id": 83,
        "headline": "SNIPING FOR GOLD",
        "subtitle": "Underwater Treasure Hunting",
        "list_header": "SNIPING TACTICS",
        "list_points": [
            "Wear a wetsuit and snorkel",
            "Use a bulb snifter or hand dredge",
            "Fanning away sand to expose bedrock",
            "Look into deep cracks others miss"
        ]
    },
    {
        "id": 84,
        "headline": "CLASSIFYING DIRT",
        "subtitle": "Size Matters for Recovery",
        "list_header": "WHY CLASSIFY?",
        "list_points": [
            "Matches material to water flow speed",
            "Prevents large rocks from washing gold out",
            "Speeds up panning significantly",
            "Use 1/4 or 1/2 inch mesh screens"
        ]
    },
    {
        "id": 85,
        "headline": "BLACK SAND RECOVERY",
        "subtitle": "Extracting the Invisible Gold",
        "list_header": "CLEANUP METHODS",
        "list_points": [
            "Super-magnets to remove magnetite",
            "Blue bowl concentrators",
            "Miller tables for fine separation",
            "Tapping the pan to walk gold up"
        ]
    },
    {
        "id": 86,
        "headline": "HIGHBANKING 101",
        "subtitle": "Processing Dirt Faster",
        "list_header": "HIGHBANKER ADVANTAGES",
        "list_points": [
            "Water pump allows working away from river",
            "Built-in grizzly classifying screen",
            "Continuous feeding without bending",
            "Processes 10x more than a pan"
        ]
    },
    {
        "id": 87,
        "headline": "GROUND BALANCING",
        "subtitle": "Silencing the Earth's Noise",
        "list_header": "DETECTOR CALIBRATION",
        "list_points": [
            "Cancels out iron-rich 'hot rocks'",
            "Pump coil over clean ground to set",
            "Re-balance when soil color changes",
            "Crucial for hearing faint nugget signals"
        ]
    },
    {
        "id": 88,
        "headline": "HISTORICAL TAILINGS",
        "subtitle": "Reworking the Old Timers' Waste",
        "list_header": "WHY HUNT TAILINGS?",
        "list_points": [
            "Old technology missed fine gold",
            "Detectors can find nuggets they threw out",
            "Often safe, public access areas",
            "Look for quartz piles and crushed rock"
        ]
    },
    {
        "id": 89,
        "headline": "MOSS & ROOT TRAPS",
        "subtitle": "Nature's Catchers",
        "list_header": "VEGETATION GOLD",
        "list_points": [
            "Moss acts like miner's moss/carpet",
            "Tree roots slow water during floods",
            "Carefully pluck moss and wash in bucket",
            "Often yields very fine 'flour gold'"
        ]
    },
    {
        "id": 90,
        "headline": "THE SPECIFIC GRAVITY",
        "subtitle": "Why Gold Sinks Rapidly",
        "list_header": "UNDERSTANDING WEIGHT",
        "list_points": [
            "Gold is 19.3 times heavier than water",
            "Over 6 times heavier than typical gravel",
            "Will sink through shaking and vibration",
            "Never stops until it hits bedrock or clay"
        ]
    },
    {
        "id": 91,
        "headline": "CALICHE DEPOSITS",
        "subtitle": "Cemented Desert Wealth",
        "list_header": "BREAKING THE HARDPAN",
        "list_points": [
            "Caliche acts like natural concrete",
            "Traps ancient gold deposits tightly",
            "Requires picks, hammers, or soaking",
            "Often confused with barren bedrock"
        ]
    },
    {
        "id": 92,
        "headline": "SLUICE BOX RIFFLES",
        "subtitle": "Catching Different Gold Sizes",
        "list_header": "RIFFLE PROFILES",
        "list_points": [
            "Hungarian Riffles: Creates strong vortexes",
            "Expanded Metal: Catches fine flour gold",
            "V-Matting: Great for early stage catching",
            "Angle matters more than riffle type"
        ]
    },
    {
        "id": 93,
        "headline": "VLF DETECTORS",
        "subtitle": "The Coin Shooter's Upgrade",
        "list_header": "VLF CAPABILITIES",
        "list_points": [
            "Very Low Frequency technology",
            "Excellent discrimination against iron junk",
            "Highly sensitive to tiny nuggets",
            "Struggles in extremely mineralized ground"
        ]
    },
    {
        "id": 94,
        "headline": "PULSE INDUCTION",
        "subtitle": "Punching Deep for Nuggets",
        "list_header": "PI DETECTOR PROS",
        "list_points": [
            "Ignores highly mineralized hot rocks",
            "Achieves extreme depth penetration",
            "Must dig almost every signal (low discrimination)",
            "The choice of professional prospectors"
        ]
    },
    {
        "id": 95,
        "headline": "THE PANNING ANGLE",
        "subtitle": "Finding the Perfect Rhythm",
        "list_header": "PANNING TECHNIQUE",
        "list_points": [
            "Start with vigorous horizontal shaking",
            "Tilt at a 30-degree angle to the water",
            "Wash lighter sands off the front lip",
            "Keep gold safely in the back corner"
        ]
    },
    {
        "id": 96,
        "headline": "FLOOD GOLD ZONES",
        "subtitle": "Post-Storm Riches",
        "list_header": "FRESH DEPOSITS",
        "list_points": [
            "Floods rip gold from banks and banks",
            "Look for new gravel bars after high water",
            "Skim panning surface layers",
            "Gold is usually small and flat (flakes)"
        ]
    },
    {
        "id": 97,
        "headline": "AVOIDING CLAIM JUMPING",
        "subtitle": "Stay Legal, Stay Safe",
        "list_header": "IDENTIFYING CLAIMS",
        "list_points": [
            "Look for PVC pipes, wood posts, or rock cairns",
            "Check BLM or local government databases",
            "Noting 'No Trespassing' or claim signs",
            "Always ask permission if unsure"
        ]
    },
    {
        "id": 98,
        "headline": "MERCURY WARNINGS",
        "subtitle": "Toxic Legacies of the Past",
        "list_header": "HANDLING AMALGAM",
        "list_points": [
            "Old miners used mercury to catch fine gold",
            "Looks like silver-coated gold or dull beads",
            "Never heat or burn it in open air",
            "Store in water and dispose as hazmat"
        ]
    },
    {
        "id": 99,
        "headline": "TEST PANNING",
        "subtitle": "Sampling Before You Sweat",
        "list_header": "WHY SAMPLE?",
        "list_points": [
            "Never move yards of dirt blindly",
            "Pan a small sample from top, middle, bottom",
            "Follow the best color count",
            "Saves hours of wasted energy"
        ]
    },
    {
        "id": 100,
        "headline": "LEAVE NO TRACE",
        "subtitle": "The Prospector's Ethics",
        "list_header": "RESPECTING THE LAND",
        "list_points": [
            "Always fill your holes back in",
            "Pack out all your trash (and others')",
            "Don't dig into live tree roots or banks",
            "Preserve access for future generations"
        ]
    }
]

file_path = 'data/topics.json'
with open(file_path, 'r', encoding='utf-8') as f:
    topics = json.load(f)

# Ensure no duplicates by ID
existing_ids = {t['id'] for t in topics}
for nt in new_topics:
    if nt['id'] not in existing_ids:
        topics.append(nt)

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(topics, f, indent=4)

print(f"Successfully added {len(new_topics)} topics. Total topics is now {len(topics)}.")
