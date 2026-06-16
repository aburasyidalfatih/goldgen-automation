#!/bin/bash
# Start Goldgen Automation Dashboard
# Usage: ./start.sh

cd /home/ubuntu/goldgen-automation

# Kill existing process
pkill -f "goldgen.*api.py"
sleep 2

# Start API
nohup ./venv/bin/python3 api.py > api.log 2>&1 &

sleep 3

# Check status
if netstat -tlnp 2>/dev/null | grep -q 18794; then
    echo "✅ Goldgen Dashboard started successfully on port 18794"
    echo "🌐 Access: https://gold.kelasmaster.id"
else
    echo "❌ Failed to start Goldgen Dashboard"
    echo "Check logs: tail -f api.log"
    exit 1
fi
