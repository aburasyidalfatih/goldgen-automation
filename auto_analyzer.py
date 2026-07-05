#!/usr/bin/env python3
"""
Auto Analyzer - Goldgen Automation
Menganalisis komentar terbaru menggunakan Gemini AI untuk mengupdate insights secara otomatis.
Dijalankan via cron job.
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path
from comment_analyzer import CommentAnalyzer

def main():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Memulai Auto Analyzer...")
    try:
        analyzer = CommentAnalyzer()
    except Exception as e:
        print(f"❌ Gagal inisialisasi Analyzer: {e}")
        return

    results = []
    for page in analyzer.fanspages:
        page_name = page['name']
        page_id = page['page_id']
        access_token = page['access_token']

        print(f"\n▶ Menganalisa halaman: {page_name}")
        
        # Ambil komentar dari 3 hari terakhir (bisa disesuaikan)
        comments = analyzer.get_recent_comments(page_id, access_token, days=3)
        if len(comments) < 3:
            print(f"   ⚠️ Hanya {len(comments)} komentar, dilewati (minimal 3)")
            results.append({'page': page_name, 'status': 'skipped', 'reason': f'Only {len(comments)} comments'})
            continue

        print(f"   💬 Ditemukan {len(comments)} komentar. Menganalisa dengan Gemini...")
        analysis = analyzer.analyze_with_gemini(comments, page_name)
        if not analysis:
            print(f"   ❌ Gagal menganalisa dengan Gemini")
            results.append({'page': page_name, 'status': 'error', 'reason': 'Gemini analysis failed'})
            continue

        analyzer.save_insight(page_id, page_name, len(comments), analysis)
        print(f"   ✅ Analisis berhasil disimpan (Sentimen: {analysis.get('sentiment')})")
        results.append({
            'page': page_name,
            'status': 'success',
            'total_comments': len(comments)
        })
    
    print("\n" + "="*50)
    print("✅ Auto Analyzer Selesai")
    print("="*50)

if __name__ == "__main__":
    # Locking mechanism to prevent concurrent execution
    try:
        import fcntl
        lock_file = open('data/analyzer.lock', 'w')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("⏳ Another auto_analyzer instance is running. Exiting.")
            sys.exit(0)
    except ImportError:
        import msvcrt
        lock_file = open('data/analyzer.lock', 'w')
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except IOError:
            print("⏳ Another auto_analyzer instance is running. Exiting.")
            sys.exit(0)
            
    main()
