import os
import sys
from api import app
from flask import session

with app.test_request_context('/api/analytics?days=7'):
    session['authenticated'] = True
    try:
        response = app.full_dispatch_request()
        print("Analytics Status:", response.status_code)
        print("Analytics Data:", response.get_data(as_text=True)[:200])
    except Exception as e:
        print("Exception:", e)
