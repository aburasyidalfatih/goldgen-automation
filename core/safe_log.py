"""
Penyensor kredensial untuk pesan log.

Library HTTP (requests) menyertakan URL lengkap di pesan error-nya. Karena
access token Facebook dan API key Gemini dikirim sebagai query parameter,
token itu ikut tercetak utuh ke log setiap kali ada error — dan token halaman
Facebook yang long-lived tidak punya masa kedaluwarsa.

Selalu bungkus pesan error dengan redact() sebelum dicetak.
"""

import re

# access_token=..., key=..., client_secret=... pada URL/query string
_PARAM_PATTERN = re.compile(
    r'((?:access_token|key|api_key|client_secret|token_secret|password)=)([^&\s"\']+)',
    re.IGNORECASE
)

# Token Facebook biasanya diawali "EAA"; API key Google diawali "AIza".
# Ditangkap juga kalau muncul tanpa nama parameter.
_BARE_TOKEN_PATTERN = re.compile(r'\b(EAA[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_\-]{20,})\b')


def redact(value):
    """Ganti kredensial di dalam teks dengan penanda tersensor.

    Menerima string maupun exception. Selalu mengembalikan string yang aman
    dicetak ke log.
    """
    if value is None:
        return ''
    text = str(value)
    text = _PARAM_PATTERN.sub(lambda m: f"{m.group(1)}***DISENSOR***", text)
    text = _BARE_TOKEN_PATTERN.sub('***DISENSOR***', text)
    return text
