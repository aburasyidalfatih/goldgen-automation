#!/usr/bin/env python3
"""
Test script to show generated prompts
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from goldgen_service import GoldGenService

def main():
    # Mock API key for testing
    os.environ['GEMINI_API_KEY'] = 'test'
    
    service = GoldGenService('test')
    
    print("="*80)
    print("GOLDGEN EDUCATIONAL CONTENT - PROMPT EXAMPLES")
    print("="*80)
    print()
    
    # Show 3 topics as examples
    for i in range(3):
        topic = service.get_next_topic()
        
        print(f"\n{'='*80}")
        print(f"TOPIC {topic['id']}: {topic['headline']}")
        print(f"{'='*80}\n")
        
        print("--- IMAGE PROMPT ---")
        print(service.generate_image_prompt(topic))
        print()
        
        print("\n" + "-"*80)
        print()
    
    print("\n✅ Sistem rotasi topik berjalan dengan baik!")
    print(f"   Total topik: {len(service.topics)}")
    print(f"   Next topic akan dimulai dari: Topic {(i+2) % len(service.topics) + 1}")

if __name__ == "__main__":
    main()
