#!/bin/bash
# Wrapper script to run auto_poster.py with virtual environment

cd /home/ubuntu/goldgen-automation
source venv/bin/activate
python3 auto_poster.py >> logs/auto_poster.log 2>&1
