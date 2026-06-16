#!/bin/bash
# Goldgen Automation Cleanup Script
# Runs daily to prevent disk space issues

LOG_DIR="/home/ubuntu/goldgen-automation/logs"
IMG_DIR="/home/ubuntu/goldgen-automation/generated_images"
DB_DIR="/home/ubuntu/goldgen-automation/data"

echo "[$(date)] Starting cleanup..."

# 1. Rotate logs older than 7 days
find "$LOG_DIR" -name "*.log" -type f -mtime +7 -exec gzip {} \;
echo "✓ Compressed logs older than 7 days"

# 2. Delete compressed logs older than 30 days
find "$LOG_DIR" -name "*.log.gz" -type f -mtime +30 -delete
echo "✓ Deleted compressed logs older than 30 days"

# 3. Delete images older than 7 days
find "$IMG_DIR" -name "*.png" -type f -mtime +7 -delete
echo "✓ Deleted images older than 7 days"

# 4. Vacuum database to reclaim space
sqlite3 "$DB_DIR/posts.db" "VACUUM;"
echo "✓ Database vacuumed"

# 5. Show current usage
echo "Current usage:"
du -sh "$LOG_DIR" "$IMG_DIR" "$DB_DIR"

echo "[$(date)] Cleanup completed"
