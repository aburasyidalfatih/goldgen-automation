"""Shared topic/layout compatibility for selection and experiments."""


def curate_layouts(layouts):
    """Expose new layouts even when /app/data is an older persistent volume.

    Keep existing compositions, retirement decisions and learned priors intact.
    This projection does not rewrite the user's persisted configuration.
    """
    import copy
    from core.hidden_gold_catalog import LAYOUT_DEFINITION
    result = copy.deepcopy(layouts)
    if not any(item['name'] == LAYOUT_DEFINITION['name'] for item in result):
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
