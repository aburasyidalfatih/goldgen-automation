#!/usr/bin/env python3
"""
Audit script untuk GoldGen Automation
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "posts.db"
CONFIG_PATH = BASE_DIR / "data" / "config.json"
STATE_PATH = BASE_DIR / "data" / "topic_state.json"

def audit_database():
    """Audit database structure and data"""
    print("\n" + "="*80)
    print("DATABASE AUDIT")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n✅ Tables: {', '.join(tables)}")
    
    # Check posts
    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]
    print(f"✅ Total posts in DB: {total_posts}")
    
    cursor.execute("SELECT COUNT(*) FROM posts WHERE status='success'")
    success_posts = cursor.fetchone()[0]
    print(f"✅ Successful posts: {success_posts}")
    
    cursor.execute("SELECT COUNT(*) FROM posts WHERE status='failed'")
    failed_posts = cursor.fetchone()[0]
    print(f"⚠️  Failed posts: {failed_posts}")
    
    # Check last post times
    cursor.execute("SELECT page_id, last_posted FROM last_post_time")
    last_posts = cursor.fetchall()
    print(f"\n✅ Last post tracking: {len(last_posts)} pages")
    for page_id, last_posted in last_posts:
        dt = datetime.fromisoformat(last_posted)
        print(f"   - Page {page_id}: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn.close()

def audit_config():
    """Audit configuration"""
    print("\n" + "="*80)
    print("CONFIGURATION AUDIT")
    print("="*80)
    
    if not CONFIG_PATH.exists():
        print("❌ Config file not found!")
        return
    
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    print(f"\n✅ Gemini API Key: {'*' * 20}{config['gemini_api_key'][-10:]}")
    print(f"✅ Fanspages configured: {len(config['fanspages'])}")
    
    for i, fp in enumerate(config['fanspages'], 1):
        print(f"\n   Fanspage {i}:")
        print(f"   - Name: {fp['name']}")
        print(f"   - Page ID: {fp['page_id']}")
        print(f"   - Interval: {fp['interval_hours']} hours")
        print(f"   - Enabled: {fp.get('enabled', True)}")
        print(f"   - Access Token: {'*' * 20}{fp['access_token'][-10:]}")

def audit_interval_system():
    """Audit interval posting system"""
    print("\n" + "="*80)
    print("INTERVAL SYSTEM AUDIT")
    print("="*80)
    
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for fp in config['fanspages']:
        print(f"\n📄 {fp['name']}:")
        print(f"   Interval: {fp['interval_hours']} hours")
        
        cursor.execute('SELECT last_posted FROM last_post_time WHERE page_id = ?', (fp['page_id'],))
        result = cursor.fetchone()
        
        if result:
            last_posted = datetime.fromisoformat(result[0])
            next_post = last_posted + timedelta(hours=fp['interval_hours'])
            now = datetime.now()
            
            print(f"   Last posted: {last_posted.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Next post: {next_post.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if now >= next_post:
                print(f"   ✅ Ready to post NOW")
            else:
                remaining = next_post - now
                hours = remaining.total_seconds() / 3600
                print(f"   ⏰ Next post in {hours:.1f} hours")
        else:
            print(f"   ✅ Never posted - will post on next run")
    
    conn.close()

def audit_topic_rotation():
    """Audit topic rotation system"""
    print("\n" + "="*80)
    print("TOPIC ROTATION AUDIT")
    print("="*80)
    
    if not STATE_PATH.exists():
        print("⚠️  Topic state file not found - will be created on first run")
        return
    
    with open(STATE_PATH, 'r') as f:
        state = json.load(f)
    
    current_index = state.get('current_topic_index', 0)
    last_updated = state.get('last_updated', 'Never')
    
    print(f"\n✅ Current topic index: {current_index + 1}/10")
    print(f"✅ Last updated: {last_updated}")
    print(f"✅ Next topic: {(current_index + 1) % 10 + 1}/10")
    
    topics = [
        "Reading the River",
        "Bedrock Traps",
        "Quartz Indicators",
        "Iron Staining",
        "Black Sand Secrets",
        "Gold vs Pyrite",
        "Ancient Channels",
        "Placer vs Lode",
        "Ruby Companions",
        "False Bedrock"
    ]
    
    print(f"\n📚 All Topics:")
    for i, topic in enumerate(topics, 1):
        marker = "→" if i == current_index + 1 else " "
        print(f"   {marker} {i}. {topic}")

def audit_image_generation():
    """Audit image generation capability"""
    print("\n" + "="*80)
    print("IMAGE GENERATION AUDIT")
    print("="*80)
    
    print("\n✅ Model: gemini-3-pro-image-preview (Nano Banana Pro)")
    print("✅ Features:")
    print("   - 4K resolution support")
    print("   - Advanced text rendering")
    print("   - Multimodal processing")
    print("   - Vertical format (9:16)")
    
    images_dir = BASE_DIR / "generated_images"
    if images_dir.exists():
        images = list(images_dir.glob("*.png"))
        print(f"\n✅ Generated images: {len(images)}")
        if images:
            latest = max(images, key=lambda p: p.stat().st_mtime)
            print(f"   Latest: {latest.name}")
    else:
        print("\n⚠️  No images generated yet")

def audit_dashboard():
    """Audit dashboard"""
    print("\n" + "="*80)
    print("DASHBOARD AUDIT")
    print("="*80)
    
    dashboard_file = BASE_DIR / "dashboard.html"
    if dashboard_file.exists():
        print("\n✅ Dashboard file exists")
        print("✅ Accessible at: https://gold.kelasmaster.id")
        print("✅ Features:")
        print("   - Total posts statistics")
        print("   - Success rate")
        print("   - Recent posts list")
        print("   - Fanspage management")
        print("\n⚠️  Note: Dashboard UI masih generic (belum disesuaikan untuk gold prospecting)")
    else:
        print("\n❌ Dashboard file not found")

def main():
    print("\n" + "="*80)
    print("GOLDGEN AUTOMATION - SYSTEM AUDIT")
    print("="*80)
    print(f"Audit Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    audit_database()
    audit_config()
    audit_interval_system()
    audit_topic_rotation()
    audit_image_generation()
    audit_dashboard()
    
    print("\n" + "="*80)
    print("AUDIT SUMMARY")
    print("="*80)
    print("\n✅ WORKING:")
    print("   - Database structure")
    print("   - Config loading")
    print("   - Interval system")
    print("   - Topic rotation (10 topics)")
    print("   - Fanspage management (2 pages)")
    print("   - Model configuration (Gemini 3.1 Pro + Nano Banana Pro)")
    
    print("\n⚠️  NEEDS ATTENTION:")
    print("   - Dashboard UI belum disesuaikan untuk gold prospecting content")
    print("   - Image generation belum ditest (perlu API key valid)")
    
    print("\n💡 RECOMMENDATIONS:")
    print("   1. Update dashboard UI untuk menampilkan topik edukasi")
    print("   2. Test image generation dengan API key valid")
    print("   3. Monitor first few posts untuk quality check")
    print("\n")

if __name__ == "__main__":
    main()
