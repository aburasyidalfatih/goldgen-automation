#!/usr/bin/env python3
"""
Dashboard untuk monitoring GoldGen Auto Poster
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "data" / "posts.db"

def show_dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("         GOLDGEN AUTO POSTER - DASHBOARD")
    print("="*60 + "\n")
    
    # Total posts
    cursor.execute("SELECT COUNT(*) FROM posts")
    total = cursor.fetchone()[0]
    print(f"📊 Total Posts: {total}")
    
    # Success rate
    cursor.execute("SELECT COUNT(*) FROM posts WHERE status='success'")
    success = cursor.fetchone()[0]
    success_rate = (success / total * 100) if total > 0 else 0
    print(f"✅ Successful: {success} ({success_rate:.1f}%)")
    
    # Failed posts
    cursor.execute("SELECT COUNT(*) FROM posts WHERE status='failed'")
    failed = cursor.fetchone()[0]
    print(f"❌ Failed: {failed}")
    
    # Last 24 hours
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute("SELECT COUNT(*) FROM posts WHERE timestamp > ?", (yesterday,))
    last_24h = cursor.fetchone()[0]
    print(f"📅 Last 24 hours: {last_24h} posts")
    
    print("\n" + "-"*60)
    print("RECENT POSTS (Last 5)")
    print("-"*60 + "\n")
    
    cursor.execute("""
        SELECT timestamp, status, fb_post_id, error_message 
        FROM posts 
        ORDER BY id DESC 
        LIMIT 5
    """)
    
    for row in cursor.fetchall():
        timestamp, status, fb_post_id, error = row
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        status_icon = "✅" if status == "success" else "❌"
        print(f"{status_icon} {time_str}")
        
        if fb_post_id:
            print(f"   FB Post ID: {fb_post_id}")
        if error:
            print(f"   Error: {error[:80]}...")
        print()
    
    print("-"*60)
    print("\nNext scheduled run:")
    now = datetime.now()
    next_hour = (now.hour // 3 + 1) * 3
    if next_hour >= 24:
        next_run = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
    else:
        next_run = now.replace(hour=next_hour, minute=0, second=0)
    print(f"⏰ {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    conn.close()

if __name__ == "__main__":
    try:
        show_dashboard()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure to run setup.py first!")
