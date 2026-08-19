#!/usr/bin/env python3
"""
Web Dashboard for GoldGen Auto Poster
Simple Flask API to serve dashboard data
"""

from flask import (
    Flask, jsonify, request, session, redirect, url_for,
    render_template, send_from_directory
)
from flask_cors import CORS
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json
from functools import wraps

from flask import Blueprint
bp = Blueprint('api', __name__)

from core.config import BASE_DIR, DB_PATH, IMAGES_DIR, DATA_DIR, CONFIG_PATH, DASHBOARD_PIN
from core.database import get_db_connection


def require_pin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized', 'require_auth': True}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    return get_db_connection()


@bp.route("/")
def index():
    """Redirect to login or dashboard based on auth status"""
    if session.get('authenticated'):
        return redirect('/dashboard')
    return redirect('/login')

@bp.route("/login")
def login_page():
    """Serve login page"""
    return render_template("login.html")

@bp.route("/dashboard")
@require_pin
def serve_dashboard():
    return render_template("dashboard_schedule.html")



@bp.route("/detail")
def serve_detail():
    """Serve app detail page (public access)"""
    return render_template("app_detail.html")

@bp.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate with PIN"""
    data = request.json
    pin = data.get('pin', '')
    
    if pin == DASHBOARD_PIN:
        session['authenticated'] = True
        return jsonify({'success': True, 'message': 'Authentication successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid PIN'}), 401

@bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout"""
    session.pop('authenticated', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@bp.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check if authenticated"""
    return jsonify({'authenticated': session.get('authenticated', False)})

@bp.route('/api/trigger-post', methods=['POST'])
@require_pin
def trigger_post():
    """Trigger an immediate manual post for a specific page"""
    data = request.json
    page_id = data.get('page_id')
    if not page_id:
        return jsonify({'success': False, 'error': 'Missing page_id'}), 400
        
    def run_poster():
        try:
            from auto_poster import GoldGenAutoPoster
            poster = GoldGenAutoPoster()
            poster.force_post(page_id)
        except Exception as e:
            print(f"Manual post trigger error: {e}")
            
    import threading
    threading.Thread(target=run_poster, daemon=True).start()
    
    return jsonify({'success': True, 'message': 'Post generation started in background'})

@bp.route('/api/stats')
@require_pin
def get_stats():
    """Get overall statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total posts
        cursor.execute("SELECT COUNT(*) as total FROM posts")
        total = cursor.fetchone()['total']
        
        # Today's posts (since midnight)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor.execute("SELECT COUNT(*) as today FROM posts WHERE timestamp >= ?", (today_start,))
        today = cursor.fetchone()['today']
        
        # Success count
        cursor.execute("SELECT COUNT(*) as success FROM posts WHERE status='success'")
        success = cursor.fetchone()['success']
        
        # Failed count
        # Hitung semua yang bukan sukses sebagai gagal — termasuk baris lama
        # yang tersimpan dengan status 'error'
        cursor.execute("SELECT COUNT(*) as failed FROM posts WHERE status != 'success'")
        failed = cursor.fetchone()['failed']
        
        # Last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("SELECT COUNT(*) as last24h FROM posts WHERE timestamp > ?", (yesterday,))
        last_24h = cursor.fetchone()['last24h']
        
        # Success rate
        success_rate = (success / total * 100) if total > 0 else 0
        
        conn.close()
        
        return jsonify({
            'total_posts': total,
            'today_posts': today,
            'total': total,
            'success': success,
            'failed': failed,
            'last_24h': last_24h,
            'success_rate': round(success_rate, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/posts')
@require_pin
def get_posts():
    """Get recent posts"""
    try:
        limit = 10
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, page_name, content, image_path, fb_post_id, status, error_message
            FROM posts 
            ORDER BY id DESC 
            LIMIT ?
        """, (limit,))
        
        posts = []
        for row in cursor.fetchall():
            content = row['content'] or ''
            posts.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'page_name': row['page_name'] if 'page_name' in row.keys() else None,
                'content': content[:200] + '...' if len(content) > 200 else content,
                'image_path': Path(row['image_path']).name if row['image_path'] else None,
                'fb_post_id': row['fb_post_id'],
                'status': row['status'],
                # Kalau gagal, alasan wajib ada — jangan biarkan kosong di UI
                'error_message': row['error_message'] or (
                    'Gagal tanpa keterangan (postingan lama sebelum pencatatan alasan diperbaiki)'
                    if row['status'] != 'success' else None
                )
            })
        
        conn.close()
        
        return jsonify({'posts': posts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/next-run')
@require_pin
def get_next_run():
    """Get next scheduled run time and all fanspages schedule"""
    now = datetime.now()
    
    # Cron runs every hour at :00
    if now.minute == 0 and now.second < 5:
        # Currently at the hour, next run is next hour
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        # Next run is at the next hour
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    # Get ALL fanspages schedule
    all_schedules = []
    try:
        config_file = DATA_DIR / "config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
                fanspages = config.get('fanspages', [])
            
            conn = get_db()
            cursor = conn.cursor()
            
            # Track posting order for delay calculation
            ready_count = 0
            
            for idx, fp in enumerate(fanspages):
                # Get last post time
                cursor.execute('''
                    SELECT MAX(timestamp) as last_post 
                    FROM posts 
                    WHERE page_id = ?
                ''', (fp['page_id'],))
                
                result = cursor.fetchone()
                last_post = result['last_post'] if result['last_post'] else None
                
                if last_post:
                    last_post_time = datetime.fromisoformat(last_post)
                    interval_hours = fp.get('interval_hours', 6)
                    next_eligible_time = last_post_time + timedelta(hours=interval_hours)
                    
                    # Check if ready to post
                    if next_eligible_time <= next_run:
                        # Will post on next cron
                        # Calculate actual posting time with delay
                        delay_minutes = ready_count * config.get('fanspage_delay_minutes', 60)
                        actual_post_time = next_run + timedelta(minutes=delay_minutes)
                        # Next post after that
                        next_post_time = actual_post_time + timedelta(hours=interval_hours)
                        ready_count += 1
                    else:
                        # Not ready yet, use calculated time
                        next_post_time = next_eligible_time
                else:
                    # Never posted, will post on next cron
                    delay_minutes = ready_count * config.get('fanspage_delay_minutes', 60)
                    actual_post_time = next_run + timedelta(minutes=delay_minutes)
                    next_post_time = actual_post_time + timedelta(hours=interval_hours)
                    ready_count += 1
                    last_post_time = None
                
                time_until = next_post_time - now
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                
                # Status - all should be scheduled (future)
                if not fp.get('enabled', True):
                    status = 'disabled'
                    status_icon = '⏸️'
                else:
                    status = 'scheduled'
                    status_icon = '⏰'
                
                all_schedules.append({
                    'page_name': fp['name'],
                    'page_id': fp['page_id'],
                    'enabled': fp.get('enabled', True),
                    'interval_hours': fp.get('interval_hours', 6),
                    'last_post': last_post_time.strftime('%Y-%m-%d %H:%M') if last_post else 'Never',
                    'next_post_time': next_post_time.strftime('%Y-%m-%d %H:%M'),
                    'next_post_formatted': next_post_time.strftime('%H:%M WIB'),
                    'time_until': f'{hours}h {minutes}m' if hours > 0 else f'{minutes}m',
                    'status': status,
                    'status_icon': status_icon
                })
            
            # Sort by next_post_time
            all_schedules.sort(key=lambda x: x['next_post_time'])
            
            conn.close()
    except Exception as e:
        print(f"Error getting schedules: {e}")
    
    return jsonify({
        'next_run': next_run.isoformat(),
        'next_run_formatted': next_run.strftime('%Y-%m-%d %H:%M:%S') + ' WIB',
        'all_schedules': all_schedules
    })

@bp.route('/api/topic-info')
@require_pin
def get_topic_info():
    """Get current topic rotation info"""
    try:
        # Load from goldgen_service to get actual topics
        from goldgen_service import GoldGenService
        
        # Load config to get API key
        config_file = DATA_DIR / "config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
                api_key = config.get('gemini_api_key', 'dummy')
        else:
            api_key = 'dummy'
        
        service = GoldGenService(api_key)
        
        # Get current state
        state_file = DATA_DIR / "topic_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                current_index = state.get('current_topic_index', 0)
        else:
            current_index = 0
        
        # Get current and next topics
        current_topic = service.topics[current_index]
        next_index = (current_index + 1) % len(service.topics)
        next_topic = service.topics[next_index]
        
        # Get layout info
        current_layout_idx = current_index % len(service.layouts)
        next_layout_idx = next_index % len(service.layouts)
        current_layout = service.layouts[current_layout_idx]
        next_layout = service.layouts[next_layout_idx]
        
        return jsonify({
            'current': {
                'id': current_topic['id'],
                'name': current_topic['headline'],
                'subtitle': current_topic['subtitle'],
                'layout': current_layout['name'],
                'index': current_index
            },
            'next': {
                'id': next_topic['id'],
                'name': next_topic['headline'],
                'subtitle': next_topic['subtitle'],
                'layout': next_layout['name'],
                'index': next_index
            },
            'total_topics': len(service.topics),
            'total_layouts': len(service.layouts)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/images/<filename>')
def get_image(filename):
    """Serve generated images"""
    return send_from_directory(IMAGES_DIR, filename)

@bp.route('/api/config', methods=['GET'])
@require_pin
def get_config():
    """Get current configuration (without sensitive data)"""
    try:
        if not CONFIG_PATH.exists():
            return jsonify({'configured': False, 'fanspages': [], 'fanspage_delay_minutes': 60})
        
        config = {'fanspages': []}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        
        now = datetime.now()

        # Status token berdasarkan BUKTI NYATA, bukan tebakan kalender.
        #
        # Versi lama menghitung `60 - hari sejak token dibuat` dan menandai
        # EXPIRED setelah hari ke-60. Itu salah untuk long-lived page token yang
        # `expires_at`-nya 0 (tidak pernah kedaluwarsa) — semua page jadi merah
        # padahal tokennya sehat, dan peringatan yang selalu menyala jadi diabaikan.
        #
        # Sekarang: page ditandai bermasalah HANYA kalau percobaan posting terakhir
        # memang gagal karena token. Tidak ada request tambahan ke Facebook.
        token_failures = {}
        try:
            conn = get_db()
            rows = conn.execute("""
                SELECT page_id, status, error_message, timestamp
                FROM posts
                WHERE id IN (SELECT MAX(id) FROM posts GROUP BY page_id)
            """).fetchall()
            conn.close()
            for row in rows:
                msg = row['error_message'] or ''
                if row['status'] != 'success' and msg.startswith('TOKEN TIDAK AKTIF'):
                    token_failures[row['page_id']] = {'reason': msg[:200], 'since': row['timestamp']}
        except Exception as e:
            print(f"Token status check skipped: {e}")

        fanspages = []
        for page in config.get('fanspages', []):
            token_created = page.get('token_created_date')
            failure = token_failures.get(page.get('page_id'))

            if not page.get('access_token'):
                token_warning = "NO_TOKEN"
                token_message = "Belum ada token untuk page ini."
            elif failure:
                token_warning = "INVALID"
                token_message = failure['reason']
            else:
                token_warning = None
                token_message = None

            # Tidak lagi menebak sisa hari — long-lived token tidak punya masa berlaku
            days_until_expire = None

            fanspages.append({
                'name': page['name'],
                'page_id': page['page_id'],
                'interval_hours': page.get('interval_hours'),
                'schedule_hours': page.get('schedule_hours', []),
                'enabled': page.get('enabled', True),
                'has_token': bool(page.get('access_token')),
                'token_warning': token_warning,
                'token_message': token_message,
                'days_until_expire': days_until_expire,
                'token_created_date': token_created,
                'instagram_config': page.get('instagram_config', {}),
                'twitter_config': {
                    'api_key': page.get('twitter_config', {}).get('api_key', ''),
                    'api_secret': '********' if page.get('twitter_config', {}).get('api_secret') else '',
                    'access_token': '********' if page.get('twitter_config', {}).get('access_token') else '',
                    'token_secret': '********' if page.get('twitter_config', {}).get('token_secret') else ''
                },
                'pinterest_config': {
                    'access_token': '********' if page.get('pinterest_config', {}).get('access_token') else '',
                    'board_id': page.get('pinterest_config', {}).get('board_id', '')
                },
                'threads_config': {
                    'access_token': '********' if page.get('threads_config', {}).get('access_token') else '',
                    'user_id': page.get('threads_config', {}).get('user_id', '')
                }
            })
        
        return jsonify({
            'configured': True,
            'has_gemini_key': bool(config.get('gemini_api_key')),
            'image_model': config.get('image_model', 'gemini-3.1-flash-image'),
            'text_model': config.get('text_model', 'gemini-3.5-flash'),
            'fanspage_delay_minutes': config.get('fanspage_delay_minutes', 60),
            'fanspages': fanspages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/config', methods=['POST'])
@require_pin
def update_config():
    """Update configuration"""
    try:
        data = request.json
        
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        else:
            config = {'fanspages': []}
        
        if 'gemini_api_key' in data and data['gemini_api_key']:
            config['gemini_api_key'] = data['gemini_api_key']
        
        if 'fanspage_delay_minutes' in data:
            config['fanspage_delay_minutes'] = int(data['fanspage_delay_minutes'])
        
        if 'fanspages' in data:
            # Merge with existing fanspages to preserve tokens
            existing_pages = {p['page_id']: p for p in config.get('fanspages', [])}
            
            new_fanspages = []
            for new_page in data['fanspages']:
                page_id = new_page['page_id']
                
                # Start with existing page data if it exists
                if page_id in existing_pages:
                    merged_page = existing_pages[page_id].copy()
                    # Update with new data
                    merged_page.update(new_page)
                    # Preserve existing token if new one not provided
                    if 'access_token' not in new_page and 'access_token' in existing_pages[page_id]:
                        merged_page['access_token'] = existing_pages[page_id]['access_token']
                else:
                    merged_page = new_page
                
                new_fanspages.append(merged_page)
            
            config['fanspages'] = new_fanspages
        
        DATA_DIR.mkdir(exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Configuration updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/fanspages', methods=['POST'])
@require_pin
def add_fanspage():
    """Add new fanspage"""
    try:
        data = request.json
        
        config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        
        if 'fanspages' not in config:
            config['fanspages'] = []
        
        # Check if page_id already exists
        if any(fp['page_id'] == data['page_id'] for fp in config['fanspages']):
            return jsonify({'error': 'Fanspage with this Page ID already exists'}), 400
        
        new_fanspage = {
            'name': data['name'],
            'page_id': data['page_id'],
            'access_token': data['access_token'],
            'enabled': True,
            'token_created_date': datetime.now().isoformat()
        }
        
        # Support both interval_hours and schedule_hours
        if 'schedule_hours' in data:
            new_fanspage['schedule_hours'] = data['schedule_hours']
        elif 'interval_hours' in data:
            new_fanspage['interval_hours'] = int(data['interval_hours'])
            
        # Per-fanspage multi-platform
        for platform in ['twitter_config', 'pinterest_config', 'threads_config', 'instagram_config']:
            if platform in data:
                new_fanspage[platform] = data[platform]
        
        config['fanspages'].append(new_fanspage)
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/fanspages/<page_id>', methods=['PUT'])
@require_pin
def update_fanspage(page_id):
    """Update fanspage"""
    try:
        data = request.json
        
        config = {'fanspages': []}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        
        for page in config['fanspages']:
            if page['page_id'] == page_id:
                if 'name' in data:
                    page['name'] = data['name']
                if 'interval_hours' in data:
                    page['interval_hours'] = int(data['interval_hours'])
                if 'schedule_hours' in data:
                    page['schedule_hours'] = data['schedule_hours']
                    # Remove interval_hours if schedule_hours is set
                    page.pop('interval_hours', None)
                if 'enabled' in data:
                    page['enabled'] = data['enabled']
                if 'access_token' in data and data['access_token']:
                    page['access_token'] = data['access_token']
                    page['token_created_date'] = datetime.now().isoformat()
                
                # Per-fanspage multi-platform
                for platform in ['twitter_config', 'pinterest_config', 'threads_config', 'instagram_config']:
                    if platform in data:
                        page[platform] = data[platform]
                break
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/fanspages/<page_id>', methods=['DELETE'])
@require_pin
def delete_fanspage(page_id):
    """Delete fanspage"""
    try:
        config = {'fanspages': []}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        
        config['fanspages'] = [p for p in config['fanspages'] if p['page_id'] != page_id]
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/queue-post', methods=['POST'])
@require_pin
def queue_post():
    """Queue a post from web app for auto posting"""
    try:
        data = request.json
        
        # Validate required fields
        required = ['caption', 'image_data', 'page_ids']
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Save image
        import base64
        from datetime import datetime
        
        image_data = data['image_data'].split(',')[1]  # Remove data:image/png;base64,
        image_bytes = base64.b64decode(image_data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = IMAGES_DIR / f"queued_poster_{timestamp}.png"
        
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        
        # Queue for each page (skema tabel dikelola core/database.py)
        conn = get_db()
        cursor = conn.cursor()

        # Add to queue
        now_iso = datetime.now().isoformat()
        for page_id in data['page_ids']:
            cursor.execute('''
                INSERT INTO post_queue (page_id, content, image_path, scheduled_time, created_at, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (page_id, data['caption'], str(image_path), now_iso, now_iso))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Queued for {len(data["page_ids"])} page(s)',
            'image_path': str(image_path)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/queue', methods=['GET'])
@require_pin
def get_queue():
    """Get pending posts in queue"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, page_id, content, image_path, status,
                   COALESCE(created_at, scheduled_time) as created_at
            FROM post_queue
            WHERE status = 'pending'
            ORDER BY COALESCE(created_at, scheduled_time) DESC
        ''')

        queue = []
        for row in cursor.fetchall():
            content = row['content'] or ''
            queue.append({
                'id': row['id'],
                'page_id': row['page_id'],
                'caption': content[:100] + ('...' if len(content) > 100 else ''),
                'image_path': Path(row['image_path']).name if row['image_path'] else None,
                'status': row['status'],
                'created_at': row['created_at']
            })
        
        conn.close()
        
        return jsonify({'queue': queue})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/health')
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@bp.route('/api/bot-status', methods=['GET'])
@require_pin
def get_bot_status():
    """Get bot enabled/disabled status"""
    disabled_file = BASE_DIR / ".DISABLED"
    is_enabled = not disabled_file.exists()
    return jsonify({'enabled': is_enabled})

@bp.route('/api/bot-toggle', methods=['POST'])
@require_pin
def toggle_bot():
    """Toggle bot on/off"""
    disabled_file = BASE_DIR / ".DISABLED"
    
    if disabled_file.exists():
        # Enable bot
        disabled_file.unlink()
        return jsonify({'enabled': True, 'message': 'Bot enabled'})
    else:
        # Disable bot
        with open(disabled_file, 'w') as f:
            f.write(f'Bot disabled at {datetime.now().isoformat()}')
        return jsonify({'enabled': False, 'message': 'Bot disabled'})

@bp.route('/api/stats/enhanced')
@require_pin
def get_stats_enhanced():
    """Get enhanced statistics with today's posts"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total posts
        cursor.execute("SELECT COUNT(*) as total FROM posts")
        total = cursor.fetchone()['total']
        
        # Today's posts
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor.execute("SELECT COUNT(*) as today FROM posts WHERE timestamp >= ?", (today_start,))
        today = cursor.fetchone()['today']
        
        # Success count
        cursor.execute("SELECT COUNT(*) as success FROM posts WHERE status='success'")
        success = cursor.fetchone()['success']
        
        # Failed count
        # Hitung semua yang bukan sukses sebagai gagal — termasuk baris lama
        # yang tersimpan dengan status 'error'
        cursor.execute("SELECT COUNT(*) as failed FROM posts WHERE status != 'success'")
        failed = cursor.fetchone()['failed']
        
        # Last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("SELECT COUNT(*) as last24h FROM posts WHERE timestamp > ?", (yesterday,))
        last_24h = cursor.fetchone()['last24h']
        
        # Success rate
        success_rate = (success / total * 100) if total > 0 else 0
        
        conn.close()
        
        return jsonify({
            'total_posts': total,
            'today_posts': today,
            'success': success,
            'failed': failed,
            'last_24h': last_24h,
            'success_rate': round(success_rate, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/app-info', methods=['GET'])
def get_app_info():
    """Get application information and details"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get total posts
        cursor.execute("SELECT COUNT(*) as total FROM posts")
        total_posts = cursor.fetchone()['total']
        
        # Get successful posts
        cursor.execute("SELECT COUNT(*) as total FROM posts WHERE status='success'")
        success_posts = cursor.fetchone()['total']
        
        # Get failed posts
        cursor.execute("SELECT COUNT(*) as total FROM posts WHERE status != 'success'")
        failed_posts = cursor.fetchone()['total']
        
        # Get first post date
        cursor.execute("SELECT MIN(timestamp) as first_post FROM posts")
        first_post = cursor.fetchone()['first_post']
        
        # Get last post
        cursor.execute("SELECT timestamp, page_name, status FROM posts ORDER BY id DESC LIMIT 1")
        last_post = cursor.fetchone()
        
        # Get fanspages count
        fanspages_count = 0
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
            fanspages_count = len(config.get('fanspages', []))
        
        # Calculate uptime
        import os
        import psutil
        process = psutil.Process(os.getpid())
        uptime_seconds = (datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
        
        # Get disk usage
        import shutil
        total, used, free = shutil.disk_usage(str(BASE_DIR))
        
        conn.close()
        
        return jsonify({
            'app_name': 'GoldGen Auto Poster',
            'version': '2.0',
            'description': 'Automated Facebook posting system for gold price updates',
            'url': 'https://gold.kelasmaster.id',
            'port': 18794,
            'tech_stack': ['Python', 'Flask', 'SQLite', 'Gemini AI'],
            'features': [
                'Auto-generate gold price posters with AI',
                'Multi-fanpage support',
                'Scheduled posting every 3 hours',
                'Auto-reply to comments',
                'Web dashboard with PIN authentication',
                'Post history tracking',
                'Topic rotation system'
            ],
            'statistics': {
                'total_posts': total_posts,
                'successful_posts': success_posts,
                'failed_posts': failed_posts,
                'success_rate': round((success_posts / total_posts * 100) if total_posts > 0 else 0, 2),
                'fanspages_count': fanspages_count,
                'first_post_date': first_post,
                'last_post': {
                    'timestamp': last_post['timestamp'] if last_post else None,
                    'page_name': last_post['page_name'] if last_post else None,
                    'status': last_post['status'] if last_post else None
                } if last_post else None
            },
            'system': {
                'uptime_seconds': int(uptime_seconds),
                'uptime_formatted': str(timedelta(seconds=int(uptime_seconds))),
                'disk_total_gb': round(total / (1024**3), 2),
                'disk_used_gb': round(used / (1024**3), 2),
                'disk_free_gb': round(free / (1024**3), 2),
                'disk_usage_percent': round((used / total) * 100, 2)
            },
            'schedule': {
                'interval': 'Every 3 hours',
                'times': ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00']
            },
            'endpoints': {
                'dashboard': '/dashboard',
                'api_stats': '/api/stats',
                'api_posts': '/api/posts',
                'api_config': '/api/config',
                'api_health': '/api/health'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/settings', methods=['POST'])
@require_pin
def update_settings():
    """Update settings (API key and image model)"""
    try:
        data = request.json
        
        config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        
        if 'gemini_api_key' in data and data['gemini_api_key']:
            api_key = data['gemini_api_key']
            # Validate API Key
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                # Just try to list models to verify key
                for _ in client.models.list(config={'page_size': 1}):
                    break
            except Exception as e:
                return jsonify({'success': False, 'error': f'Invalid Gemini API Key: {str(e)}'}), 400
            
            config['gemini_api_key'] = api_key
        
        if 'image_model' in data:
            config['image_model'] = data['image_model']
            
        if 'text_model' in data:
            config['text_model'] = data['text_model']
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analytics/insights')
@require_pin
def get_ai_insights():
    """Use Gemini to analyze which content patterns get highest engagement"""
    try:
        config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        api_key = config.get('gemini_api_key', '')
        if not api_key:
            return jsonify({'error': 'Gemini API key belum dikonfigurasi'}), 400

        days = int(request.args.get('days', 30))
        since = (datetime.now() - timedelta(days=days)).isoformat()

        conn = get_db()
        rows = conn.execute("""
            SELECT p.content, p.page_name, ec.likes, ec.comments, (ec.likes+ec.comments) as total
            FROM posts p
            JOIN engagement_cache ec ON ec.fb_post_id = p.fb_post_id
            WHERE p.status='success' AND p.timestamp >= ?
            ORDER BY total DESC
        """, (since,)).fetchall()
        conn.close()

        if len(rows) < 3:
            return jsonify({'error': 'Data engagement belum cukup. Coba refresh analitik dulu.'}), 400

        # Top 10 & bottom 10
        top = rows[:10]
        bottom = rows[-10:]

        def summarize(rows):
            return '\n\n'.join([
                f"[{r['page_name']} | ❤️{r['likes']} 💬{r['comments']}]\n{r['content'][:400]}..."
                for r in rows
            ])

        prompt = f"""Kamu adalah analis konten media sosial. Berikut data postingan Facebook dari akun edukasi emas/prospecting.

TOP 10 POSTINGAN (engagement tertinggi):
{summarize(top)}

BOTTOM 10 POSTINGAN (engagement terendah):
{summarize(bottom)}

Analisa pola konten dan berikan insight dalam format JSON berikut (HANYA output JSON, tanpa markdown):
{{
  "top_patterns": ["pola 1", "pola 2", "pola 3"],
  "avoid_patterns": ["pola 1", "pola 2"],
  "best_topics": ["topik 1", "topik 2", "topik 3"],
  "best_hook_style": "deskripsi gaya pembuka yang paling efektif",
  "best_cta_style": "deskripsi cta",
  "summary": "1-2 kalimat ringkasan sentimen audiens",
  "preferred_visual_styles": ["gaya visual/gambar yang cocok dengan topik viral", "gaya visual lain"],
  "prompt_improvement_suggestions": ["saran perbaikan prompt untuk AI image generator", "saran perbaikan prompt text"]
}}"""

        from google import genai as google_genai
        client = google_genai.Client(api_key=api_key)
        
        text_model = config.get('text_model', 'gemini-3.5-flash')
        
        response = client.models.generate_content(
            model=text_model,
            contents=prompt
        )
        text = response.text.strip()
        # Strip markdown code block if present
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        insights = json.loads(text)
        return jsonify({'success': True, 'insights': insights, 'analyzed': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/analytics/jit_report')
@require_pin
def get_jit_report():
    try:
        # Pakai CONFIG_PATH, bukan path relatif — path relatif ikut berubah
        # mengikuti working directory proses dan bisa gagal di luar /app
        config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        fanspages = config.get('fanspages', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        report = []
        for fp in fanspages:
            page_id = fp['page_id']
            # Ambil top 5 topics
            cursor.execute('''
                SELECT topic_keyword, boost_score, last_updated 
                FROM topic_preferences 
                WHERE page_id = ? 
                ORDER BY boost_score DESC 
                LIMIT 5
            ''', (page_id,))
            topics = [dict(row) for row in cursor.fetchall()]
            
            # Cari kapan terakhir diupdate
            last_updated = None
            if topics:
                # Ambil tanggal paling baru dari list topic yang didapat
                last_updated = max(t['last_updated'] for t in topics)
                
            report.append({
                'page_name': fp['name'],
                'page_id': page_id,
                'last_updated': last_updated,
                'topics': topics
            })
            
        conn.close()
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analytics/learning')
@require_pin
def get_learning_report():
    """Laporan pembelajaran: layout terbukti, keandalan editor AI, dan jam terbaik"""
    try:
        from learning_insights import full_report

        config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)

        return jsonify({'success': True, 'report': full_report(config.get('fanspages', []))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/schedule-insight')
@require_pin
def serve_schedule_insight():
    """Halaman rekomendasi jam posting per fanspage"""
    return render_template("schedule_insight.html")

@bp.route('/analytics')
@require_pin
def serve_analytics():
    return render_template("analytics.html")

@bp.route('/api/analyze-comments', methods=['POST'])
@require_pin
def analyze_comments():
    """Analisis komentar dari semua page dan simpan insight ke DB"""
    try:
        from comment_analyzer import CommentAnalyzer
        analyzer = CommentAnalyzer()

        results = []
        for page in analyzer.fanspages:
            page_name = page['name']
            page_id = page['page_id']
            access_token = page['access_token']

            comments = analyzer.get_recent_comments(page_id, access_token, days=3)
            silent_metrics = analyzer.get_silent_engagement_metrics(page_id, access_token, days=3)
            
            if len(comments) < 3 and not silent_metrics:
                results.append({'page': page_name, 'status': 'skipped', 'reason': f'Insufficient data'})
                continue

            analysis = analyzer.analyze_with_gemini(comments, page_name, silent_metrics=silent_metrics, page_id=page_id)
            if not analysis:
                results.append({'page': page_name, 'status': 'error', 'reason': 'Gemini analysis failed'})
                continue

            weight = 1 + int(len(comments) * 0.1) + int(len(silent_metrics or []) * 0.5)
            analyzer.save_insight(page_id, page_name, len(comments), analysis, weight=weight)
            results.append({
                'page': page_name,
                'status': 'success',
                'total_comments': len(comments),
                'sentiment': analysis.get('sentiment'),
                'top_keywords': analysis.get('top_keywords', []),
                'suggested_topics': analysis.get('suggested_topics', []),
                'preferred_visual_styles': analysis.get('preferred_visual_styles', []),
                'prompt_improvement_suggestions': analysis.get('prompt_improvement_suggestions', [])
            })

        analyzer.apply_time_decay()

        # Ambil top preferences terbaru
        top_prefs = analyzer.get_top_preferences(10)

        return jsonify({'success': True, 'results': results, 'top_preferences': top_prefs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/comment-insights')
@require_pin
def get_comment_insights():
    """Ambil insight komentar terbaru dari DB"""
    try:
        conn = get_db()
        rows = conn.execute(
            'SELECT * FROM comment_insights ORDER BY analyzed_at DESC LIMIT 5'
        ).fetchall()
        prefs = conn.execute(
            'SELECT topic_keyword, boost_score FROM topic_preferences ORDER BY boost_score DESC LIMIT 10'
        ).fetchall()
        conn.close()
        return jsonify({
            'insights': [dict(r) for r in rows],
            'top_preferences': [{'keyword': r['topic_keyword'], 'score': r['boost_score']} for r in prefs]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/export-insights-md')
@require_pin
def export_insights_md():
    """Export insights as Markdown file"""
    try:
        conn = get_db()
        rows = conn.execute(
            'SELECT * FROM comment_insights ORDER BY analyzed_at DESC LIMIT 10'
        ).fetchall()
        prefs = conn.execute(
            'SELECT topic_keyword, boost_score FROM topic_preferences ORDER BY boost_score DESC LIMIT 20'
        ).fetchall()
        conn.close()

        from flask import make_response
        import json

        content = "# 📊 GoldGen AI Analytics Report\n\n"
        content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        content += "## 📈 Top Audience Preferences\n"
        if not prefs:
            content += "No preferences data yet.\n\n"
        else:
            for p in prefs:
                content += f"- **{p['topic_keyword']}** (Score: {p['boost_score']})\n"
            content += "\n"

        content += "## 🤖 Recent AI Insights\n"
        if not rows:
            content += "No insights available yet.\n"
        else:
            for r in rows:
                content += f"### Page: {r['page_name']}\n"
                content += f"- **Analyzed At:** {r['analyzed_at']}\n"
                content += f"- **Total Comments Analyzed:** {r['total_comments_analyzed']}\n"
                content += f"- **Sentiment:** {r['sentiment'] if 'sentiment' in r.keys() else 'N/A'}\n"
                content += "- **Top Keywords:**\n"
                try:
                    kws = json.loads(r['top_keywords']) if r['top_keywords'] else []
                    for k in kws:
                        content += f"  - {k}\n"
                except:
                    content += f"  - {r['top_keywords']}\n"
                
                content += "- **Suggested Topics:**\n"
                try:
                    topics = json.loads(r['suggested_topics']) if r['suggested_topics'] else []
                    for t in topics:
                        content += f"  - {t}\n"
                except:
                    content += f"  - {r['suggested_topics']}\n"
                content += "\n---\n\n"

        response = make_response(content)
        response.headers["Content-Disposition"] = "attachment; filename=goldgen_insights.md"
        response.headers["Content-Type"] = "text/markdown; charset=utf-8"
        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/analytics')
@require_pin
def get_analytics():
    """Fetch engagement data — cached in DB, parallel fetch from Facebook API"""
    try:
        import urllib.request, urllib.error
        from concurrent.futures import ThreadPoolExecutor, as_completed

        config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)

        page_tokens = {p['page_id']: (p['name'], p.get('access_token', '')) for p in config.get('fanspages', [])}

        days = int(request.args.get('days', 7))
        since = (datetime.now() - timedelta(days=days)).isoformat()

        conn = get_db()

        # Tabel engagement_cache dibuat di core/database.init_db()
        posts = conn.execute(
            "SELECT id, fb_post_id, page_id, page_name, timestamp, layout_name FROM posts "
            "WHERE status='success' AND fb_post_id IS NOT NULL AND timestamp >= ? ORDER BY timestamp DESC",
            (since,)
        ).fetchall()

        # Split: cached vs needs fetch (cache valid 1 hour)
        cache_cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        cached = {
            row['fb_post_id']: row
            for row in conn.execute(
                "SELECT fb_post_id, likes, comments FROM engagement_cache WHERE cached_at >= ?",
                (cache_cutoff,)
            ).fetchall()
        }

        to_fetch = [p for p in posts if p['fb_post_id'] not in cached]

        def fetch_one(post):
            page_id = post['page_id']
            _, token = page_tokens.get(page_id, ('', ''))
            if not token:
                return None
            try:
                url = (f"https://graph.facebook.com/v21.0/{post['fb_post_id']}"
                       f"?fields=id,likes.summary(true),comments.summary(true)"
                       f"&access_token={token}")
                r = urllib.request.urlopen(url, timeout=8)
                d = json.loads(r.read())
                return {
                    'fb_post_id': post['fb_post_id'],
                    'likes': d.get('likes', {}).get('summary', {}).get('total_count', 0),
                    'comments': d.get('comments', {}).get('summary', {}).get('total_count', 0),
                }
            except Exception:
                return None

        # Parallel fetch for uncached posts (max 10 workers)
        if to_fetch:
            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = {ex.submit(fetch_one, p): p for p in to_fetch}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        conn.execute(
                            "INSERT OR REPLACE INTO engagement_cache (fb_post_id, likes, comments, cached_at) VALUES (?,?,?,?)",
                            (result['fb_post_id'], result['likes'], result['comments'], datetime.now().isoformat())
                        )
            conn.commit()
            # Reload cache
            cached = {
                row['fb_post_id']: row
                for row in conn.execute(
                    "SELECT fb_post_id, likes, comments FROM engagement_cache WHERE cached_at >= ?",
                    (cache_cutoff,)
                ).fetchall()
            }

        results = []
        for post in posts:
            c = cached.get(post['fb_post_id'])
            if not c:
                continue
            likes, comments = c['likes'], c['comments']
            results.append({
                'post_id': post['id'],
                'fb_post_id': post['fb_post_id'],
                'page_id': post['page_id'],
                'page_name': post['page_name'],
                'timestamp': post['timestamp'],
                'layout_name': post['layout_name'],
                'likes': likes,
                'comments': comments,
                'total_engagement': likes + comments,
            })

        conn.close()

        summary = {}
        for r in results:
            pid = r['page_id']
            if pid not in summary:
                summary[pid] = {'page_name': r['page_name'], 'total_likes': 0, 'total_comments': 0, 'post_count': 0}
            summary[pid]['total_likes'] += r['likes']
            summary[pid]['total_comments'] += r['comments']
            summary[pid]['post_count'] += 1

        for pid in summary:
            total = summary[pid]['total_likes'] + summary[pid]['total_comments']
            count = summary[pid]['post_count']
            summary[pid]['avg_engagement'] = round(total / count, 1) if count else 0

        # Layout summary
        layout_map = {}
        for r in results:
            ln = r['layout_name'] or 'Unknown'
            if ln not in layout_map:
                layout_map[ln] = {'total_likes': 0, 'total_comments': 0, 'post_count': 0}
            layout_map[ln]['total_likes'] += r['likes']
            layout_map[ln]['total_comments'] += r['comments']
            layout_map[ln]['post_count'] += 1
        layout_summary = []
        for ln, d in layout_map.items():
            total = d['total_likes'] + d['total_comments']
            layout_summary.append({
                'layout_name': ln,
                'post_count': d['post_count'],
                'total_likes': d['total_likes'],
                'total_comments': d['total_comments'],
                'avg_engagement': round(total / d['post_count'], 1) if d['post_count'] else 0
            })
        layout_summary.sort(key=lambda x: x['avg_engagement'], reverse=True)

        return jsonify({
            'posts': results,
            'summary': list(summary.values()),
            'layout_summary': layout_summary,
            'days': days,
            'total_fetched': len(results),
            'from_cache': len(results) - len(to_fetch),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')



