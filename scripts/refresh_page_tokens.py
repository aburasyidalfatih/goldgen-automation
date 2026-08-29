#!/usr/bin/env python3
"""
Perbarui page access token di data/config.json menjadi long-lived.

Alur resmi Facebook yang dijalankan script ini:
  1. Tukar short-lived USER token  ->  long-lived USER token (butuh app secret)
  2. Ambil PAGE token dari long-lived user token lewat /me/accounts
     (page token turunan long-lived user token TIDAK pernah kedaluwarsa)
  3. Verifikasi tiap token: masa berlaku + scope
  4. Tulis ke config.json, hanya untuk page yang memang ada di konfigurasi

Kredensial diminta lewat prompt tersembunyi — tidak lewat argumen, supaya
tidak tercatat di riwayat shell. Token tidak pernah dicetak ke layar.

Pakai:
    python scripts/refresh_page_tokens.py            # tampilkan rencana saja
    python scripts/refresh_page_tokens.py --apply    # tulis ke config.json
"""

import getpass
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CONFIG_PATH  # noqa: E402

GRAPH = "https://graph.facebook.com/v18.0"


def minta(nama, env):
    """Ambil dari environment kalau ada, kalau tidak minta lewat prompt tersembunyi"""
    nilai = os.getenv(env)
    if nilai:
        return nilai.strip()
    return getpass.getpass(f"{nama}: ").strip()


def periksa_token(token):
    """Return (valid, tidak_pernah_kedaluwarsa, punya_read_insights, pesan)"""
    try:
        d = requests.get(f"{GRAPH}/debug_token",
                         params={'input_token': token, 'access_token': token},
                         timeout=30).json().get('data', {})
    except Exception as e:
        return False, False, False, f"gagal memeriksa: {type(e).__name__}"

    if not d.get('is_valid', True) and 'expires_at' not in d:
        return False, False, False, 'token tidak valid'

    expires = d.get('expires_at')
    scopes = d.get('scopes') or []
    return True, (not expires), ('read_insights' in scopes), ''


def main():
    apply_changes = '--apply' in sys.argv

    print("Masukkan kredensial aplikasi Meta (tidak akan ditampilkan/disimpan).")
    print("App ID & Secret ada di: developers.facebook.com > Aplikasi > Pengaturan > Dasar\n")
    app_id = minta("App ID", "FB_APP_ID")
    app_secret = minta("App Secret", "FB_APP_SECRET")
    user_token = minta("User token dari Graph API Explorer", "FB_USER_TOKEN")

    # 1. Tukar jadi long-lived user token
    print("\n▶ Menukar user token menjadi long-lived...")
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': user_token,
    }, timeout=30).json()

    if 'access_token' not in r:
        print(f"   ❌ Gagal: {str(r.get('error', {}).get('message'))[:160]}")
        return
    long_user_token = r['access_token']
    print("   ✅ Long-lived user token diperoleh")

    # 2. Ambil page token
    print("\n▶ Mengambil page token...")
    r = requests.get(f"{GRAPH}/me/accounts",
                     params={'access_token': long_user_token, 'limit': 100},
                     timeout=30).json()
    if 'data' not in r:
        print(f"   ❌ Gagal: {str(r.get('error', {}).get('message'))[:160]}")
        return

    token_per_page = {p['id']: (p.get('name'), p['access_token']) for p in r['data']}
    print(f"   ✅ {len(token_per_page)} page ditemukan di akun ini")

    # 3. Cocokkan dengan config & verifikasi
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    print(f"\n{'PAGE':<18}{'SELAMANYA':<12}{'read_insights':<16}KETERANGAN")
    print("-" * 74)

    siap = []
    for page in config.get('fanspages', []):
        nama = (page.get('name') or '?')[:17]
        pid = page.get('page_id')
        if pid not in token_per_page:
            print(f"{nama:<18}{'-':<12}{'-':<16}tidak ada di akun ini, dilewati")
            continue

        _, token_baru = token_per_page[pid]
        valid, selamanya, insights, pesan = periksa_token(token_baru)
        print(f"{nama:<18}{('YA' if selamanya else 'TIDAK'):<12}"
              f"{('ADA' if insights else 'BELUM'):<16}{pesan or 'siap dipakai'}")

        if valid and selamanya and insights:
            siap.append((page, token_baru))
        elif valid and selamanya:
            # Tetap layak dipakai, hanya reach yang belum bisa diambil
            siap.append((page, token_baru))

    print("-" * 74)
    print(f"Siap diperbarui: {len(siap)} page")

    if not apply_changes:
        print("\n(rencana saja — tambahkan --apply untuk menulis ke config.json)")
        return

    if not siap:
        print("Tidak ada yang diperbarui.")
        return

    cadangan = Path(str(CONFIG_PATH) + f".backup_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy(CONFIG_PATH, cadangan)

    for page, token_baru in siap:
        page['access_token'] = token_baru
        page['token_created_date'] = datetime.now().isoformat()

    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ config.json diperbarui untuk {len(siap)} page (cadangan: {cadangan.name})")
    print("   Bot memakai token baru pada siklus berikutnya — tidak perlu restart.")


if __name__ == '__main__':
    main()
