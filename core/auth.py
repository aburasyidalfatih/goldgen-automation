import os
from pathlib import Path

# core/auth.py
from functools import wraps
from flask import session, jsonify

def require_pin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized', 'require_auth': True}), 401
        return f(*args, **kwargs)
    return decorated_function
