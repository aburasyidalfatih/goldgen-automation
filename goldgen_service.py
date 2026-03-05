#!/usr/bin/env python3
"""
GoldGen Service - Generate educational content about gold prospecting
"""

from google import genai
import os
import json
from pathlib import Path
from datetime import datetime

class GoldGenService:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-3-flash-preview'
        
        # Topic rotation state
        self.state_file = Path(__file__).parent / "data" / "topic_state.json"
        
        # 10 Layouts - rotates every topic
        self.layouts = [
            {
                "name": "CROSS-SECTION CUTAWAY",
                "composition": "A realistic National Geographic style cross-section of a river bend. Show the water velocity slowing down on the inside curve, depositing gold flakes in the gravel layers. Bright daylight lighting, educational labels."
            },
            {
                "name": "VISUAL CHECKLIST",
                "composition": "Survivor Manual aesthetic. Rough wood or dirt background. A rugged illustration of a dry riverbed showing exposed bedrock crevices filled with packed gravel and gold. Tools like pickaxes and pans arranged as borders."
            },
            {
                "name": "STEP-BY-STEP PROCESS",
                "composition": "Vintage Field Guide aesthetic. Aged parchment paper texture background. Hand-drawn scientific illustration of a 'rotten' quartz vein with iron oxide stains versus a sterile white quartz chunk. Typography looks like an old manual."
            },
            {
                "name": "FIELD SIGNS GRID",
                "composition": "Dark Rock Macro style. Extreme close-up of a rusty, oxidized rock surface. The red and orange iron stains contrast with the dark rock matrix. A small vein of gold is visible within the rust. High contrast lighting."
            },
            {
                "name": "THE GOLDEN PATH",
                "composition": "Detailed Diagrammatic style. A split screen showing a gold pan. Top half: The raw gravel mix. Bottom half: The concentrated black sand with gold flakes at the edge. Arrows indicate the panning motion to separate the layers."
            },
            {
                "name": "THE MAGNIFYING GLASS",
                "composition": "Extreme macro zoom style. Show a magnified view through a circular lens of rock texture with microscopic gold inclusions, sulfide crystals, or mineral grains. The magnifying glass frame is visible at edges. Ultra-detailed texture."
            },
            {
                "name": "BEFORE & AFTER",
                "composition": "Split vertical composition. Left side labeled 'BEFORE' shows normal river conditions. Right side labeled 'AFTER' shows post-flood changes with exposed bedrock, new gravel bars, and shifted gold deposits. Clear dividing line."
            },
            {
                "name": "THE GEOLOGIST'S NOTEBOOK",
                "composition": "Hand-drawn field journal style. Sketched illustrations of rocks, veins, or terrain features with handwritten annotations, arrows, circles highlighting key features. Aged paper texture with coffee stains and pencil marks."
            },
            {
                "name": "3D BLOCK DIAGRAM",
                "composition": "Isometric 3D cutaway block of earth layers. Show surface terrain on top, then soil layers, gravel, and bedrock below. Gold veins or deposits visible cutting through layers. Clean technical illustration with depth."
            },
            {
                "name": "THE PROSPECTOR'S MAP",
                "composition": "Topographic map view from above. Contour lines showing elevation, blue lines for streams, X marks for sample locations. Legend box in corner. Looks like a technical treasure map with grid coordinates."
            }
        ]
        
        self.topics = [
            {
                "id": 1,
                "headline": "READING THE RIVER",
                "subtitle": "Gold drops where water slows down.",
                "list_header": "KEY DEPOSIT ZONES",
                "list_points": [
                    "Inside bends (Low Pressure Zone)",
                    "Behind large boulders (Eddies)",
                    "Bedrock cracks (Natural Riffles)",
                    "Moss roots (Fine Gold Traps)"
                ],            },
            {
                "id": 2,
                "headline": "BEDROCK TRAPS",
                "subtitle": "Nature's own sluice box.",
                "list_header": "TRAP TYPES",
                "list_points": [
                    "Vertical crevices (Deep catchers)",
                    "Boiler holes (Swirling traps)",
                    "Rough slate edges (Natural Riffles)",
                    "Limestone pockets (Chemical traps)"
                ],            },
            {
                "id": 3,
                "headline": "QUARTZ INDICATORS",
                "subtitle": "Rusty and rotten holds the fortune.",
                "list_header": "WHAT TO LOOK FOR",
                "list_points": [
                    "Iron staining (Red/Orange Oxide)",
                    "Boxwork texture (Honeycombed)",
                    "Sulfide presence (Pyrite/Arsenopyrite)",
                    "Fractured structure (Not solid white)"
                ],            },
            {
                "id": 4,
                "headline": "IRON STAINING",
                "subtitle": "Rust is the color of money.",
                "list_header": "OXIDATION SIGNS",
                "list_points": [
                    "Red Hematite stains",
                    "Orange Limonite crusts",
                    "Black Manganese coatings",
                    "Gossan caps on veins"
                ],            },
            {
                "id": 5,
                "headline": "BLACK SAND SECRETS",
                "subtitle": "Heavy minerals lead the way.",
                "list_header": "COMPOSITION",
                "list_points": [
                    "Magnetite (Magnetic)",
                    "Hematite (Non-magnetic red)",
                    "Ilmenite (Titanium iron)",
                    "Gold (Heaviest of all)"
                ],            },
            {
                "id": 6,
                "headline": "GOLD VS PYRITE",
                "subtitle": "The hammer never lies.",
                "list_header": "FIELD TEST",
                "list_points": [
                    "Gold: Dents / Malleable",
                    "Pyrite: Shatters / Brittle",
                    "Gold: Yellow in shade",
                    "Pyrite: Greenish-grey in shade"
                ],            },
            {
                "id": 7,
                "headline": "ANCIENT CHANNELS",
                "subtitle": "High benches hold forgotten wealth.",
                "list_header": "LOCATING BENCHES",
                "list_points": [
                    "Rounded river rocks on hillsides",
                    "Flat distinct terraces above river",
                    "Color change in soil layers",
                    "Old vegetation lines"
                ],            },
            {
                "id": 8,
                "headline": "PLACER VS LODE",
                "subtitle": "Tracking the source upstream.",
                "list_header": "DEPOSIT TYPES",
                "list_points": [
                    "Placer: Rounded & Smooth (Water worn)",
                    "Lode: Jagged & Rough (Near source)",
                    "Placer: Riverbeds & Benches",
                    "Lode: Veins & Hard Rock"
                ],            },
            {
                "id": 9,
                "headline": "RUBY COMPANIONS",
                "subtitle": "Garnets signal heavy ground.",
                "list_header": "IDENTIFICATION",
                "list_points": [
                    "Deep red color",
                    "Glassy luster",
                    "Often dodecahedral shape",
                    "Found with black sand"
                ],            },
            {
                "id": 10,
                "headline": "FALSE BEDROCK",
                "subtitle": "Clay layers trap gold too.",
                "list_header": "CLAY SIGNS",
                "list_points": [
                    "Impermeable sticky layer",
                    "Blue or grey color often",
                    "Gold sits ON TOP of it",
                    "Don't dig through it!"
                ],            }
            ,{
                "id": 11,
                "headline": "SULFIDES",
                "subtitle": "The invisible gold host.",
                "list_header": "KEY SULFIDE MINERALS",
                "list_points": [
                    "Pyrite (Iron sulfide - Gold carrier)",
                    "Arsenopyrite (Arsenic-iron sulfide)",
                    "Chalcopyrite (Copper-iron sulfide)",
                    "Pyrrhotite (Magnetic iron sulfide)"
                ],            }
            ,{
                "id": 12,
                "headline": "GOSSAN CAPS",
                "subtitle": "The rusty hat of a gold vein.",
                "list_header": "GOSSAN INDICATORS",
                "list_points": [
                    "Iron oxide cap (Rusty red/brown)",
                    "Porous boxwork texture",
                    "Sits above sulfide zone",
                    "Limonite and hematite rich"
                ],            }
            ,{
                "id": 13,
                "headline": "CONTACT ZONES",
                "subtitle": "Where geology changes.",
                "list_header": "CONTACT TYPES",
                "list_points": [
                    "Intrusive-sedimentary contacts",
                    "Limestone-granite boundaries",
                    "Dike-host rock interfaces",
                    "Metamorphic grade changes"
                ],            }
            ,{
                "id": 14,
                "headline": "FAULT LINES",
                "subtitle": "Nature's gold plumbing.",
                "list_header": "FAULT ZONE FEATURES",
                "list_points": [
                    "Crushed rock (Breccia zones)",
                    "Quartz veins along fault",
                    "Slickensides (Polished surfaces)",
                    "Clay gouge (Fault filling)"
                ],            }
            ,{
                "id": 15,
                "headline": "SKARN DEPOSITS",
                "subtitle": "Gold in limestone.",
                "list_header": "SKARN MINERALS",
                "list_points": [
                    "Garnet (Red-brown crystals)",
                    "Epidote (Green alteration)",
                    "Magnetite (Black magnetic)",
                    "Calcite replacement zones"
                ],            }
            ,{
                "id": 16,
                "headline": "PORPHYRY SYSTEMS",
                "subtitle": "Low grade, huge tonnage.",
                "list_header": "PORPHYRY INDICATORS",
                "list_points": [
                    "Stockwork vein networks",
                    "Disseminated sulfides",
                    "Potassic alteration (Pink)",
                    "Large intrusive body"
                ],            }
            ,{
                "id": 17,
                "headline": "EPITHERMAL VEINS",
                "subtitle": "Boiling zone bonanzas.",
                "list_header": "EPITHERMAL TEXTURES",
                "list_points": [
                    "Banded quartz (Crustiform)",
                    "Bladed calcite (After boiling)",
                    "Colloform banding",
                    "Platy calcite pseudomorphs"
                ],            }
            ,{
                "id": 18,
                "headline": "GREENSTONE BELTS",
                "subtitle": "Ancient volcanic gold.",
                "list_header": "GREENSTONE FEATURES",
                "list_points": [
                    "Metamorphosed volcanics",
                    "Chlorite-rich (Green color)",
                    "Shear zone hosted",
                    "Archean age rocks"
                ],            }
            ,{
                "id": 19,
                "headline": "SLATE BELTS",
                "subtitle": "The nugget factories.",
                "list_header": "SLATE BELT SIGNS",
                "list_points": [
                    "Fine-grained metamorphic rock",
                    "Quartz veins cutting slate",
                    "Coarse gold common",
                    "Historic mining areas"
                ],            }
            ,{
                "id": 20,
                "headline": "GLACIAL GOLD",
                "subtitle": "Moraines and flour gold.",
                "list_header": "GLACIAL INDICATORS",
                "list_points": [
                    "Rounded boulders (Glacial till)",
                    "Fine flour gold",
                    "Erratic gold distribution",
                    "Moraine deposits"
                ],            }
            ,{
                "id": 21,
                "headline": "DESERT PROSPECTING",
                "subtitle": "Dry washing tactics.",
                "list_header": "DRY WASHING METHODS",
                "list_points": [
                    "Dry washer equipment",
                    "Wind classification",
                    "Desert pavement indicators",
                    "Arroyo concentrations"
                ],            }
            ,{
                "id": 22,
                "headline": "BEACH PLACERS",
                "subtitle": "Wave action gold.",
                "list_header": "BEACH GOLD ZONES",
                "list_points": [
                    "Black sand layers",
                    "Storm berms",
                    "Bedrock outcrops",
                    "Tidal concentration zones"
                ],            }
            ,{
                "id": 23,
                "headline": "ELUVIAL DEPOSITS",
                "subtitle": "Gold that hasn't moved.",
                "list_header": "ELUVIAL CHARACTERISTICS",
                "list_points": [
                    "Angular gold pieces",
                    "Still near source vein",
                    "Weathered host rock",
                    "Hillside deposits"
                ],            }
            ,{
                "id": 24,
                "headline": "RESIDUAL DEPOSITS",
                "subtitle": "Weathered in place.",
                "list_header": "RESIDUAL FEATURES",
                "list_points": [
                    "Laterite soil profile",
                    "Gold enrichment at depth",
                    "Tropical weathering",
                    "Iron-rich surface"
                ],            }
            ,{
                "id": 25,
                "headline": "SPECIFIC GRAVITY",
                "subtitle": "Why gold sinks.",
                "list_header": "DENSITY COMPARISON",
                "list_points": [
                    "Gold: 19.3 g/cm³",
                    "Magnetite: 5.2 g/cm³",
                    "Quartz: 2.65 g/cm³",
                    "Water: 1.0 g/cm³"
                ],            }
            ,{
                "id": 26,
                "headline": "THE STREAK TEST",
                "subtitle": "Gold vs. Chalcopyrite.",
                "list_header": "STREAK COLORS",
                "list_points": [
                    "Gold: Golden yellow streak",
                    "Chalcopyrite: Greenish-black streak",
                    "Pyrite: Greenish-black streak",
                    "Use unglazed porcelain"
                ],            }
            ,{
                "id": 27,
                "headline": "ARSENOPYRITE",
                "subtitle": "The garlic-smelling indicator.",
                "list_header": "ARSENOPYRITE SIGNS",
                "list_points": [
                    "Silvery metallic luster",
                    "Garlic smell when struck",
                    "Often gold-bearing",
                    "Orthorhombic crystals"
                ],            }
            ,{
                "id": 28,
                "headline": "GALENA",
                "subtitle": "Silver-lead and gold friends.",
                "list_header": "GALENA INDICATORS",
                "list_points": [
                    "Cubic cleavage (Perfect cubes)",
                    "Lead-gray metallic",
                    "Often with silver and gold",
                    "Heavy mineral"
                ],            }
            ,{
                "id": 29,
                "headline": "MAGNETITE VS HEMATITE",
                "subtitle": "Know your irons.",
                "list_header": "IRON OXIDE TYPES",
                "list_points": [
                    "Magnetite: Black, magnetic",
                    "Hematite: Red-brown, non-magnetic",
                    "Magnetite: Fe3O4",
                    "Hematite: Fe2O3"
                ],            }
            ,{
                "id": 30,
                "headline": "SERPENTINE ROCK",
                "subtitle": "The green host.",
                "list_header": "SERPENTINE FEATURES",
                "list_points": [
                    "Green waxy appearance",
                    "Slippery feel",
                    "Altered ultramafic rock",
                    "Often with chromite"
                ],            }
            ,{
                "id": 31,
                "headline": "CALCITE VS QUARTZ",
                "subtitle": "The acid test.",
                "list_header": "IDENTIFICATION TESTS",
                "list_points": [
                    "Calcite: Fizzes in acid",
                    "Quartz: No reaction",
                    "Calcite: Softer (H=3)",
                    "Quartz: Harder (H=7)"
                ],            }
            ,{
                "id": 32,
                "headline": "BOXWORK TEXTURE",
                "subtitle": "Where sulfides used to be.",
                "list_header": "BOXWORK INDICATORS",
                "list_points": [
                    "Honeycomb pattern",
                    "Iron oxide framework",
                    "Former sulfide location",
                    "Porous structure"
                ],            }
            ,{
                "id": 33,
                "headline": "BOILING ZONES",
                "subtitle": "Textures of epithermal gold.",
                "list_header": "BOILING TEXTURES",
                "list_points": [
                    "Platy calcite (Bladed)",
                    "Lattice bladed texture",
                    "Colloform banding",
                    "Crustiform layering"
                ],            }
            ,{
                "id": 34,
                "headline": "NUGGET PATCHES",
                "subtitle": "Detecting shallow ground.",
                "list_header": "NUGGET INDICATORS",
                "list_points": [
                    "Coarse gold in patches",
                    "Shallow bedrock",
                    "Detector targets",
                    "Erratic distribution"
                ],            }
            ,{
                "id": 35,
                "headline": "PAYSTREAKS",
                "subtitle": "Path of least resistance.",
                "list_header": "PAYSTREAK FEATURES",
                "list_points": [
                    "Narrow gold-rich zones",
                    "Follow old channels",
                    "Bedrock irregularities",
                    "Concentrated heavy minerals"
                ],            }
            ,{
                "id": 36,
                "headline": "FLOOD GOLD",
                "subtitle": "Skim bars and moss mats.",
                "list_header": "FLOOD DEPOSITS",
                "list_points": [
                    "High water deposits",
                    "Skim bars (Surface gold)",
                    "Moss and root mats",
                    "Flood debris piles"
                ],            }
            ,{
                "id": 37,
                "headline": "CREVICING",
                "subtitle": "Snipping gold from cracks.",
                "list_header": "CREVICING TOOLS",
                "list_points": [
                    "Crevice tools (Picks, spoons)",
                    "Snuffer bottle",
                    "Bedrock cracks",
                    "Exposed bedrock areas"
                ],            }
            ,{
                "id": 38,
                "headline": "BOOMING",
                "subtitle": "Ancient water methods.",
                "list_header": "BOOMING TECHNIQUE",
                "list_points": [
                    "Dam and release water",
                    "Wash overburden away",
                    "Expose bedrock",
                    "Historic method"
                ],            }
            ,{
                "id": 39,
                "headline": "MERCURY IN GOLD",
                "subtitle": "The amalgam danger.",
                "list_header": "MERCURY HAZARDS",
                "list_points": [
                    "Toxic heavy metal",
                    "Forms gold amalgam",
                    "Historic use in mining",
                    "Environmental contamination"
                ],            }
            ,{
                "id": 40,
                "headline": "TELLURIDES",
                "subtitle": "The silver-gold mix.",
                "list_header": "TELLURIDE MINERALS",
                "list_points": [
                    "Calaverite (Gold telluride)",
                    "Sylvanite (Gold-silver telluride)",
                    "Petzite (Silver-gold telluride)",
                    "Often high-grade"
                ],            }
            ,{
                "id": 41,
                "headline": "CARLIN-TYPE GOLD",
                "subtitle": "Invisible and disseminated.",
                "list_header": "CARLIN CHARACTERISTICS",
                "list_points": [
                    "Submicroscopic gold",
                    "Sediment-hosted",
                    "Arsenic association",
                    "Large tonnage, low grade"
                ],            }
            ,{
                "id": 42,
                "headline": "OROGENIC GOLD",
                "subtitle": "Mountain building riches.",
                "list_header": "OROGENIC FEATURES",
                "list_points": [
                    "Shear zone hosted",
                    "Metamorphic setting",
                    "Quartz-carbonate veins",
                    "Mesothermal depth"
                ],            }
            ,{
                "id": 43,
                "headline": "VMS DEPOSITS",
                "subtitle": "Volcanic massive sulfides.",
                "list_header": "VMS INDICATORS",
                "list_points": [
                    "Massive sulfide lenses",
                    "Volcanic host rocks",
                    "Base metals with gold",
                    "Seafloor origin"
                ],            }
            ,{
                "id": 44,
                "headline": "WITWATERSRAND",
                "subtitle": "The pebble conglomerates.",
                "list_header": "WITWATERSRAND TYPE",
                "list_points": [
                    "Placer conglomerate",
                    "Rounded quartz pebbles",
                    "Pyrite and uraninite",
                    "Ancient river deposits"
                ],            }
            ,{
                "id": 45,
                "headline": "BRECCIA PIPES",
                "subtitle": "Exploded rock gold.",
                "list_header": "BRECCIA FEATURES",
                "list_points": [
                    "Angular rock fragments",
                    "Pipe-like structure",
                    "Hydrothermal alteration",
                    "Gold in matrix"
                ],            }
            ,{
                "id": 46,
                "headline": "SHEAR ZONES",
                "subtitle": "Crushed rock pathways.",
                "list_header": "SHEAR ZONE SIGNS",
                "list_points": [
                    "Foliated rock fabric",
                    "Quartz veins parallel to shear",
                    "Mylonite texture",
                    "Linear structural trend"
                ],            }
            ,{
                "id": 47,
                "headline": "FOLD HINGES",
                "subtitle": "Structural traps.",
                "list_header": "FOLD HINGE FEATURES",
                "list_points": [
                    "Maximum curvature zone",
                    "Dilation and fracturing",
                    "Quartz vein concentration",
                    "Gold enrichment"
                ],            }
            ,{
                "id": 48,
                "headline": "SADDLE REEFS",
                "subtitle": "Gold at the top of the fold.",
                "list_header": "SADDLE REEF STRUCTURE",
                "list_points": [
                    "Anticlinal fold crest",
                    "Saddle-shaped quartz body",
                    "Bedding-parallel veins",
                    "Classic Victorian goldfields"
                ],            }
            ,{
                "id": 49,
                "headline": "STOCKWORKS",
                "subtitle": "Networks of tiny veins.",
                "list_header": "STOCKWORK PATTERNS",
                "list_points": [
                    "Dense vein networks",
                    "Crosscutting veins",
                    "Disseminated gold",
                    "Porphyry and epithermal systems"
                ],            }
            ,{
                "id": 50,
                "headline": "LATERITE GOLD",
                "subtitle": "Tropical weathering.",
                "list_header": "LATERITE PROFILE",
                "list_points": [
                    "Deep weathering profile",
                    "Iron-rich surface layer",
                    "Gold enrichment at base",
                    "Tropical climate formation"
                ],            }
        ]
    
    def get_next_topic(self):
        """Get next topic in rotation with dynamic layout assignment"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                current_index = state.get('current_topic_index', 0)
        else:
            current_index = 0
        
        # Get topic
        topic = self.topics[current_index].copy()
        
        # Assign layout based on current index (rotates every 10 topics)
        layout_index = current_index % len(self.layouts)
        layout = self.layouts[layout_index]
        topic['layout'] = layout['name']
        topic['composition'] = layout['composition']
        
        # Update state for next run
        next_index = (current_index + 1) % len(self.topics)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump({'current_topic_index': next_index, 'last_updated': datetime.now().isoformat()}, f)
        
        return topic
    
    def get_topic_with_offset(self, offset=0):
        """Get topic with offset (for multiple fanspages without updating state)"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                base_index = state.get('current_topic_index', 0)
        else:
            base_index = 0
        
        # Calculate index with offset
        current_index = (base_index + offset) % len(self.topics)
        
        # Get topic
        topic = self.topics[current_index].copy()
        
        # Assign layout based on current index
        layout_index = current_index % len(self.layouts)
        layout = self.layouts[layout_index]
        topic['layout'] = layout['name']
        topic['composition'] = layout['composition']
        
        # Don't update state - will be updated by caller
        return topic
    
    def generate_caption(self, topic):
        """Generate educational caption for gold prospecting topic"""
        
        list_text = "\n".join([f"• {point}" for point in topic['list_points']])
        
        prompt = f"""Create a CAPTIVATING EDUCATIONAL CAPTION for a gold prospecting infographic post.

TOPIC: {topic['headline']}
SUBTITLE: {topic['subtitle']}

KEY POINTS:
{list_text}

Requirements:
1. Language: ENGLISH
2. Max Length: 600 characters
3. Structure:
   (a) ATTENTION-GRABBING HEADLINE - Use power words, curiosity, or surprising facts
   (b) Brief explanation with storytelling elements
   (c) Actionable field tip or "pro secret"
   (d) Hashtags (4-6 relevant to gold prospecting)

HEADLINE FORMULAS (choose one that fits):
- "The [Number] Secret(s) [Expert] Don't Tell You About..."
- "Why [Common Belief] Is WRONG About..."
- "This [Simple Thing] Changed Everything..."
- "What [Successful People] Know About..."
- "The Hidden Truth About..."
- "Stop [Common Mistake] - Do This Instead"
- "[Surprising Fact] That Will Change How You..."

Style: Engaging, educational, creates curiosity and urgency.
Tone: Expert sharing insider knowledge, slightly mysterious but trustworthy.
Format: Clean text without markdown symbols (no **, ##, etc)

Example structures:

"THE ONE THING PROS LOOK FOR (That Beginners Miss)

While everyone's chasing shiny quartz, experienced prospectors know the real money is in the ugly, rusty, rotten-looking rock. Iron staining means decomposed sulfides - and that's where gold hides.

Pro Secret: If it looks "too clean" it's probably empty. Seek the stained and fractured.

#GoldProspecting #PlacerGold #ProspectingSecrets #GoldPanning #FindGold"

OR

"WHY MOST PROSPECTORS FAIL (And How to Avoid It)

They dig where it looks good. Smart prospectors dig where physics says gold MUST be. Heavy gold sinks to bedrock, gets trapped in crevices, and stays there for centuries while lighter material washes away.

Field Tip: Find bedrock, find cracks, find gold. It's that simple.

#GoldProspecting #PlacerGold #ProspectingTips #GoldPanning #GoldHunting"

Generate similar caption for the current topic. Make the headline IRRESISTIBLE to click. Use plain text only, no markdown formatting.
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            caption = response.text
            # Add AI disclosure
            caption += "\n\n🤖 Content created with AI assistance"
            return caption
        except Exception as e:
            # Fallback caption
            return f"""🪨 {topic['headline']}

