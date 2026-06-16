# PIN Authentication for Dashboard

**Date**: 2026-03-06
**Status**: ✅ Implemented

## Overview
Dashboard sekarang dilindungi dengan PIN authentication untuk keamanan.

## PIN Configuration
- **PIN**: `888888`
- **Location**: `api.py` line ~20
- **Session-based**: Login persists until logout or browser close

## How It Works

### 1. Login Flow
```
User visits https://gold.kelasmaster.id
  ↓
Redirected to /login
  ↓
Enter PIN: 888888
  ↓
Session created
  ↓
Redirected to /dashboard
```

### 2. Protected Endpoints
All API endpoints are now protected:
- `/` → Redirects to /login or /dashboard
- `/dashboard` → Requires authentication
- `/api/stats` → Requires authentication
- `/api/posts` → Requires authentication
- `/api/next-run` → Requires authentication
- `/api/topic-info` → Requires authentication

### 3. Public Endpoints
- `/login` → Login page
- `/api/auth/login` → Login API
- `/api/auth/logout` → Logout API
- `/api/auth/check` → Check auth status
- `/api/health` → Health check (public)

## Usage

### Access Dashboard
1. Visit: https://gold.kelasmaster.id
2. Enter PIN: `888888`
3. Click "Login"
4. Dashboard will load

### Logout
Click the "🔒 Logout" button in the top-right corner of dashboard.

### Change PIN
Edit `api.py`:
```python
# Line ~20
DASHBOARD_PIN = "888888"  # Change this
```

Then restart service:
```bash
cd /home/ubuntu/goldgen-automation
ps aux | grep api.py | grep -v grep | awk '{print $2}' | xargs kill
nohup ./venv/bin/python3 api.py > dashboard_web.log 2>&1 &
```

## Security Features

1. **Session-based authentication**
   - Uses Flask sessions with secret key
   - Session expires on browser close

2. **Password input**
   - PIN field is type="password" (hidden)
   - Auto-focus for quick entry

3. **API protection**
   - All sensitive endpoints require authentication
   - Returns 401 Unauthorized if not authenticated

4. **Auto-redirect**
   - Unauthenticated users redirected to login
   - Authenticated users redirected to dashboard

## Files Modified

1. **api.py**
   - Added session management
   - Added `require_pin` decorator
   - Added auth endpoints
   - Protected all sensitive routes

2. **login.html** (new)
   - Simple login page
   - PIN input form
   - Error handling

3. **dashboard_schedule.html**
   - Added logout button
   - Added auth check on load
   - Auto-redirect if not authenticated

## Testing

### Test Login API
```bash
# Correct PIN
curl -X POST http://localhost:18794/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin":"888888"}'

# Wrong PIN
curl -X POST http://localhost:18794/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin":"123456"}'
```

### Test Protected Endpoint
```bash
# Without auth (should return 401)
curl http://localhost:18794/api/stats

# With auth (need session cookie)
curl -c cookies.txt -X POST http://localhost:18794/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"pin":"888888"}'
  
curl -b cookies.txt http://localhost:18794/api/stats
```

## Notes

- PIN is stored in plain text in code (for simplicity)
- For production, consider using environment variables
- Session secret key should be changed for production
- Consider adding rate limiting for login attempts
- Consider adding 2FA for enhanced security

## Troubleshooting

### Can't access dashboard
1. Check if service is running: `netstat -tlnp | grep 18794`
2. Check logs: `tail -f ~/goldgen-automation/dashboard_web.log`
3. Try clearing browser cookies
4. Verify PIN is correct: `888888`

### Session expires too quickly
Flask sessions expire when browser closes. This is by design for security.

### Forgot PIN
PIN is hardcoded in `api.py` line ~20. Check the file or ask admin.
