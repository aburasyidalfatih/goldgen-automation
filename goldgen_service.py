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
    def __init__(self, api_key, model='gemini-3.5-flash'):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
        # Topic rotation state
        self.state_file = Path(__file__).parent / "data" / "topic_state.json"
        
        # Load layouts and topics from external JSON
        try:
            with open(Path(__file__).parent / 'data' / 'layouts.json', 'r', encoding='utf-8') as f:
                self.layouts = json.load(f)
            with open(Path(__file__).parent / 'data' / 'topics.json', 'r', encoding='utf-8') as f:
                self.topics = json.load(f)
        except Exception as e:
            print(f'Warning: Could not load layouts or topics. Fallback to empty lists. Error: {e}')
            self.layouts = []
            self.topics = []

    def _get_audience_preferences(self):
        """Ambil top topic preferences dari analisis komentar"""
        try:
            from core.database import get_db_connection
            conn = get_db_connection()
            rows = conn.execute(
                'SELECT topic_keyword, boost_score FROM topic_preferences ORDER BY boost_score DESC LIMIT 10'
            ).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return []

    def get_next_topic(self):
        """Get next topic in rotation, prioritize topics matching audience preferences"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                current_index = state.get('current_topic_index', 0)
        else:
            current_index = 0

        # Cek audience preferences dari analisis komentar
        preferences = self._get_audience_preferences()

        selected_index = current_index
        if preferences:
            # Cari topic yang paling match dengan preferences audience
            best_match_index = None
            best_score = 0
            for i, topic in enumerate(self.topics):
                topic_text = f"{topic['headline']} {topic['subtitle']} {' '.join(topic.get('list_points', []))}".lower()
                score = sum(1 for pref in preferences if pref.lower() in topic_text)
                if score > best_score:
                    best_score = score
                    best_match_index = i

            # Pakai topic yang match jika score > 0 dan belum dipakai baru-baru ini
            recently_used = state.get('recently_used', []) if self.state_file.exists() else []
            if best_match_index is not None and best_score > 0 and best_match_index not in recently_used[-5:]:
                selected_index = best_match_index

        # Get topic
        topic = self.topics[selected_index].copy()

        # Assign layout
        layout_index = selected_index % len(self.layouts)
        layout = self.layouts[layout_index]
        topic['layout'] = layout['name']
        topic['composition'] = layout['composition']

        # Update state
        next_index = (current_index + 1) % len(self.topics)
        recently_used = state.get('recently_used', []) if self.state_file.exists() else []
        recently_used.append(selected_index)
        if len(recently_used) > 20:
            recently_used = recently_used[-20:]

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump({
                'current_topic_index': next_index,
                'last_updated': datetime.now().isoformat(),
                'recently_used': recently_used
            }, f)

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
        
        prompt = f"""Create a VIRAL EDUCATIONAL CAPTION for a gold prospecting Facebook post.

TOPIC: {topic['headline']}
SUBTITLE: {topic['subtitle']}

KEY POINTS TO EXPLAIN:
{list_text}

=== PROVEN VIRAL FORMULA (based on top-performing posts analysis) ===

HOOK STYLE (MUST USE ONE):
- "While beginners [do X], real veterans know [secret Y]"
- "Most people walk right past [thing] because they don't know [secret]"
- "The [number] secret(s) that separate amateur prospectors from legends"
- "Stop [common mistake]. Here's what actually works..."
- "What successful prospectors know about [topic] that nobody talks about"

CONTENT STRUCTURE:
1. HEADLINE — Bombastic, provocative, promises exclusive insider knowledge
2. Opening hook (2 sentences) — Create urgency, highlight beginner mistake vs pro knowledge
3. Core explanation (3-4 paragraphs) — Each paragraph explains ONE visual/physical indicator they can use IN THE FIELD TODAY. Connect mineral indicators to gold presence with clear cause-effect logic.
4. FIELD TIP — Start with "Field Tip:" — Give ONE specific, actionable technique they can use immediately
5. Closing — Short motivational line about ugly/broken rocks hiding the best gold
6. CTA — Ask about their personal field experience with this specific indicator. Examples:
   - "What's your experience with [specific indicator] in your local area?"
   - "Have you encountered [specific sign] in the field? Tag a fellow prospector who needs to see this."
   - "That [specific rock/mineral] you almost tossed might be worth a second look."
