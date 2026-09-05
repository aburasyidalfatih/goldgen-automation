#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ringkasan klik dan interaksi untuk diagnosis awal.
Klik bukan jangkauan atau jumlah orang unik. Rasio engagement/klik bukan
conversion rate dan tidak memisahkan penyebab distribusi dari kualitas konten.

Pakai:
    python scripts/reach_check.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import DB_PATH  # noqa: E402

PAGES = (
    ('488507404341313', 'Putri Kejora'),
    ('109490145423939', 'Kedai Digital'),
    ('664499226752760', 'Miners 24'),
)


def main():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    print('=== KLIK PER PAGE PER HARI ===')
    for pid, nama in PAGES:
        rows = list(c.execute(
            "SELECT date(timestamp) hari, count(*) n, avg(clicks) k, avg(engagement) e "
            "FROM post_engagement WHERE page_id=? AND source='snapshot48' AND clicks IS NOT NULL "
            "GROUP BY hari ORDER BY hari", (pid,)))
        print('\n  %s' % nama)
        if not rows:
            print('     belum ada data klik')
        for r in rows:
            bar = '#' * min(40, int((r['k'] or 0) / 10))
            print('     %s n=%s klik=%6.0f eng=%5.1f %s' % (
                r['hari'], r['n'], r['k'] or 0, r['e'] or 0, bar))

    print('\n=== PERBANDINGAN ENGAGEMENT/KLIK — bukan conversion rate atau bukti penyebab ===')
    for r in c.execute(
            "SELECT date(timestamp) hari, sum(engagement) e, sum(clicks) k "
            "FROM post_engagement WHERE source='snapshot48' AND clicks IS NOT NULL "
            "GROUP BY hari ORDER BY hari"):
        if r['k']:
            print('  %s  klik %-5s eng %-4s -> rasio %.0f%%' % (
                r['hari'], r['k'], r['e'], 100.0 * r['e'] / r['k']))

    print('\n=== KUNJUNGAN & INTERAKSI HALAMAN ===')
    for pid, nama in PAGES:
        rows = list(c.execute(
            "SELECT captured_date, followers_count, post_engagements, page_views "
            "FROM page_stats WHERE page_id=? AND post_engagements IS NOT NULL "
            "ORDER BY captured_date", (pid,)))
        if rows:
            print('\n  %s' % nama)
            for r in rows:
                print('     %s pengikut %-7s interaksi %-6s kunjungan %s' % (
                    r['captured_date'], r['followers_count'],
                    r['post_engagements'], r['page_views']))

    print('\n=== JUMLAH POSTINGAN PER HARI ===')
    for r in c.execute(
            "SELECT date(timestamp) hari, count(*) n FROM posts "
            "WHERE status='success' AND timestamp>=datetime('now','-14 days') "
            "GROUP BY hari ORDER BY hari"):
        print('  %s  %s postingan' % (r['hari'], r['n']))

    c.close()


if __name__ == '__main__':
    main()
