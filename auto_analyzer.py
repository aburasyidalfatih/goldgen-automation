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
        
        # Ambil metrik diam (Likes & Shares)
        silent_metrics = analyzer.get_silent_engagement_metrics(page_id, access_token, days=3)
        if silent_metrics:
            print(f"   📈 Menemukan {len(silent_metrics)} postingan dengan Silent Engagement tinggi")

        if len(comments) < 3 and not silent_metrics:
            print(f"   ⚠️ Hanya {len(comments)} komentar dan tidak ada keviralan bisu, dilewati")
            results.append({'page': page_name, 'status': 'skipped', 'reason': f'Insufficient data'})
            continue

        print(f"   🤖 Menganalisa {len(comments)} komentar dan {len(silent_metrics)} metrik dengan Gemini...")
        analysis = analyzer.analyze_with_gemini(comments, page_name, silent_metrics=silent_metrics, page_id=page_id)
        
        if not analysis:
            print(f"   ❌ Gagal menganalisa dengan Gemini")
            results.append({'page': page_name, 'status': 'error', 'reason': 'Gemini analysis failed'})
            continue

        print(f"   👁️  Mencari postingan visual terbaik (Vision AI)...")
        best_img = analyzer.get_most_engaged_image(page_id, access_token)
        if best_img:
            vision_styles = analyzer.analyze_vision_styles(best_img)
            if vision_styles:
                print(f"   ✅ Vision AI menemukan gaya visual pemenang: {vision_styles}")
                analysis['preferred_visual_styles'] = vision_styles
            else:
                print(f"   ⚠️  Vision AI gagal mengekstrak gaya visual")

        # Hitung Bobot Keviralan (Weighted Scoring)
        # Dasar 1 poin. Tambah bobot jika komentar atau silent metrics (likes/shares) tinggi.
        weight = 1 + int(len(comments) * 0.1) + int(len(silent_metrics or []) * 0.5)
        
        analyzer.save_insight(page_id, page_name, len(comments), analysis, weight=weight)
        print(f"   ✅ Analisis berhasil disimpan (Sentimen: {analysis.get('sentiment')}) dengan Bobot/Weight: {weight}")
        results.append({
            'page': page_name,
            'status': 'success',
            'total_comments': len(comments)
        })
    
    # Eksekusi Time Decay agar topik lama meluruh
    print("\n▶ Menerapkan efek peluruhan waktu (Time Decay) pada database...")
    analyzer.apply_time_decay()
    
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
