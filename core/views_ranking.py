"""Grouping and ordering for the 30-day views dashboard."""


def group_views_by_page(rows):
    groups = {}
    for source in rows:
        row = dict(source)
        group = groups.setdefault(row['page_id'], {
            'page_id': row['page_id'],
            'page_name': row['page_name'],
            'posts': [],
            'measured': 0,
            'total_views': 0,
        })
        if row.get('media_views') is not None:
            group['measured'] += 1
            group['total_views'] += max(0, int(row['media_views']))
        group['posts'].append(row)

    # Total measured views is the primary ordering criterion. Coverage breaks
    # ties, followed by name to keep the output deterministic.
    return sorted(
        groups.values(),
        key=lambda group: (
            -group['total_views'],
            -group['measured'],
            str(group['page_name'] or '').lower(),
        ),
    )
