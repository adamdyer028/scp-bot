# SCP Bot - Quick Start Guide for SparkedHost

## 🚀 Super Quick Setup (5 minutes)

### 1. Upload Files to Server
```bash
# From your local machine
scp -r D:\scp-bot/* username@your-server-ip:~/scp-bot/
```

### 2. Run Deployment Script
```bash
# On your server
ssh username@your-server-ip
cd scp-bot
chmod +x deploy.sh
./deploy.sh
```

### 3. Configure Bot Token
```bash
# Switch to bot user
sudo su - scpbot
cd scp-bot
nano .env
# Add your Discord token: DISCORD_TOKEN=your_actual_token_here
```

### 4. Build Database
```bash
# Still as scpbot user
source venv/bin/activate
python scraper.py --full
```

### 5. Test Bot
```bash
python bot.py
# Press Ctrl+C after seeing "Bot has connected to Discord!"
```

### 6. Set Up Auto-Start
```bash
# Copy service file
sudo cp scp-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scp-bot
sudo systemctl start scp-bot
```

## ✅ Verify Everything Works

```bash
# Check bot status
sudo systemctl status scp-bot

# Check logs
sudo journalctl -u scp-bot -f

# Test in Discord
# Try: /library command
```

## 🔧 Common Commands

```bash
# Restart bot
sudo systemctl restart scp-bot

# Stop bot
sudo systemctl stop scp-bot

# Update library
cd ~/scp-bot && source venv/bin/activate && python scraper.py --update

# View logs
sudo journalctl -u scp-bot --since "1 hour ago"
```

## 🆘 Need Help?

- Check the full guide: `SPARKEDHOST_DEPLOYMENT.md`
- Check logs: `sudo journalctl -u scp-bot -f`
- Verify .env file has correct Discord token
- Make sure database exists: `ls -la ~/scp-bot/library_content.db`

## 📋 Checklist

- [ ] Files uploaded to server
- [ ] Deployment script run
- [ ] Discord token added to .env
- [ ] Database built with scraper
- [ ] Bot tested manually
- [ ] Systemd service installed and started
- [ ] Bot responds to Discord commands

**Your bot should now be running 24/7! 🎉**
