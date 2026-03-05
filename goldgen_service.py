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
            ,{
                "id": 51,
                "headline": "METAL DETECTORS",
                "subtitle": "Electronic gold hunting.",
                "list_header": "DETECTOR BASICS",
                "list_points": [
                    "VLF vs PI technology",
                    "Ground balance settings",
                    "Discrimination modes",
                    "Coil selection for gold"
                ],            }
            ,{
                "id": 52,
                "headline": "SLUICE BOXES",
                "subtitle": "Gravity does the work.",
                "list_header": "SLUICE SETUP",
                "list_points": [
                    "Proper angle (5-7 degrees)",
                    "Water flow rate",
                    "Riffle types and spacing",
                    "Matting and carpet choice"
                ],            }
            ,{
                "id": 53,
                "headline": "CLAIM STAKING",
                "subtitle": "Securing your ground.",
                "list_header": "STAKING PROCESS",
                "list_points": [
                    "Research available land",
                    "Mark boundaries properly",
                    "File with authorities",
                    "Annual maintenance fees"
                ],            }
            ,{
                "id": 54,
                "headline": "MERCURY SAFETY",
                "subtitle": "The silent killer.",
                "list_header": "MERCURY HAZARDS",
                "list_points": [
                    "Vapor inhalation danger",
                    "Skin absorption risk",
                    "Environmental contamination",
                    "Safe alternatives exist"
                ],            }
            ,{
                "id": 55,
                "headline": "SPRING RUNOFF",
                "subtitle": "High water opportunity.",
                "list_header": "RUNOFF ADVANTAGES",
                "list_points": [
                    "Exposes new bedrock",
                    "Moves heavy material",
                    "Creates new deposits",
                    "Cleans out crevices"
                ],            }
            ,{
                "id": 56,
                "headline": "SAMPLING STRATEGIES",
                "subtitle": "Smart testing saves time.",
                "list_header": "SAMPLING METHODS",
                "list_points": [
                    "Grid pattern sampling",
                    "Systematic spacing",
                    "Consistent sample size",
                    "Record GPS coordinates"
                ],            }
            ,{
                "id": 57,
                "headline": "SELLING YOUR GOLD",
                "subtitle": "Getting fair value.",
                "list_header": "SELLING OPTIONS",
                "list_points": [
                    "Local refineries",
                    "Online buyers",
                    "Pawn shops (lowest price)",
                    "Direct to jewelers"
                ],            }
            ,{
                "id": 58,
                "headline": "GOLD RUSH HISTORY",
                "subtitle": "Learning from the past.",
                "list_header": "HISTORIC LESSONS",
                "list_points": [
                    "Old workings show deposits",
                    "Technology left gold behind",
                    "Maps reveal patterns",
                    "Tailings hold value"
                ],            }
            ,{
                "id": 59,
                "headline": "NO GOLD FOUND",
                "subtitle": "Troubleshooting dry holes.",
                "list_header": "COMMON MISTAKES",
                "list_points": [
                    "Wrong location in stream",
                    "Not reaching bedrock",
                    "Overburden too deep",
                    "Upstream source missing"
                ],            }
            ,{
                "id": 60,
                "headline": "PROSPECTING CLUBS",
                "subtitle": "Strength in numbers.",
                "list_header": "CLUB BENEFITS",
                "list_points": [
                    "Access to claims",
                    "Shared knowledge",
                    "Group outings",
                    "Equipment loans"
                ],            }
            ,{
                "id": 61,
                "headline": "GOLD PANS",
                "subtitle": "The essential tool.",
                "list_header": "PAN SELECTION",
                "list_points": [
                    "Size: 10-14 inches",
                    "Riffles vs smooth",
                    "Green or black color",
                    "Plastic vs metal"
                ],            }
            ,{
                "id": 62,
                "headline": "ACID TESTING",
                "subtitle": "Chemical verification.",
                "list_header": "ACID TEST PROCEDURE",
                "list_points": [
                    "Scratch test surface",
                    "Apply nitric acid",
                    "Gold won't react",
                    "Pyrite dissolves"
                ],            }
            ,{
                "id": 63,
                "headline": "MINING PERMITS",
                "subtitle": "Legal requirements.",
                "list_header": "PERMIT TYPES",
                "list_points": [
                    "Recreational permits",
                    "Commercial licenses",
                    "Environmental clearance",
                    "Water rights"
                ],            }
            ,{
                "id": 64,
                "headline": "AFTER FLOODS",
                "subtitle": "Nature's redistribution.",
                "list_header": "POST-FLOOD SIGNS",
                "list_points": [
                    "New gravel bars",
                    "Exposed bedrock",
                    "Changed stream course",
                    "Fresh concentrations"
                ],            }
            ,{
                "id": 65,
                "headline": "FINE GOLD RECOVERY",
                "subtitle": "Capturing flour gold.",
                "list_header": "FINE GOLD TECHNIQUES",
                "list_points": [
                    "Blue bowl concentrator",
                    "Miller table",
                    "Spiral panning",
                    "Chemical recovery"
                ],            }
            ,{
                "id": 66,
                "headline": "ASSAYING",
                "subtitle": "Professional analysis.",
                "list_header": "ASSAY METHODS",
                "list_points": [
                    "Fire assay (most accurate)",
                    "XRF analysis",
                    "ICP testing",
                    "Sample preparation"
                ],            }
            ,{
                "id": 67,
                "headline": "FAMOUS NUGGETS",
                "subtitle": "Legendary finds.",
                "list_header": "RECORD NUGGETS",
                "list_points": [
                    "Welcome Stranger (72kg)",
                    "Hand of Faith (27kg)",
                    "Pepita Canaã (60kg)",
                    "Great Triangle (36kg)"
                ],            }
            ,{
                "id": 68,
                "headline": "GOLD PRICING",
                "subtitle": "Understanding value.",
                "list_header": "PRICING FACTORS",
                "list_points": [
                    "Spot price per ounce",
                    "Purity percentage",
                    "Buyer's premium",
                    "Specimen vs melt value"
                ],            }
            ,{
                "id": 69,
                "headline": "EQUIPMENT FAILURES",
                "subtitle": "Field repairs.",
                "list_header": "COMMON FAILURES",
                "list_points": [
                    "Detector coil damage",
                    "Sluice riffle loss",
                    "Pan cracks",
                    "Pump failures"
                ],            }
            ,{
                "id": 70,
                "headline": "TAILINGS",
                "subtitle": "Old dumps, new gold.",
                "list_header": "TAILINGS POTENTIAL",
                "list_points": [
                    "Old tech missed fine gold",
                    "Modern recovery better",
                    "Already crushed material",
                    "Known gold presence"
                ],            }
            ,{
                "id": 71,
                "headline": "DREDGES",
                "subtitle": "Underwater mining.",
                "list_header": "DREDGE BASICS",
                "list_points": [
                    "Suction power (HP)",
                    "Nozzle size selection",
                    "Sluice box design",
                    "Legal restrictions"
                ],            }
            ,{
                "id": 72,
                "headline": "ENVIRONMENTAL RULES",
                "subtitle": "Protecting waterways.",
                "list_header": "ENVIRONMENTAL LAWS",
                "list_points": [
                    "No stream pollution",
                    "Restore disturbed areas",
                    "Protect fish habitat",
                    "Proper waste disposal"
                ],            }
            ,{
                "id": 73,
                "headline": "DRONE PROSPECTING",
                "subtitle": "Aerial reconnaissance.",
                "list_header": "DRONE APPLICATIONS",
                "list_points": [
                    "Mapping terrain",
                    "Spotting outcrops",
                    "Access scouting",
                    "Thermal imaging"
                ],            }
            ,{
                "id": 74,
                "headline": "GHOST TOWNS",
                "subtitle": "Mining camp remnants.",
                "list_header": "GHOST TOWN CLUES",
                "list_points": [
                    "Old workings nearby",
                    "Tailings piles",
                    "Equipment remains",
                    "Historical records"
                ],            }
            ,{
                "id": 75,
                "headline": "SPECIMEN GOLD",
                "subtitle": "Collectible pieces.",
                "list_header": "SPECIMEN VALUE",
                "list_points": [
                    "Natural crystal form",
                    "Attached quartz matrix",
                    "Aesthetic appeal",
                    "Worth more than melt"
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
        
        prompt = f"""Create a COMPREHENSIVE EDUCATIONAL CAPTION for a gold prospecting infographic post.

TOPIC: {topic['headline']}
SUBTITLE: {topic['subtitle']}

KEY POINTS TO EXPLAIN:
{list_text}

Requirements:
1. Language: ENGLISH
2. Length: 1000-1500 characters (LONG and DETAILED)
3. Structure:
   (a) ATTENTION-GRABBING HEADLINE - Use power words, curiosity, or surprising facts
   (b) Opening hook - 1-2 sentences that create intrigue
   (c) DETAILED explanation of the topic (3-4 paragraphs)
       - Explain EACH key point from the list
       - Include scientific/geological context
       - Add real-world examples or scenarios
   (d) Practical field tips - Actionable advice prospectors can use
   (e) Closing statement - Motivational or thought-provoking
   (f) CALL-TO-ACTION - Encourage engagement WITHOUT directly asking for comments
       Examples:
       - "What's your experience with [topic]?"
       - "Have you encountered [situation] in the field?"
       - "Share your [discovery/finding/technique]"
       - "Tag a fellow prospector who needs to see this"
       - "What would you add to this list?"
       - "Your [rock/sample/location] might be the next big find"
   (g) Hashtags (6-8 relevant to gold prospecting)

HEADLINE FORMULAS (choose one that fits):
- "The [Number] Secret(s) [Expert] Don't Tell You About..."
- "Why [Common Belief] Is WRONG About..."
- "This [Simple Thing] Changed Everything..."
- "What [Successful People] Know About..."
- "The Hidden Truth About..."
- "Stop [Common Mistake] - Do This Instead"
- "[Surprising Fact] That Will Change How You..."
- "The Ultimate Guide to..."
- "Everything You Need to Know About..."

Style: Engaging, educational, comprehensive, creates curiosity.
Tone: Expert educator sharing deep knowledge, trustworthy and authoritative.
Format: Clean text without markdown symbols (no **, ##, etc)

Example structure:

"THE HIDDEN TRUTH ABOUT IRON STAINING (That Could Make You Rich)

Most beginners walk right past the best gold deposits because they're looking for the wrong thing. They want shiny, clean quartz veins. But experienced prospectors know better.

Iron staining is your treasure map. When sulfide minerals like pyrite decompose, they leave behind rusty red and orange stains on the rock. This oxidation process, called gossan formation, is a direct indicator that you're in a mineralized zone. And where there are sulfides, there's often gold.

Here's what to look for: Red hematite stains indicate iron oxide. Orange limonite crusts show weathered sulfides. Black manganese coatings appear in highly mineralized areas. And those rusty, rotten-looking gossan caps sitting on top of veins? They're literally pointing down to potential gold deposits below.

The science is simple: Gold often occurs with sulfide minerals in hydrothermal veins. When these veins reach the surface and weather, the sulfides oxidize and create that distinctive rusty appearance. The gold, being chemically stable, remains behind while the sulfides decompose around it.

Field Tip: If the rock looks "too clean" and pure white, it's probably barren. Seek the stained, fractured, and oxidized material. Use a magnet to test for magnetite in the black sand. Look for boxwork textures where sulfides have weathered away, leaving honeycomb patterns. These are your indicators.

Remember: Ugly rocks make beautiful gold. Don't judge a vein by its surface appearance.

What's been your experience with iron-stained rocks? That rusty specimen you almost tossed might be worth a second look.

#GoldProspecting #IronStaining #Gossan #PlacerGold #ProspectingTips #GoldPanning #FindGold #MiningLife"

Generate a similar COMPREHENSIVE caption for the current topic. Make it INFORMATIVE and COMPLETE so readers fully understand the infographic. ALWAYS include a natural call-to-action that encourages sharing experiences or tagging others. Use plain text only, no markdown formatting.
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            caption = response.text
            return caption
        except Exception as e:
            # Fallback caption
            return f"""🪨 {topic['headline']}

{topic['subtitle']}

{topic['list_header']}:
{list_text}

Learn the signs. Find the gold.

What's your experience with this? Share your findings.

#GoldProspecting #PlacerGold #ProspectingTips #GoldPanning"""
    
    def generate_image_prompt(self, topic):
        """Generate image prompt for gold prospecting infographic"""
        
        list_text = "\n".join([f"- {point}" for point in topic['list_points']])
        
        # Get layout-specific visual instructions
        layout_name = topic.get('layout', 'CROSS-SECTION CUTAWAY')
        
        # Base prompt with topic content
        base_prompt = f"""Create a VERTICAL EDUCATIONAL INFOGRAPHIC about GOLD PROSPECTING.

TOPIC: {topic['headline']}
SUBTITLE: {topic['subtitle']}

KEY INFORMATION TO VISUALIZE:
{list_text}

LAYOUT STYLE: {layout_name}
COMPOSITION GUIDE: {topic['composition']}

"""
        
        # Add specific visual instructions based on layout
        if "CROSS-SECTION" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a realistic cross-section illustration showing underground layers. Display the surface at top, then soil/gravel layers, and bedrock at bottom. Show gold deposits trapped in crevices or layers. Use natural earth tones with clear labeling lines pointing to key features. Style: Educational textbook diagram with scientific accuracy."""

        elif "CHECKLIST" in layout_name or "SPLIT" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a split-screen comparison image with a clear vertical divider. Left side shows one condition/type, right side shows the contrasting condition/type. Each side should be clearly labeled. Use realistic, detailed photography style suitable for a field guide. Make the differences obvious and educational."""

        elif "STEP-BY-STEP" in layout_name or "PROCESS" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a vertical flow diagram showing sequential steps from top to bottom. Use numbered steps (1, 2, 3, 4) with arrows indicating progression and movement. Each step should show a clear stage of the process. Style: Illustrative and easy to follow with a rugged outdoor aesthetic. Use directional arrows to show flow."""

        elif "GRID" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 2x2 or 3x2 grid layout showing distinct close-up images of different indicators or examples. Each grid cell should be clearly separated with borders. Images should be macro-style, highly detailed, and realistic. Each section can have a small label. Focus on texture and detail."""

        elif "GOLDEN PATH" in layout_name or "PATH" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a top-down aerial view or map-style illustration. Use arrows to mark flow direction or movement patterns. Highlight specific zones or areas with golden glow, markers, or circles to indicate important locations. Style: Strategic diagram or treasure map with realistic terrain features."""

        elif "MAGNIFYING GLASS" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create an image showing a surface with a magnifying glass overlay. Inside the lens, show a highly magnified, detailed view revealing features invisible to the naked eye. The focus should be sharp inside the lens and slightly blurred outside. Style: Scientific discovery with emphasis on detail revelation."""

        elif "BEFORE" in layout_name and "AFTER" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a split landscape view showing the same location in two different states. Top half labeled 'BEFORE', bottom half labeled 'AFTER'. Show clear changes between the two states. Highlight new features or changes that are significant. Style: Realistic comparative photography."""

        elif "NOTEBOOK" in layout_name or "GEOLOGIST" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create an image that looks like a page from a field notebook. Feature hand-sketched but detailed drawings with handwritten-style annotations, arrows pointing to key features, and labels. Add authentic touches like coffee stains, dirt smudges, or pencil marks. Background: Aged paper texture."""

        elif "3D" in layout_name or "BLOCK" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 3D isometric block diagram showing a cutaway section of earth. Display surface features on top and underground layers in cross-section. Show how geological features connect from deep underground to the surface. Style: Clean, educational, three-dimensional technical illustration."""

        elif "MAP" in layout_name or "PROSPECTOR" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a vintage-style topographic map with contour lines showing elevation. Mark key features like rivers in blue, and add hand-drawn markers (X marks, circles) in red ink at important locations. Style: Aged paper, rugged, adventurous with a treasure map aesthetic."""

        else:
            # Default fallback
            visual_instruction = """VISUAL EXECUTION:
Create a realistic educational illustration combining the topic's key visual elements. Use clear composition with labeled features. Style: National Geographic field guide with scientific accuracy and visual appeal."""

        # Combine all parts
        full_prompt = base_prompt + visual_instruction + f"""

MANDATORY REQUIREMENTS:
- Format: Vertical 9:16 aspect ratio (story/poster format)
- Color Scheme: Earth tones (browns, grays, ochres) with metallic gold accents and rust oranges
- Texture: Realistic rock, soil, water, and mineral textures
- Atmosphere: Educational, scientific, professional
- Quality: High detail, sharp focus on key elements
- NO ABSTRACT ART. NO CARTOONS. Must look like a professional reference guide.
- Text elements should be minimal and integrated naturally into the design (if any)
"""
        
        return full_prompt
