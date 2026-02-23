#!/usr/bin/env python3
"""
Test script untuk memverifikasi logika delay antar fanspage
"""

from datetime import datetime, timedelta
import time

# Simulasi fanspages
fanspages = [
    {'name': 'Fanspage A', 'page_id': '123', 'enabled': True},
    {'name': 'Fanspage B', 'page_id': '456', 'enabled': True},
    {'name': 'Fanspage C', 'page_id': '789', 'enabled': True},
]

def simulate_posting():
    """Simulasi proses posting dengan delay"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting simulation...\n")
    
    posted_count = 0
    
    for idx, fanspage in enumerate(fanspages):
        if not fanspage.get('enabled', True):
            print(f"⏭️  Skipping {fanspage['name']} (disabled)")
            continue
        
        # Simulasi posting
        print(f"📄 Processing: {fanspage['name']}")
        print(f"   Simulating post...")
        time.sleep(1)  # Simulasi waktu posting
        print(f"   ✅ Success!")
        posted_count += 1
        print()
        
        # Delay logic
        if posted_count > 0 and idx < len(fanspages) - 1:
            # Check if there are more enabled pages
            has_more = any(
                p.get('enabled', True) 
                for p in fanspages[idx+1:]
            )
            if has_more:
                # Untuk testing, gunakan delay 5 detik (bukan 3600)
                delay_seconds = 5  # 5 detik untuk testing (production: 3600)
                next_time = datetime.now() + timedelta(seconds=delay_seconds)
                print(f"⏳ Waiting {delay_seconds} seconds before next fanspage...")
                print(f"   Next post at: {next_time.strftime('%H:%M:%S')}\n")
                time.sleep(delay_seconds)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Simulation completed!")
    print(f"Total posts: {posted_count}")

if __name__ == "__main__":
    print("=" * 60)
    print("FANSPAGE DELAY SIMULATION")
    print("=" * 60)
    print()
    print("Testing delay logic with 3 fanspages")
    print("Delay: 5 seconds (production will use 3600 = 1 hour)")
    print()
    
    simulate_posting()
    
    print("\n" + "=" * 60)
    print("Test completed! Check the timing between posts.")
    print("=" * 60)
