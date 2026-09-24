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


def capture_output():
    """Persist redacted stdout/stderr across container replacement, with rotation."""
    import logging
    import logging.handlers
    import sys
    from pathlib import Path
    from core.config import LOGS_DIR
    LOGS_DIR.mkdir(exist_ok=True)
    sink = logging.handlers.RotatingFileHandler(
        LOGS_DIR / (Path(sys.argv[0]).stem + '.log'),
        maxBytes=5_000_000, backupCount=4, encoding='utf-8')
    sink.setFormatter(logging.Formatter('%(asctime)s %(message)s'))

    class RedactedStream:
        def __init__(self, stream):
            self.stream = stream

        def write(self, text):
            safe = redact(text)
            result = self.stream.write(safe)
            if safe.strip():
                sink.handle(logging.LogRecord('goldgen', logging.INFO, '', 0, safe.rstrip(), (), None))
            return result

        def flush(self):
            self.stream.flush()
            sink.flush()

        def __getattr__(self, name):
            return getattr(self.stream, name)

    if not getattr(sys.stdout, '_goldgen_captured', False):
        for name in ('stdout', 'stderr'):
            wrapped = RedactedStream(getattr(sys, name))
            wrapped._goldgen_captured = True
            setattr(sys, name, wrapped)
