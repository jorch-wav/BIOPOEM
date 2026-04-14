#!/usr/bin/env python3
"""
BioPoem Gallery Backend - Feedback Collection API
Replaces localStorage with centralized SQLite database
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import subprocess
import json

app = Flask(__name__)
CORS(app)  # Allow requests from gallery frontend

DB_PATH = 'gallery_feedback.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ratings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            poem_id TEXT PRIMARY KEY,
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Comments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poem_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User ratings tracking (prevent double voting)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_ratings (
            user_id TEXT NOT NULL,
            poem_id TEXT NOT NULL,
            rating_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            PRIMARY KEY (user_id, poem_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[DEBUG] Database initialized at {DB_PATH}")

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/feedback/<poem_id>', methods=['GET'])
def get_feedback(poem_id):
    """Get all feedback for a poem"""
    conn = get_db()
    
    # Get ratings
    ratings_row = conn.execute(
        'SELECT likes, dislikes FROM ratings WHERE poem_id = ?',
        (poem_id,)
    ).fetchone()
    
    likes = ratings_row['likes'] if ratings_row else 0
    dislikes = ratings_row['dislikes'] if ratings_row else 0
    
    # Get comments
    comments_rows = conn.execute(
        'SELECT text, timestamp, user_id FROM comments WHERE poem_id = ? ORDER BY timestamp DESC',
        (poem_id,)
    ).fetchall()
    
    comments = [dict(row) for row in comments_rows]
    
    conn.close()
    
    return jsonify({
        'likes': likes,
        'dislikes': dislikes,
        'comments': comments
    })

@app.route('/api/rate/<poem_id>', methods=['POST'])
def rate_poem(poem_id):
    """
    Add or update a rating for a poem
    Expected JSON: {'type': 'like' or 'dislike', 'userId': 'user_xxx'}
    """
    data = request.json
    rating_type = data.get('type')  # 'like' or 'dislike'
    user_id = data.get('userId')
    
    if not rating_type or rating_type not in ['like', 'dislike']:
        return jsonify({'error': 'Invalid rating type'}), 400
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if user has already rated this poem
        existing = cursor.execute(
            'SELECT rating_type FROM user_ratings WHERE user_id = ? AND poem_id = ?',
            (user_id, poem_id)
        ).fetchone()
        
        if existing:
            old_type = existing['rating_type']
            
            # User is changing their rating or un-rating
            if old_type == rating_type:
                # Un-rating (remove vote)
                cursor.execute(
                    'DELETE FROM user_ratings WHERE user_id = ? AND poem_id = ?',
                    (user_id, poem_id)
                )
                cursor.execute(
                    f'UPDATE ratings SET {rating_type}s = {rating_type}s - 1, updated_at = ? WHERE poem_id = ?',
                    (datetime.now().isoformat(), poem_id)
                )
            else:
                # Changing vote (decrease old, increase new)
                cursor.execute(
                    f'UPDATE ratings SET {old_type}s = {old_type}s - 1, {rating_type}s = {rating_type}s + 1, updated_at = ? WHERE poem_id = ?',
                    (datetime.now().isoformat(), poem_id)
                )
                cursor.execute(
                    'UPDATE user_ratings SET rating_type = ?, timestamp = ? WHERE user_id = ? AND poem_id = ?',
                    (rating_type, datetime.now().isoformat(), user_id, poem_id)
                )
        else:
            # New rating
            # Ensure poem exists in ratings table
            cursor.execute(
                'INSERT OR IGNORE INTO ratings (poem_id, likes, dislikes) VALUES (?, 0, 0)',
                (poem_id,)
            )
            
            # Add rating
            cursor.execute(
                f'UPDATE ratings SET {rating_type}s = {rating_type}s + 1, updated_at = ? WHERE poem_id = ?',
                (datetime.now().isoformat(), poem_id)
            )
            
            # Track user vote
            cursor.execute(
                'INSERT INTO user_ratings (user_id, poem_id, rating_type, timestamp) VALUES (?, ?, ?, ?)',
                (user_id, poem_id, rating_type, datetime.now().isoformat())
            )
        
        conn.commit()
        
        # Return updated counts
        result = cursor.execute(
            'SELECT likes, dislikes FROM ratings WHERE poem_id = ?',
            (poem_id,)
        ).fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'likes': result['likes'] if result else 0,
            'dislikes': result['dislikes'] if result else 0
        })
    
    except Exception as e:
        conn.close()
        print(f"[ERROR] Rating failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/comment/<poem_id>', methods=['POST'])
def add_comment(poem_id):
    """
    Add a comment to a poem
    Expected JSON: {'text': 'comment text', 'userId': 'user_xxx'}
    """
    data = request.json
    comment_text = data.get('text', '').strip()
    user_id = data.get('userId')
    
    if not comment_text:
        return jsonify({'error': 'Comment text required'}), 400
    
    if len(comment_text) > 280:
        return jsonify({'error': 'Comment too long (max 280 characters)'}), 400
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        timestamp = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO comments (poem_id, user_id, text, timestamp) VALUES (?, ?, ?, ?)',
            (poem_id, user_id, comment_text, timestamp)
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'comment': {
                'text': comment_text,
                'timestamp': timestamp,
                'userId': user_id
            }
        })
    
    except Exception as e:
        conn.close()
        print(f"[ERROR] Comment failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-rating/<user_id>/<poem_id>', methods=['GET'])
def get_user_rating(user_id, poem_id):
    """Get a specific user's rating for a poem"""
    conn = get_db()
    
    result = conn.execute(
        'SELECT rating_type FROM user_ratings WHERE user_id = ? AND poem_id = ?',
        (user_id, poem_id)
    ).fetchone()
    
    conn.close()
    
    if result:
        return jsonify({'rating': result['rating_type']})
    else:
        return jsonify({'rating': None})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    conn = get_db()
    
    total_ratings = conn.execute(
        'SELECT SUM(likes + dislikes) as total FROM ratings'
    ).fetchone()
    
    total_comments = conn.execute(
        'SELECT COUNT(*) as total FROM comments'
    ).fetchone()
    
    unique_users = conn.execute(
        'SELECT COUNT(DISTINCT user_id) as total FROM user_ratings'
    ).fetchone()
    
    conn.close()
    
    return jsonify({
        'total_ratings': total_ratings['total'] or 0,
        'total_comments': total_comments['total'] or 0,
        'unique_users': unique_users['total'] or 0
    })

