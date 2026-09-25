"""Shared topic/layout compatibility for selection and experiments."""


def shipped_layouts():
    """Katalog layout yang ikut di-deploy, di luar volume /app/data.

    Dockerfile menyalin data/layouts.json ke /app/catalog saat build. Volume
    data yang permanen menutupi /app/data, jadi tanpa salinan ini perubahan
    katalog di repo (mis. pensiun tiga layout pada 15 September) tidak pernah
    sampai ke produksi.
    """
    import json
    from core.config import BASE_DIR
    path = BASE_DIR / 'catalog' / 'layouts.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []


def curate_layouts(layouts, shipped=None):
    """Expose new layouts even when /app/data is an older persistent volume.

    Keep existing compositions, retirement decisions and learned priors intact.
    From the shipped catalog, only additions and retirements are applied: a
    layout retired in the repo is retired here too, but never un-retired.
    This projection does not rewrite the user's persisted configuration.
    """
    import copy
    from core.hidden_gold_catalog import LAYOUT_DEFINITION
    result = copy.deepcopy(layouts)
    shipped = shipped_layouts() if shipped is None else shipped
    by_name = {item['name']: item for item in result}
    for item in shipped:
        current = by_name.get(item.get('name'))
        if current is None:
            result.append(copy.deepcopy(item))
            by_name[item['name']] = result[-1]
        elif item.get('retired') and not current.get('retired'):
            current['retired'] = True
            current['retired_reason'] = item.get('retired_reason', 'Dipensiunkan di katalog repo')
    if LAYOUT_DEFINITION['name'] not in by_name:
        result.append(copy.deepcopy(LAYOUT_DEFINITION))
    return result


def compatible(topic, layout):
    topic = topic or {}
    if layout.get('retired'):
        return False
    allowed = topic.get('allowed_layouts')
    if allowed is not None and layout['name'] not in allowed:
        return False
    series = layout.get('topic_series')
    return series is None or topic.get('series') in series
