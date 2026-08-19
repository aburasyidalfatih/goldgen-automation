#!/usr/bin/env python3
"""
Cek status token Facebook semua fanspage.

Dijalankan LANGSUNG DI SERVER — token tidak pernah dicetak atau dikirim keluar,
hanya nama page dan hasil pengecekannya.

Pakai:  python check_tokens.py
"""

import datetime
import json

import requests

try:
    from core.config import CONFIG_PATH
except Exception:
    CONFIG_PATH = 'data/config.json'


def main():
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)

    pages = cfg.get('fanspages', [])
    print(f"Total fanspage: {len(pages)}\n")
    header = f"{'PAGE':<18}{'AKTIF':<8}{'KEDALUWARSA':<16}{'DIBUAT':<12} KETERANGAN"
    print(header)
    print("-" * 100)

    aktif = mati = 0

    for p in pages:
        name = (p.get('name') or '?')[:17]
        token = p.get('access_token') or ''
        page_id = p.get('page_id') or ''
        created = (p.get('token_created_date') or '')[:10] or '-'

        if not token:
            print(f"{name:<18}{'TIDAK':<8}{'-':<16}{created:<12} tidak ada token di config")
            mati += 1
            continue

        # 1. Token masih hidup atau tidak
        try:
            r = requests.get(
                f"https://graph.facebook.com/v18.0/{page_id}",
                params={'access_token': token, 'fields': 'name'},
                timeout=20
            )
            if r.status_code == 200:
                alive = 'YA'
                note = 'OK - ' + (r.json().get('name') or '')[:30]
                aktif += 1
            else:
                err = r.json().get('error', {})
                alive = 'TIDAK'
                note = f"code={err.get('code')} {(err.get('message') or '')[:50]}"
                mati += 1
        except Exception as e:
            alive = '?'
            note = f"gagal konek: {type(e).__name__}"

        # 2. Masa berlaku (debug_token self-inspect)
        exp = '?'
        try:
            data = requests.get(
                "https://graph.facebook.com/v18.0/debug_token",
                params={'input_token': token, 'access_token': token},
                timeout=20
            ).json().get('data', {})
            if 'expires_at' in data:
                ea = data.get('expires_at')
                exp = 'TIDAK PERNAH' if not ea else datetime.datetime.fromtimestamp(ea).strftime('%Y-%m-%d')
        except Exception:
            pass

        print(f"{name:<18}{alive:<8}{exp:<16}{created:<12} {note}")

    print("-" * 100)
    print(f"Aktif: {aktif}   Bermasalah: {mati}")


if __name__ == '__main__':
    main()
