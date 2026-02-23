#!/bin/bash
# Setup Cron Job for GoldGen Auto Poster
# This script will configure automatic posting every hour

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CRON_CMD="0 * * * * cd $SCRIPT_DIR && ./run.sh >> logs/cron.log 2>&1"

echo "=========================================="
echo "🔧 SETUP CRON JOB - GoldGen Auto Poster"
echo "=========================================="
echo ""
echo "Script akan menambahkan cron job untuk:"
echo "  - Jalankan auto_poster.py setiap jam"
echo "  - Log output ke logs/cron.log"
echo ""
echo "Cron command:"
echo "  $CRON_CMD"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "goldgen-automation"; then
    echo "⚠️  Cron job sudah ada!"
    echo ""
    echo "Cron jobs saat ini:"
    crontab -l | grep goldgen
    echo ""
    read -p "Hapus dan buat ulang? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup dibatalkan"
        exit 0
    fi
    
    # Remove old cron job
    crontab -l | grep -v "goldgen-automation" | crontab -
    echo "✅ Cron job lama dihapus"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo ""
echo "✅ Cron job berhasil ditambahkan!"
echo ""
echo "📋 Cron jobs aktif:"
crontab -l | grep goldgen
echo ""
echo "📊 Monitoring:"
echo "  - Lihat log: tail -f $SCRIPT_DIR/logs/cron.log"
echo "  - Lihat cron: crontab -l"
echo "  - Hapus cron: crontab -e (lalu hapus baris goldgen)"
echo ""
echo "🚀 Auto-posting akan berjalan setiap jam!"
echo "=========================================="
