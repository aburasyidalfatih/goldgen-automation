"""Conservative local exclusions shared by learning and replies."""
import re
import unicodedata


def is_promotional_spam(text):
    if not isinstance(text, str):
        return False
    # Normalize decorative Unicode used to evade ordinary keyword filters.
    normalized = unicodedata.normalize('NFKC', text).casefold()
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Cf')
    compact = re.sub(r'[^a-z0-9]', '', normalized)
    if any(brand in compact for brand in ('buayatoto', 'kinghoki4d')):
        return True
    terms = sum(bool(re.search(pattern, normalized)) for pattern in (
        r'\b(?:slot|togel|casino|judi)\b',
        r'\b(?:deposit|withdraw|jackpot|gacor)\b',
        r'https?://|\b(?:daftar|bonus|promo)\b'))
    return terms >= 3
