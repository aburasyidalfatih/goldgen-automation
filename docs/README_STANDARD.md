# goldgen-automation - Quick Reference

**Last Updated:** 2026-03-11 06:04

---

## 📊 Bot Information

- **Directory:** `/home/ubuntu/goldgen-automation`
- **Port:** 18794
- **Supervisor:** No
- **Cron Jobs:** Yes

---

## 🚀 Quick Commands

### Start/Stop/Restart
```bash
# Using bot-manager
/home/ubuntu/bot-manager.sh start goldgen-automation
/home/ubuntu/bot-manager.sh stop goldgen-automation
/home/ubuntu/bot-manager.sh restart goldgen-automation

# Using supervisor directly
sudo supervisorctl start goldgen-automation
sudo supervisorctl stop goldgen-automation
sudo supervisorctl restart goldgen-automation
```

### Check Status
```bash
/home/ubuntu/bot-manager.sh status goldgen-automation
sudo supervisorctl status goldgen-automation
```

### View Logs
```bash
/home/ubuntu/bot-manager.sh logs goldgen-automation

# Or directly
tail -f /home/ubuntu/goldgen-automation/logs/*.log
```

---

## 📁 Directory Structure

```
/home/ubuntu/goldgen-automation/
├── venv/                    # Virtual environment
├── data/                    # Database & config
├── logs/                    # All logs
├── *.py                     # Python files
├── requirements.txt         # Dependencies
└── README.md               # Original documentation
```

---

## 🔧 Maintenance

### Update Dependencies
```bash
cd /home/ubuntu/goldgen-automation
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### Check Health
```bash
/home/ubuntu/bot-manager.sh health
```

### Backup
```bash
# Backup database
cp -r /home/ubuntu/goldgen-automation/data /home/ubuntu/goldgen-automation/data.backup.$(date +%Y%m%d)

# Backup config
cp /home/ubuntu/goldgen-automation/data/config.json /home/ubuntu/goldgen-automation/data/config.json.backup
```

---

## 📝 Logs Location

- **Application Logs:** `/home/ubuntu/goldgen-automation/logs/`
- **Supervisor Logs:** `/home/ubuntu/goldgen-automation/supervisor.*.log`
- **Cron Logs:** Check crontab entries

---

## ⚠️ Troubleshooting

### Bot Not Starting
1. Check supervisor status
2. Check logs for errors
3. Verify port not in use
4. Check database connection

### Port Already in Use
```bash
# Find process using port
netstat -tlnp | grep 18794

# Kill process if needed
kill -9 <PID>
```

---

**For detailed documentation, see original README.md**