7. Hashtags (6-8, mix of: #GoldProspecting #[TopicSpecific] #ProspectingTips #GoldMining #Geology #FindGold)

=== WHAT MAKES POSTS GO VIRAL (apply these) ===
✅ Focus on VISUAL indicators they can see with their eyes (color, texture, smell, weight)
✅ Use "Pro vs Beginner" framing — makes reader feel like they're getting insider secrets
✅ Mention specific minerals by name (Magnetite, Garnet, Arsenopyrite, Pyrite) — builds authority
✅ Include the PHYSICS/SCIENCE behind why it works — not just "look for X" but "X happens because Y"
✅ Field tips must be IMMEDIATELY actionable — something they can do on their next trip
✅ Length: 1000-1500 characters — detailed enough to feel valuable

❌ AVOID: Pure academic/historical theory with no field application
❌ AVOID: Administrative topics (permits, regulations, selling)
❌ AVOID: Equipment selection guides without connecting to gold discovery
❌ AVOID: Markdown symbols (**, ##, etc) — plain text only

Requirements:
- Language: ENGLISH
- Format: Clean plain text, no markdown
- Tone: Expert educator sharing "expensive knowledge for free" — authoritative but accessible
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
Create an image that looks like a page from a field notebook. Feature highly detailed, high-contrast ink and watercolor illustrations. Use strong, bold lines and rich colors. The diagram must be extremely sharp and readable. Add authentic touches like compass, rock samples, or a pencil resting on the side. Background: Aged but clean paper. DO NOT generate blurry or faded pencil sketches. DO NOT generate walls of illegible text."""

        elif "3D" in layout_name or "BLOCK" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a 3D isometric block diagram showing a cutaway section of earth. Display surface features on top and underground layers in cross-section. Show how geological features connect from deep underground to the surface. Style: Clean, educational, three-dimensional technical illustration."""

        elif "MAP" in layout_name or "PROSPECTOR" in layout_name:
            visual_instruction = """VISUAL EXECUTION:
Create a highly detailed, colorful topographic map illustration with strong contrast. Mark key features like rivers in vivid blue, and add bold red markers (X marks, circles) at important locations. Use clear, sharp, dark ink for contour lines. Style: Adventurous but professional treasure map with rich colors and sharp details. Avoid faint or blurry lines."""

        else:
            # Default fallback
            visual_instruction = """VISUAL EXECUTION:
Create a realistic educational illustration combining the topic's key visual elements. Use clear composition with labeled features. Style: National Geographic field guide with scientific accuracy and visual appeal."""

        # Combine all parts
        full_prompt = base_prompt + visual_instruction + f"""

MANDATORY REQUIREMENTS:
- Format: Vertical 9:16 aspect ratio (story/poster format)
- Background: MUST be textured like slightly weathered vintage parchment, an old geologist's map, or aged craft paper. DO NOT use plain white or solid color backgrounds.
- Color Scheme: Earth tones (browns, grays, ochres) with metallic gold accents and rust oranges
- Contrast: HIGH CONTRAST. Ensure all lines, diagrams, and features are sharp, bold, and clearly visible. NO FADED OR BLURRY ELEMENTS.
- Texture: Realistic rock, soil, water, and mineral textures
- Atmosphere: Educational, scientific, professional
- Quality: High detail, sharp focus on key elements, photorealistic rendering where applicable.
- NO ABSTRACT ART. NO CARTOONS. Must look like a professional reference guide.
- TEXT WARNING: DO NOT generate paragraphs of illegible text or scribbles. If text is included, it must be minimal, bold, and highly legible.
"""
        
        return full_prompt
