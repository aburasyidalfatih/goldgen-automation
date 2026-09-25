"""Tukar jam posting terburuk dengan jam terbaik yang sudah terbukti.

Keterbatasan data: bot hanya punya bukti untuk jam yang pernah dipakai posting.
Jam yang belum pernah dicoba tidak punya bukti — bukan berarti jelek. Karena itu
yang dilakukan hanya MENUKAR satu jam per page per eksekusi, dan hanya dengan
jam yang punya cukup sampel. Jumlah slot per page tidak berubah, jadi frekuensi
posting tetap sama.

Dipakai oleh scripts/apply_best_hours.py (manual) dan worker mingguan
(otomatis, bisa dimatikan dengan "auto_best_hours": false di config.json).
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

MIN_SAMPLES = 5   # hindari keputusan jadwal dari satu atau dua post viral
MIN_EFFECTIVE = 3


def propose(page, timing_report=None):
    """Usulan (buang, pakai, alasan) untuk satu page, atau (None, None, alasan)."""
    if timing_report is None:
        from learning_insights import timing_report
    schedule = sorted(page.get('schedule_hours') or [])
    if not schedule:
        return None, None, 'memakai interval_hours, bukan jadwal per jam'

    stats = {t['hour']: t for t in timing_report(page['page_id'])
             if t['n'] >= MIN_SAMPLES and t.get('effective_n', 0) >= MIN_EFFECTIVE}
    if len(stats) < 2:
        return None, None, f'data belum cukup (butuh >= {MIN_SAMPLES} post per jam)'

    candidates = [h for h in stats if h not in schedule]
    if not candidates:
        return None, None, 'tidak ada jam alternatif yang punya data'

    best = max(candidates, key=lambda h: stats[h]['confident_score'])
    scheduled_with_data = [h for h in schedule if h in stats]
    if scheduled_with_data:
        worst = min(scheduled_with_data, key=lambda h: stats[h]['confident_score'])
        if stats[best]['confident_score'] <= stats[worst]['confident_score']:
            return None, None, (f"jadwal sudah optimal (terburuk {worst:02d}:00 = "
                                f"{stats[worst]['confident_score']:.2f} >= kandidat {best:02d}:00 = "
                                f"{stats[best]['confident_score']:.2f})")
        reason = (f"{worst:02d}:00 skor {stats[worst]['confident_score']:.2f} ({stats[worst]['n']} post) -> "
                  f"{best:02d}:00 skor {stats[best]['confident_score']:.2f} ({stats[best]['n']} post)")
    else:
        # Jam yang dijadwalkan sekarang belum punya bukti sama sekali, sementara
        # ada jam lain yang sudah terbukti bagus dari riwayat.
        worst = schedule[0]
        reason = (f"{worst:02d}:00 belum punya bukti -> {best:02d}:00 skor "
                  f"{stats[best]['confident_score']:.2f} ({stats[best]['n']} post)")
    return worst, best, reason


def apply_best_hours(config_path, apply=True, timing_report=None):
    """Terapkan maksimal satu tukar jam per page. Mengembalikan daftar laporan."""
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    results, changed = [], False
    for page in config.get('fanspages', []):
        if not page.get('enabled', True):
            continue
        worst, best, reason = propose(page, timing_report)
        entry = {'page': page.get('name', page.get('page_id')), 'reason': reason,
                 'before': sorted(page.get('schedule_hours') or []), 'after': None}
        if worst is not None and apply:
            page['schedule_hours'] = sorted({h for h in page['schedule_hours'] if h != worst} | {best})
            entry['after'] = page['schedule_hours']
            changed = True
        results.append(entry)
    if changed:
        backup = config_path.with_name(config_path.name + f".backup.{datetime.now():%Y%m%d_%H%M%S}")
        shutil.copy(config_path, backup)
        tmp = config_path.with_name(config_path.name + '.tmp')
        tmp.write_text(json.dumps(config, indent=2), encoding='utf-8')
        tmp.replace(config_path)
    return results
