#!/usr/bin/env python3
"""
Validate all Facebook tokens and update config
Run daily at 00:00 via cron
"""

import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "data" / "config.json"

def validate_token(access_token):
    """Validate token with Facebook Graph API"""
    try:
        url = f"https://graph.facebook.com/v18.0/debug_token?input_token={access_token}&access_token={access_token}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        token_data = data.get('data', {})
        
        expires_at = token_data.get('expires_at', 0)
        is_valid = token_data.get('is_valid', False)
        
        if not is_valid:
            return None
        
        if expires_at == 0:
            # Long-lived token, assume 60 days from now
            return datetime.now() + timedelta(days=60)
        
        return datetime.fromtimestamp(expires_at)
    except Exception as e:
        print(f"Error validating token: {e}")
        return None

def main():
    if not CONFIG_PATH.exists():
        print("Config file not found")
        return
    
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    updated = False
    for fp in config.get('fanspages', []):
        page_name = fp.get('name')
        access_token = fp.get('access_token')
        
        if not access_token:
            print(f"[{page_name}] No token")
            continue
        
        print(f"[{page_name}] Validating token...")
        expire_date = validate_token(access_token)
        
        if expire_date:
            # Calculate token created date (60 days before expiration)
            token_created = expire_date - timedelta(days=60)
            fp['token_created_date'] = token_created.isoformat()
            
            days_left = (expire_date - datetime.now()).days
            print(f"[{page_name}] ✓ Valid - {days_left} days left")
            updated = True
        else:
            print(f"[{page_name}] ✗ Invalid or expired")
            # Keep existing token_created_date to show as expired
    
    if updated:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        print("\n✓ Config updated")
    else:
        print("\n✗ No updates")

if __name__ == '__main__':
    main()
