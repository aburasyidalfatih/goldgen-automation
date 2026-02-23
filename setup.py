#!/usr/bin/env python3
"""
Setup script for GoldGen Auto Poster
Run this once to configure the automation
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"

def setup():
    print("=== GoldGen Auto Poster Setup ===\n")
    
    # Get Gemini API Key
    gemini_key = input("Enter your Gemini API Key [AIzaSyD881rafoJDc6IUXbSmz4iYAjVASdjfMDA]: ").strip()
    if not gemini_key:
        gemini_key = "AIzaSyD881rafoJDc6IUXbSmz4iYAjVASdjfMDA"
    
    # Get Facebook credentials
    print("\n📘 Facebook Setup:")
    print("You need:")
    print("1. Facebook Page ID")
    print("2. Page Access Token (with pages_manage_posts permission)")
    print("\nTo get these:")
    print("- Go to https://developers.facebook.com/tools/explorer/")
    print("- Select your Page")
    print("- Generate token with 'pages_manage_posts' permission\n")
    
    fb_page_id = input("Enter Facebook Page ID: ").strip()
    fb_access_token = input("Enter Facebook Page Access Token: ").strip()
    
    # Save configuration
    config = {
        'gemini_api_key': gemini_key,
        'fb_page_id': fb_page_id,
        'fb_access_token': fb_access_token
    }
    
    DATA_DIR.mkdir(exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Configuration saved to {CONFIG_PATH}")
    print("\nNext steps:")
    print("1. Test the script: python3 auto_poster.py")
    print("2. If successful, the cron job will run automatically every 3 hours")

if __name__ == "__main__":
    setup()
