#!/usr/bin/env python3
"""
Get Facebook Page Access Token
"""
import requests

print("=" * 60)
print("FACEBOOK PAGE ACCESS TOKEN GENERATOR")
print("=" * 60)
print()
print("Langkah-langkah:")
print("1. Buka: https://developers.facebook.com/tools/explorer/")
print("2. Pilih aplikasi Anda")
print("3. Klik 'Generate Access Token'")
print("4. Pilih permissions: pages_manage_posts, pages_read_engagement")
print("5. Copy token yang muncul")
print()

user_token = input("Paste User Access Token: ").strip()

if not user_token:
    print("❌ Token kosong!")
    exit(1)

print("\n🔍 Mengambil daftar pages...")

# Get pages
url = f'https://graph.facebook.com/v18.0/me/accounts?access_token={user_token}'
response = requests.get(url)

if response.status_code != 200:
    print(f"❌ Error: {response.json()}")
    exit(1)

data = response.json()
pages = data.get('data', [])

if not pages:
    print("❌ Tidak ada page yang ditemukan!")
    print("   Pastikan token memiliki permission 'pages_manage_posts'")
    exit(1)

print(f"\n✅ Ditemukan {len(pages)} page(s):\n")

for i, page in enumerate(pages, 1):
    print(f"{i}. {page['name']}")
    print(f"   Page ID: {page['id']}")
    print(f"   Page Token: {page['access_token'][:50]}...")
    print()

# Find Putri Kejora
putri = next((p for p in pages if 'Putri' in p['name'] or 'Kejora' in p['name']), None)

if putri:
    print("=" * 60)
    print("🎯 PUTRI KEJORA PAGE TOKEN:")
    print("=" * 60)
    print(f"Page Name: {putri['name']}")
    print(f"Page ID: {putri['id']}")
    print(f"Page Token: {putri['access_token']}")
    print()
    print("✅ Copy token di atas dan update ke config.json")
else:
    print("⚠️  Page 'Putri Kejora' tidak ditemukan dalam daftar")
    print("   Silakan pilih token yang sesuai dari daftar di atas")
