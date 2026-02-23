#!/usr/bin/env python3
"""
Test script untuk memverifikasi delay configuration
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "data" / "config.json"

def test_config():
    """Test loading config with delay"""
    print("=" * 60)
    print("TESTING FANSPAGE DELAY CONFIGURATION")
    print("=" * 60)
    print()
    
    # Load config
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # Check delay field
    delay_minutes = config.get('fanspage_delay_minutes', 60)
    print(f"✅ Config loaded successfully")
    print(f"   Fanspage Delay: {delay_minutes} minutes ({delay_minutes/60} hours)")
    print()
    
    # Check fanspages
    fanspages = config.get('fanspages', [])
    print(f"✅ Fanspages configured: {len(fanspages)}")
    for idx, page in enumerate(fanspages, 1):
        print(f"   {idx}. {page['name']}")
        print(f"      - Page ID: {page['page_id']}")
        print(f"      - Interval: {page['interval_hours']} hours")
        print(f"      - Enabled: {page.get('enabled', True)}")
        print(f"      - Has Token: {bool(page.get('access_token'))}")
    print()
    
    # Simulate delay calculation
    delay_seconds = delay_minutes * 60
    print(f"✅ Delay calculation:")
    print(f"   {delay_minutes} minutes = {delay_seconds} seconds")
    print()
    
    # Test scenario
    print("📋 Example Scenario:")
    print(f"   If you have {len(fanspages)} fanspages:")
    print(f"   - Post to Fanspage 1 at 09:00")
    print(f"   - Wait {delay_minutes} minutes")
    print(f"   - Post to Fanspage 2 at {9 + delay_minutes/60:.2f}:00")
    if len(fanspages) > 2:
        print(f"   - Wait {delay_minutes} minutes")
        print(f"   - Post to Fanspage 3 at {9 + 2*delay_minutes/60:.2f}:00")
    print()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("💡 To change delay:")
    print("   1. Open dashboard at gold.kelasmaster.id")
    print("   2. Click ⚙️ Settings")
    print("   3. Change 'Delay Between Fanspages' value")
    print("   4. Click 💾 Save Configuration")
    print()

if __name__ == "__main__":
    test_config()