@app.route('/api/analyze-feedback', methods=['POST'])
def trigger_analysis():
    """
    Manually trigger feedback analysis
    Runs analyze_feedback.py and returns results including handoff report
    """
    try:
        # Run analysis script
        result = subprocess.run(
            ['python3', '/home/biopoem/analyze_feedback.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if analysis file was created/updated
        analysis_path = '/home/biopoem/feedback_analysis.json'
        if not os.path.exists(analysis_path):
            return jsonify({
                'success': False,
                'error': 'Analysis file not created. Check if analyze_feedback.py ran successfully.'
            }), 500
        
        # Read the generated analysis
        with open(analysis_path, 'r') as f:
            analysis = json.load(f)
        
        # Find the most recent handoff report
        handoff_report_path = None
        handoff_report_content = None
        
        memory_session_dir = '/home/biopoem/.vscode-server/data/User/globalStorage/github.copilot-chat/memories/session'
        if os.path.exists(memory_session_dir):
            # Find most recent feedback-handoff-*.md file
            report_files = [f for f in os.listdir(memory_session_dir) if f.startswith('feedback-handoff-') and f.endswith('.md')]
            if report_files:
                # Sort by filename (which includes timestamp) and get most recent
                report_files.sort(reverse=True)
                handoff_report_path = os.path.join(memory_session_dir, report_files[0])
                
                # Read report content
                with open(handoff_report_path, 'r') as f:
                    handoff_report_content = f.read()
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'handoff_report': handoff_report_content,
            'handoff_report_path': handoff_report_path,
            'output': result.stdout
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Analysis timed out (>30 seconds)'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export-csv', methods=['GET'])
def export_csv():
    """
    Export all poems with sensor data and ratings as CSV
    Combines poem_generations.csv with ratings from database
    """
    try:
        import csv
        from io import StringIO
        
        # Read poem_generations.csv
        csv_path = '/home/biopoem/poem_generations.csv'
        if not os.path.exists(csv_path):
            return jsonify({
                'success': False,
                'error': 'poem_generations.csv not found'
            }), 404
        
        # Get all ratings from database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT poem_id, likes, dislikes FROM ratings')
        ratings_dict = {row['poem_id']: {'likes': row['likes'], 'dislikes': row['dislikes']} 
                       for row in cursor.fetchall()}
        
        # Get all comments from database
        cursor.execute('SELECT poem_id, GROUP_CONCAT(text, " | ") as comments FROM comments GROUP BY poem_id')
        comments_dict = {row['poem_id']: row['comments'] for row in cursor.fetchall()}
        conn.close()
        
        # Read original CSV and add rating columns
        output = StringIO()
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames + ['likes', 'dislikes', 'comments']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                # Generate poem_id matching the format used in database
                # Format: YYYY-MM-DDTHH:MM:SS_title_slug
                import re
                timestamp = row.get('timestamp', '')[:19]  # Truncate to seconds
                title = row.get('poem_title', '')
                title_slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
                poem_id = f"{timestamp}_{title_slug}"
                
                # Add ratings
                ratings = ratings_dict.get(poem_id, {'likes': 0, 'dislikes': 0})
                row['likes'] = ratings['likes']
                row['dislikes'] = ratings['dislikes']
                row['comments'] = comments_dict.get(poem_id, '')
                
                writer.writerow(row)
        
        # Return CSV as downloadable file
        from flask import Response
        csv_data = output.getvalue()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'biopoem_complete_export_{timestamp}.csv'
        
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("=" * 60)
    print("BioPoem Gallery Backend")
    print("=" * 60)
    
    # Initialize database if it doesn't exist
    if not os.path.exists(DB_PATH):
        print(f"Creating database at {DB_PATH}...")
        init_db()
    else:
        print(f"Using existing database at {DB_PATH}")
    
    print("\nStarting Flask server...")
    print("API endpoints:")
    print("  GET  /api/health")
    print("  GET  /api/feedback/<poem_id>")
    print("  POST /api/rate/<poem_id>")
    print("  POST /api/comment/<poem_id>")
    print("  GET  /api/user-rating/<user_id>/<poem_id>")
    print("  GET  /api/stats")
    print("  POST /api/analyze-feedback  [Admin: Trigger AI feedback analysis]")
    print("  GET  /api/export-csv  [Export all poems + sensor data + ratings as CSV]")
    print("\nListening on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
