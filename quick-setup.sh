#!/bin/bash
# Quick setup script for GoldGen Auto Poster

echo "==================================="
echo "GoldGen Auto Poster - Quick Setup"
echo "==================================="
echo ""

cd /home/ubuntu/goldgen-automation

# Check if already configured
if [ -f "data/config.json" ]; then
    echo "⚠️  Configuration already exists!"
    echo ""
    read -p "Do you want to reconfigure? (y/n): " reconfigure
    if [ "$reconfigure" != "y" ]; then
        echo "Setup cancelled."
        exit 0
    fi
fi

echo "📋 You will need:"
echo "1. Facebook Page ID"
echo "2. Facebook Page Access Token"
echo ""
echo "To get Facebook credentials:"
echo "1. Go to: https://developers.facebook.com/tools/explorer/"
echo "2. Select your Page"
echo "3. Generate token with 'pages_manage_posts' permission"
echo ""
read -p "Press Enter to continue..."

# Run setup
source venv/bin/activate
python3 setup.py

echo ""
echo "==================================="
echo "Testing the configuration..."
echo "==================================="
echo ""

# Test run
python3 auto_poster.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup completed successfully!"
    echo ""
    echo "📅 Automation Schedule:"
    echo "   Posts will be created every 3 hours:"
    echo "   00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00"
    echo ""
    echo "📊 Monitor logs:"
    echo "   tail -f logs/auto_poster.log"
    echo ""
    echo "🔧 Manage cron:"
    echo "   crontab -e"
else
    echo ""
    echo "❌ Setup failed. Please check the error messages above."
    echo ""
    echo "Common issues:"
    echo "- Invalid Facebook token"
    echo "- Wrong Page ID"
    echo "- Missing permissions"
fi
