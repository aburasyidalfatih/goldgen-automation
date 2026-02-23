#!/usr/bin/env python3
"""
24/7 Readiness Audit for GoldGen Automation
"""

import os
import sys
from pathlib import Path
import json
import sqlite3

print("=" * 70)
print("24/7 READINESS AUDIT - GOLDGEN AUTOMATION")
print("=" * 70)
print()

issues = []
warnings = []
passed = []

# 1. Check critical files
print("1. CRITICAL FILES CHECK")
print("-" * 70)
critical_files = [
    'auto_poster.py',
    'goldgen_service.py',
    'gold_price_api.py',
    'run.sh',
    'data/config.json',
    'requirements.txt'
]

for file in critical_files:
    if Path(file).exists():
        print(f"   ✅ {file}")
        passed.append(f"File exists: {file}")
    else:
        print(f"   ❌ {file} - MISSING")
        issues.append(f"Missing critical file: {file}")
print()

# 2. Check configuration
print("2. CONFIGURATION CHECK")
print("-" * 70)
try:
    with open('data/config.json', 'r') as f:
        config = json.load(f)
    
    # Check Gemini API key
    if config.get('gemini_api_key'):
        print(f"   ✅ Gemini API Key configured")
        passed.append("Gemini API key present")
    else:
        print(f"   ❌ Gemini API Key missing")
        issues.append("Gemini API key not configured")
    
    # Check fanspages
    fanspages = config.get('fanspages', [])
    if len(fanspages) > 0:
        print(f"   ✅ {len(fanspages)} fanspage(s) configured")
        passed.append(f"{len(fanspages)} fanspages configured")
        
        for fp in fanspages:
            name = fp.get('name', 'Unknown')
            if fp.get('access_token'):
                print(f"      ✅ {name}: Token present")
            else:
                print(f"      ❌ {name}: Token missing")
                issues.append(f"Missing token for {name}")
            
            if fp.get('enabled', True):
                print(f"      ✅ {name}: Enabled")
            else:
                print(f"      ⚠️  {name}: Disabled")
                warnings.append(f"{name} is disabled")
    else:
        print(f"   ❌ No fanspages configured")
        issues.append("No fanspages configured")
except Exception as e:
    print(f"   ❌ Config error: {e}")
    issues.append(f"Config file error: {e}")
print()

# 3. Check database
print("3. DATABASE CHECK")
print("-" * 70)
db_path = Path('data/posts.db')
if db_path.exists():
    print(f"   ✅ Database exists")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'posts' in tables:
            print(f"   ✅ 'posts' table exists")
            
            # Check post count
            cursor.execute("SELECT COUNT(*) FROM posts")
            count = cursor.fetchone()[0]
            print(f"   ✅ {count} posts logged")
            passed.append(f"Database has {count} posts")
        else:
            print(f"   ❌ 'posts' table missing")
            issues.append("Posts table missing in database")
        
        conn.close()
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        issues.append(f"Database error: {e}")
else:
    print(f"   ⚠️  Database doesn't exist (will be created)")
    warnings.append("Database will be created on first run")
print()

# 4. Check cron job
print("4. CRON JOB CHECK")
print("-" * 70)
import subprocess
try:
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    cron_content = result.stdout
    
    if 'goldgen-automation' in cron_content or 'run.sh' in cron_content:
        print(f"   ✅ Cron job configured")
        
        # Extract cron line
        for line in cron_content.split('\n'):
            if 'goldgen' in line.lower() or 'run.sh' in line:
                print(f"      Schedule: {line.strip()}")
        passed.append("Cron job active")
    else:
        print(f"   ❌ Cron job not found")
        issues.append("Cron job not configured")
except Exception as e:
    print(f"   ❌ Cron check error: {e}")
    issues.append(f"Cannot check cron: {e}")
print()

# 5. Check Python dependencies
print("5. DEPENDENCIES CHECK")
print("-" * 70)
required_packages = [
    'google-genai',
    'requests',
    'Pillow',
    'flask',
    'flask-cors'
]

for package in required_packages:
    try:
        __import__(package.replace('-', '_').replace('Pillow', 'PIL'))
        print(f"   ✅ {package}")
        passed.append(f"Package installed: {package}")
    except ImportError:
        print(f"   ❌ {package} - NOT INSTALLED")
        issues.append(f"Missing package: {package}")
