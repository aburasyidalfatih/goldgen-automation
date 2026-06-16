# ✅ AUTO REPLY CRON - SETUP COMPLETE!

## 🎉 Status: ACTIVE & RUNNING

Auto reply comments sudah aktif dan berjalan otomatis setiap 15 menit!

---

## ⏰ Cron Schedule:

```bash
*/15 * * * * cd /home/ubuntu/goldgen-automation && venv/bin/python auto_reply_comments.py >> logs/auto_reply.log 2>&1
```

**Artinya:**
- ✅ Berjalan setiap 15 menit
- ✅ 24/7 non-stop
- ✅ Auto reply semua komentar baru
- ✅ Log tersimpan di `logs/auto_reply.log`

---

## 📊 Execution Schedule:

Bot akan berjalan pada:
```
00:00, 00:15, 00:30, 00:45
01:00, 01:15, 01:30, 01:45
02:00, 02:15, 02:30, 02:45
...
23:00, 23:15, 23:30, 23:45
```

**96 kali per hari!**

---

## 🎯 What It Does:

Setiap 15 menit, bot akan:

1. ✅ Check 5 postingan terbaru di **Putri Kejora**
2. ✅ Check 5 postingan terbaru di **Erna Gold**
3. ✅ Check 5 postingan terbaru di **Gold USD**
4. ✅ Check 5 postingan terbaru di **Kedai Digital**
5. ✅ Check 5 postingan terbaru di **Miners 24**
6. ✅ Scan semua komentar (max 100 per post)
7. ✅ Reply komentar baru dengan Gemini AI
8. ✅ Skip komentar yang sudah dibalas
9. ✅ Save ke database

**Total: 25 posts checked, up to 2,500 comments scanned!**

---

## 📝 Monitoring:

### View Real-time Logs:
```bash
tail -f /home/ubuntu/goldgen-automation/logs/auto_reply.log
```

### View Last 50 Lines:
```bash
tail -50 /home/ubuntu/goldgen-automation/logs/auto_reply.log
```

### Check Cron Status:
```bash
crontab -l | grep auto_reply
```

### View Replied Comments:
```bash
cd /home/ubuntu/goldgen-automation
sqlite3 data/posts.db "SELECT COUNT(*) FROM replied_comments;"
```

### View Recent Replies:
```bash
sqlite3 data/posts.db "SELECT user_name, comment_text, reply_text, timestamp FROM replied_comments ORDER BY timestamp DESC LIMIT 10;"
```

---

## 🔧 Management Commands:

### Stop Auto Reply:
```bash
crontab -e
# Comment out the line with #
# */15 * * * * cd /home/ubuntu/goldgen-automation...
```

### Start Auto Reply:
```bash
crontab -e
# Uncomment the line (remove #)
*/15 * * * * cd /home/ubuntu/goldgen-automation...
```

### Change Schedule:

**Every 10 minutes (faster):**
```bash
crontab -e
# Change to:
*/10 * * * * cd /home/ubuntu/goldgen-automation && venv/bin/python auto_reply_comments.py >> logs/auto_reply.log 2>&1
```

**Every 30 minutes (slower):**
```bash
crontab -e
# Change to:
*/30 * * * * cd /home/ubuntu/goldgen-automation && venv/bin/python auto_reply_comments.py >> logs/auto_reply.log 2>&1
```

### Manual Run (Test):
```bash
cd /home/ubuntu/goldgen-automation
venv/bin/python auto_reply_comments.py
```

---

## 📊 Expected Performance:

### Response Time:
- **Max**: 15 minutes
- **Average**: 7-8 minutes
- **Min**: < 1 minute (if just ran)

### Coverage:
- **Fanspages**: 5 fanspages
- **Posts per fanspage**: 5 posts
- **Total posts checked**: 25 posts
- **Comments per post**: Up to 100
- **Total comments scanned**: Up to 2,500

### Efficiency:
- **Processing time**: ~20-30 seconds per run
- **API calls**: Minimal (smart caching)
- **Database**: Auto-tracked (no duplicates)

---

## ✅ Features Active:

- ✅ **Multi-fanspage** - All 5 fanspages covered
- ✅ **Multi-language** - Auto-detect & reply in same language
- ✅ **Educational** - Focus on education & discussion
- ✅ **Smart tracking** - No double replies
- ✅ **Gemini AI** - Contextual & natural replies
- ✅ **24/7 automation** - Always active
- ✅ **Old posts** - Check comments on old posts too

---

## 🎉 Success Metrics:

After 24 hours, you should see:
- ✅ 96 executions
- ✅ All new comments replied
- ✅ Increased engagement
- ✅ More discussions
- ✅ Better community

---

## 📈 Next Steps:

1. **Monitor logs** - Check if replies are good
2. **Adjust prompt** - Fine-tune if needed
3. **Track engagement** - Measure impact
4. **Optimize schedule** - Change to 10 min if needed

---

## 🚨 Troubleshooting:

### If not working:

**Check cron:**
```bash
crontab -l | grep auto_reply
```

**Check logs:**
```bash
tail -50 /home/ubuntu/goldgen-automation/logs/auto_reply.log
```

**Test manual:**
```bash
cd /home/ubuntu/goldgen-automation
venv/bin/python auto_reply_comments.py
```

**Check permissions:**
```bash
ls -la /home/ubuntu/goldgen-automation/auto_reply_comments.py
chmod +x /home/ubuntu/goldgen-automation/auto_reply_comments.py
```

---

## ✅ SETUP COMPLETE!

**Status:** 🟢 ACTIVE
**Schedule:** Every 15 minutes
**Fanspages:** 5 fanspages
**Response Time:** Max 15 minutes
**Features:** All enabled

**Bot is now running 24/7 and will auto-reply to all comments!** 🎉🤖

---

**Setup Date:** 2026-03-06 17:38
**Next Run:** Within 15 minutes
**Logs:** `/home/ubuntu/goldgen-automation/logs/auto_reply.log`
