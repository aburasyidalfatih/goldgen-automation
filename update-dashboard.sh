#!/bin/bash
# Update dashboard to production

echo "Updating dashboard..."
cp /home/ubuntu/goldgen-automation/dashboard.html /home/ubuntu/GoldGen-Poster-AI/dist/
sudo systemctl restart goldgen
echo "✅ Dashboard updated!"
