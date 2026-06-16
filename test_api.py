import os
import sys
from api import app
from flask import session

with app.test_request_context('/api/stats'):
    session['authenticated'] = True
    try:
        response = app.full_dispatch_request()
        print("Stats Status:", response.status_code)
        print("Stats Data:", response.get_data(as_text=True))
    except Exception as e:
        print("Stats Exception:", e)

with app.test_request_context('/api/posts'):
    session['authenticated'] = True
    try:
        response = app.full_dispatch_request()
        print("Posts Status:", response.status_code)
        print("Posts Data:", response.get_data(as_text=True))
    except Exception as e:
        print("Posts Exception:", e)
