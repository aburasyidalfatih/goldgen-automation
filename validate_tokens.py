#!/usr/bin/env python3
"""
Validate all Facebook tokens
"""
import json
import requests
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "data" / "config.json"

def validate_token(page_name, page_id, access_token):
    """Validate Facebook token"""
    try:
        url = f"https://graph.facebook.com/v18.0/{page_id}"
        params = {'access_token': access_token, 'fields': 'name,id'}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return True, data.get('name'), None
        else:
            error = response.json().get('error', {})
            return False, None, error.get('message', 'Unknown error')
    except Exception as e:
        return False, None, str(e)

def main():
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    fanspages = config.get('fanspages', [])
    
    print("=" * 70)
    print("VALIDATING FACEBOOK TOKENS")
    print("=" * 70)
    print()
    
    valid_count = 0
    invalid_count = 0
    
    for idx, page in enumerate(fanspages, 1):
        print(f"{idx}. {page['name']}")
        print(f"   Page ID: {page['page_id']}")
        
        valid, fb_name, error = validate_token(
            page['name'], 
            page['page_id'], 
            page.get('access_token', '')
        )
        
        if valid:
            print(f"   Status: ✅ VALID")
            print(f"   FB Name: {fb_name}")
            valid_count += 1
        else:
            print(f"   Status: ❌ INVALID")
            print(f"   Error: {error}")
            invalid_count += 1
        
        print()
    
    print("=" * 70)
    print(f"SUMMARY: {valid_count} Valid | {invalid_count} Invalid")
    print("=" * 70)

if __name__ == "__main__":
    main()
