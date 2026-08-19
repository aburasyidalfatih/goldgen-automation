#!/usr/bin/env python3
"""
Telegram Notifier - Goldgen Automation

Mengirim notifikasi (post sukses, token expired, error) ke Telegram.
Kredensial dibaca dari environment variable, atau dari data/config.json:

    "telegram_bot_token": "123456:ABC...",
    "telegram_chat_id": "-1001234567890"

Jika tidak dikonfigurasi, fungsi ini diam saja (no-op) — bot tetap jalan normal.
"""

import json
import os

import requests

from core.config import CONFIG_PATH


def _load_credentials():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
            token = token or config.get('telegram_bot_token')
            chat_id = chat_id or config.get('telegram_chat_id')
        except Exception:
            pass

    return token, chat_id


def send_notification(message, parse_mode='HTML'):
    """Kirim pesan ke Telegram. Return True jika terkirim, False jika dilewati/gagal."""
    token, chat_id = _load_credentials()
    if not token or not chat_id:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={'chat_id': chat_id, 'text': message, 'parse_mode': parse_mode},
            timeout=10
        )
        if response.status_code != 200:
            print(f"⚠️  Telegram notification failed: {response.text[:150]}")
            return False
        return True
    except Exception as e:
        print(f"⚠️  Telegram notification error: {e}")
        return False


if __name__ == '__main__':
    ok = send_notification("✅ <b>Goldgen Bot</b>\n\nTes notifikasi Telegram berhasil.")
    print("Terkirim!" if ok else "Dilewati — telegram_bot_token / telegram_chat_id belum dikonfigurasi.")
