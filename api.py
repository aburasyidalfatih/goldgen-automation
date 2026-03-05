#!/usr/bin/env python3
"""
Web Dashboard for GoldGen Auto Poster
Simple Flask API to serve dashboard data
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "posts.db"
IMAGES_DIR = BASE_DIR / "generated_images"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check database
        cursor.execute("SELECT COUNT(*) as total FROM posts")
        total_posts = cursor.fetchone()['total']
        
        # Check last post
        cursor.execute("SELECT timestamp, page_name, status FROM posts ORDER BY id DESC LIMIT 1")
        last_post = cursor.fetchone()
        
        # Check disk space
        import shutil
        total, used, free = shutil.disk_usage('/')
        free_gb = free // (2**30)
        
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'total_posts': total_posts,
            'last_post': {
                'timestamp': last_post['timestamp'] if last_post else None,
                'fanspage': last_post['page_name'] if last_post else None,
                'status': last_post['status'] if last_post else None
            },
            'disk_space_gb': free_gb
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total posts
        cursor.execute("SELECT COUNT(*) as total FROM posts")
        total = cursor.fetchone()['total']
        
        # Success count
        cursor.execute("SELECT COUNT(*) as success FROM posts WHERE status='success'")
        success = cursor.fetchone()['success']
        
        # Failed count
        cursor.execute("SELECT COUNT(*) as failed FROM posts WHERE status='failed'")
        failed = cursor.fetchone()['failed']
        
        # Last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("SELECT COUNT(*) as last24h FROM posts WHERE timestamp > ?", (yesterday,))
        last_24h = cursor.fetchone()['last24h']
        
        # Success rate
        success_rate = (success / total * 100) if total > 0 else 0
        
        conn.close()
        
        return jsonify({
            'total': total,
            'success': success,
            'failed': failed,
            'last_24h': last_24h,
            'success_rate': round(success_rate, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/posts')
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
            posts.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'page_name': row['page_name'] if 'page_name' in row.keys() else None,
                'content': row['content'][:200] + '...' if len(row['content']) > 200 else row['content'],
                'image_path': Path(row['image_path']).name if row['image_path'] else None,
                'fb_post_id': row['fb_post_id'],
                'status': row['status'],
                'error_message': row['error_message']
            })
        
        conn.close()
        
        return jsonify({'posts': posts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/next-run')
def get_next_run():
    """Get next scheduled run time (cron runs every hour at :00)"""
    now = datetime.now()
    
    # Next hour at :00
    if now.minute == 0 and now.second < 5:
        # If we're at the start of the hour, next run is this hour
        next_run = now.replace(minute=0, second=0, microsecond=0)
    else:
        # Otherwise, next run is next hour
        if now.hour == 23:
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_run = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
    
    return jsonify({
        'next_run': next_run.isoformat(),
        'next_run_formatted': next_run.strftime('%Y-%m-%d %H:%M:%S') + ' WIB'
    })

@app.route('/api/topic-info')
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

@app.route('/api/images/<filename>')
def get_image(filename):
    """Serve generated images"""
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration (without sensitive data)"""
    try:
        if not CONFIG_PATH.exists():
            return jsonify({'configured': False, 'fanspages': [], 'fanspage_delay_minutes': 60})
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        fanspages = []
        for page in config.get('fanspages', []):
            fanspages.append({
                'name': page['name'],
                'page_id': page['page_id'],
                'interval_hours': page['interval_hours'],
                'enabled': page.get('enabled', True),
                'has_token': bool(page.get('access_token'))
            })
        
        return jsonify({
            'configured': True,
            'has_gemini_key': bool(config.get('gemini_api_key')),
            'fanspage_delay_minutes': config.get('fanspage_delay_minutes', 60),
            'fanspages': fanspages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
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

@app.route('/api/fanspages', methods=['POST'])
def add_fanspage():
    """Add new fanspage"""
    try:
        data = request.json
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        if 'fanspages' not in config:
            config['fanspages'] = []
        
        config['fanspages'].append({
            'name': data['name'],
            'page_id': data['page_id'],
            'access_token': data['access_token'],
            'interval_hours': int(data['interval_hours']),
            'enabled': True
        })
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fanspages/<page_id>', methods=['PUT'])
def update_fanspage(page_id):
    """Update fanspage"""
    try:
        data = request.json
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        for page in config['fanspages']:
            if page['page_id'] == page_id:
                if 'name' in data:
                    page['name'] = data['name']
                if 'interval_hours' in data:
                    page['interval_hours'] = int(data['interval_hours'])
                if 'enabled' in data:
                    page['enabled'] = data['enabled']
                if 'access_token' in data and data['access_token']:
                    page['access_token'] = data['access_token']
                break
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fanspages/<page_id>', methods=['DELETE'])
def delete_fanspage(page_id):
    """Delete fanspage"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        config['fanspages'] = [p for p in config['fanspages'] if p['page_id'] != page_id]
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/queue-post', methods=['POST'])
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
        
        # Queue for each page
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create queue table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS post_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                caption TEXT NOT NULL,
                image_path TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                posted_at TEXT
            )
        ''')
        
        # Add to queue
        for page_id in data['page_ids']:
            cursor.execute('''
                INSERT INTO post_queue (page_id, caption, image_path, created_at)
                VALUES (?, ?, ?, ?)
            ''', (page_id, data['caption'], str(image_path), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Queued for {len(data["page_ids"])} page(s)',
            'image_path': str(image_path)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/queue', methods=['GET'])
def get_queue():
    """Get pending posts in queue"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, page_id, caption, image_path, status, created_at
            FROM post_queue
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        
        queue = []
        for row in cursor.fetchall():
            queue.append({
                'id': row[0],
                'page_id': row[1],
                'caption': row[2][:100] + '...',
                'image_path': Path(row[3]).name,
                'status': row[4],
                'created_at': row[5]
            })
        
        conn.close()
        
        return jsonify({'queue': queue})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=18794, debug=False)