print()

# 6. Check directories
print("6. DIRECTORY STRUCTURE CHECK")
print("-" * 70)
required_dirs = [
    'data',
    'logs',
    'generated_images',
    'venv'
]

for dir_name in required_dirs:
    dir_path = Path(dir_name)
    if dir_path.exists() and dir_path.is_dir():
        print(f"   ✅ {dir_name}/")
        passed.append(f"Directory exists: {dir_name}")
    else:
        print(f"   ❌ {dir_name}/ - MISSING")
        issues.append(f"Missing directory: {dir_name}")
print()

# 7. Check error handling
print("7. ERROR HANDLING CHECK")
print("-" * 70)
try:
    with open('auto_poster.py', 'r') as f:
        code = f.read()
    
    if 'try:' in code and 'except' in code:
        print(f"   ✅ Exception handling present")
        passed.append("Error handling implemented")
    else:
        print(f"   ⚠️  Limited exception handling")
        warnings.append("Consider adding more error handling")
    
    if 'logging' in code or 'print(' in code:
        print(f"   ✅ Logging present")
        passed.append("Logging implemented")
    else:
        print(f"   ⚠️  No logging found")
        warnings.append("Consider adding logging")
except Exception as e:
    print(f"   ❌ Cannot check code: {e}")
print()

# 8. Check disk space
print("8. DISK SPACE CHECK")
print("-" * 70)
try:
    import shutil
    total, used, free = shutil.disk_usage('/')
    free_gb = free // (2**30)
    
    if free_gb > 5:
        print(f"   ✅ Free space: {free_gb} GB")
        passed.append(f"Sufficient disk space: {free_gb} GB")
    elif free_gb > 1:
        print(f"   ⚠️  Free space: {free_gb} GB (low)")
        warnings.append(f"Low disk space: {free_gb} GB")
    else:
        print(f"   ❌ Free space: {free_gb} GB (critical)")
        issues.append(f"Critical disk space: {free_gb} GB")
except Exception as e:
    print(f"   ⚠️  Cannot check disk space: {e}")
print()

# 9. Check topic rotation
print("9. TOPIC ROTATION CHECK")
print("-" * 70)
try:
    from goldgen_service import GoldGenService
    service = GoldGenService('test')
    
    topic_count = len(service.topics)
    print(f"   ✅ {topic_count} topics loaded")
    
    if topic_count >= 50:
        print(f"   ✅ Full topic set (50 topics)")
        passed.append(f"{topic_count} topics available")
    else:
        print(f"   ⚠️  Only {topic_count} topics")
        warnings.append(f"Expected 50 topics, found {topic_count}")
except Exception as e:
    print(f"   ❌ Topic loading error: {e}")
    issues.append(f"Cannot load topics: {e}")
print()

# 10. Check permissions
print("10. FILE PERMISSIONS CHECK")
print("-" * 70)
executable_files = ['run.sh', 'auto_poster.py']
for file in executable_files:
    file_path = Path(file)
    if file_path.exists():
        if os.access(file_path, os.X_OK):
            print(f"   ✅ {file} - Executable")
            passed.append(f"{file} is executable")
        else:
            print(f"   ⚠️  {file} - Not executable")
            warnings.append(f"{file} should be executable")
print()

# SUMMARY
print("=" * 70)
print("AUDIT SUMMARY")
print("=" * 70)
print(f"✅ Passed: {len(passed)}")
print(f"⚠️  Warnings: {len(warnings)}")
print(f"❌ Issues: {len(issues)}")
print()

if issues:
    print("🔴 CRITICAL ISSUES (Must fix before 24/7):")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    print()

if warnings:
    print("🟡 WARNINGS (Recommended improvements):")
    for i, warning in enumerate(warnings, 1):
        print(f"   {i}. {warning}")
    print()

# Final verdict
print("=" * 70)
if len(issues) == 0:
    print("✅ VERDICT: READY FOR 24/7 OPERATION")
    if warnings:
        print("   (Some improvements recommended)")
else:
    print("❌ VERDICT: NOT READY - Fix critical issues first")
print("=" * 70)

sys.exit(0 if len(issues) == 0 else 1)
