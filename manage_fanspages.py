#!/usr/bin/env python3
"""
Manage Fanspages - Add, edit, remove fanspages
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "data" / "config.json"

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def list_fanspages():
    config = load_config()
    print("\n📋 Configured Fanspages:\n")
    for i, page in enumerate(config['fanspages'], 1):
        status = "✅ Enabled" if page.get('enabled', True) else "❌ Disabled"
        print(f"{i}. {page['name']}")
        print(f"   Page ID: {page['page_id']}")
        print(f"   Interval: {page['interval_hours']} hours")
        print(f"   Status: {status}\n")

def add_fanspage():
    config = load_config()
    print("\n➕ Add New Fanspage\n")
    
    name = input("Page Name: ")
    page_id = input("Page ID: ")
    access_token = input("Access Token: ")
    interval = int(input("Interval (hours): "))
    
    config['fanspages'].append({
        'name': name,
        'page_id': page_id,
        'access_token': access_token,
        'interval_hours': interval,
        'enabled': True
    })
    
    save_config(config)
    print(f"\n✅ {name} added successfully!")

def toggle_fanspage():
    config = load_config()
    list_fanspages()
    
    idx = int(input("Select fanspage number to toggle: ")) - 1
    if 0 <= idx < len(config['fanspages']):
        config['fanspages'][idx]['enabled'] = not config['fanspages'][idx].get('enabled', True)
        save_config(config)
        status = "enabled" if config['fanspages'][idx]['enabled'] else "disabled"
        print(f"\n✅ {config['fanspages'][idx]['name']} {status}!")
    else:
        print("❌ Invalid selection")

def edit_interval():
    config = load_config()
    list_fanspages()
    
    idx = int(input("Select fanspage number to edit interval: ")) - 1
    if 0 <= idx < len(config['fanspages']):
        new_interval = int(input(f"New interval (hours) [current: {config['fanspages'][idx]['interval_hours']}]: "))
        config['fanspages'][idx]['interval_hours'] = new_interval
        save_config(config)
        print(f"\n✅ Interval updated to {new_interval} hours!")
    else:
        print("❌ Invalid selection")

def main():
    while True:
        print("\n" + "="*50)
        print("🔧 Fanspage Manager")
        print("="*50)
        print("1. List fanspages")
        print("2. Add fanspage")
        print("3. Toggle enable/disable")
        print("4. Edit interval")
        print("5. Exit")
        
        choice = input("\nSelect option: ")
        
        if choice == '1':
            list_fanspages()
        elif choice == '2':
            add_fanspage()
        elif choice == '3':
            toggle_fanspage()
        elif choice == '4':
            edit_interval()
        elif choice == '5':
            break
        else:
            print("❌ Invalid option")

if __name__ == "__main__":
    main()