{topic['subtitle']}

{topic['list_header']}:
{list_text}

Learn the signs. Find the gold.

🤖 Content created with AI assistance

#GoldProspecting #PlacerGold #ProspectingTips #GoldPanning"""
    
    def generate_image_prompt(self, topic):
        """Generate image prompt for gold prospecting infographic"""
        
        list_text = "\n".join([f"- {point}" for point in topic['list_points']])
        
        prompt = f"""Create a VERTICAL EDUCATIONAL INFOGRAPHIC POSTER about GOLD PROSPECTING.

TEXT CONTENT TO INCLUDE (Must be legible):
HEADLINE: "{topic['headline']}"
SUBTITLE: "{topic['subtitle']}"
LIST HEADER: "{topic['list_header']}"
LIST POINTS:
{list_text}

VISUAL STYLE & COMPOSITION:
{topic['composition']}

MANDATORY ART DIRECTION:
- STYLE: Realistic Illustration / Field Guide / National Geographic Diagram.
- HEADER BANNER: Add a weathered, off-white/beige ribbon banner at the top with "fishtail" ends containing the headline. Classic field-guide or vintage explorer aesthetic. Add a secondary thinner banner below it in darker tan.
- FRAME/BORDER: Use full-bleed composition with subtle vignetting (darkened edges/corners) to draw focus to center. No hard outer border.
- TEXTURE: Detailed Rock textures, flowing water, dirt, rust, metallic gold.
- ATMOSPHERE: Educational, scientific, rugged, outdoors. Modern high-end educational infographic combining adventurous treasure-hunting feel with technical precision.
- LAYOUT: {topic['layout']} - Use distinct sections, arrows, or split screens to organize information. Left-aligned text boxes with pointer arrows linking to visual elements.
- COLOR SCHEME: 
  * Dominant: Earthy grays, browns, ochres (rock, soil, bedrock)
  * Accent: Vibrant metallic gold yellows/oranges for gold particles
  * Contrast: Deep burnt oranges for rust/iron, cool blues for water/highlights
  * Earth tones, Slate Grey, River Blue, Rusty Orange, Bright Gold
- TYPOGRAPHY: 
  * Main title: Heavy condensed sans-serif all-caps, white with dark-gray drop shadow
  * Body text: Clean modern sans-serif in tan text boxes
  * Bold key terms for quick scanning
- VISUAL ELEMENTS: Digital painting style balancing realistic textures with stylized educational elements. Use minimalist line icons in circles next to text boxes.
- NO ABSTRACT ART. NO CARTOONS. It must look like a professional reference guide with modern high-tech feel.
- Ensure all text is CLEARLY READABLE and properly integrated into the design.
"""
        
        return prompt
