# SCP Bot - SparkedHost Deployment Guide

This guide will walk you through deploying your SCP (Sacred Community Project) Discord bot on SparkedHost.

## Overview

Your bot includes:
- Discord bot with slash commands for library browsing
- SQLite database for storing scraped content
- Web scraper for Sacred Community Project digital library
- Interactive Discord UI with dropdowns and search functionality

## Prerequisites

1. **SparkedHost VPS/Server** - Any plan that supports Python 3.8+
2. **Discord Bot Token** - From Discord Developer Portal
3. **Domain name** (optional) - For easier access to your server

## Step 1: Server Setup

### 1.1 Connect to Your Server

```bash
ssh root@your-server-ip
# or
ssh username@your-server-ip
```

### 1.2 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install Python and Dependencies

```bash
# Install Python 3.8+ and pip
sudo apt install python3 python3-pip python3-venv git -y

# Verify Python version
python3 --version
```

### 1.4 Create Application User (Recommended)

```bash
# Create a dedicated user for the bot
sudo useradd -m -s /bin/bash scpbot
sudo usermod -aG sudo scpbot

# Switch to the bot user
sudo su - scpbot
```

## Step 2: Upload Your Bot Files

### 2.1 Option A: Using Git (Recommended)

```bash
# Clone your repository (if it's on GitHub/GitLab)
git clone https://github.com/yourusername/scp-bot.git
cd scp-bot

# Or create the directory and upload files manually
mkdir ~/scp-bot
cd ~/scp-bot
```

### 2.2 Option B: Upload via SCP/SFTP

From your local machine:
```bash
scp -r D:\scp-bot/* username@your-server-ip:~/scp-bot/
```

### 2.3 Verify Files

```bash
ls -la ~/scp-bot/
# Should show: bot.py, config.py, requirements.txt, scraper.py, etc.
```

## Step 3: Environment Setup

### 3.1 Create Virtual Environment

```bash
cd ~/scp-bot
python3 -m venv venv
source venv/bin/activate
```

### 3.2 Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 Create Environment File

```bash
nano .env
```

Add your Discord bot token:
```env
DISCORD_TOKEN=your_actual_discord_bot_token_here
```

**Important:** Replace `your_actual_discord_bot_token_here` with your real bot token from Discord Developer Portal.

## Step 4: Initial Database Setup

### 4.1 Run Initial Scraper

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Run the scraper to build your initial database
python scraper.py --full
```

This will take some time (10-30 minutes depending on library size). The scraper will:
- Download the sitemap
- Filter for actual articles
- Extract metadata from each page
- Build the SQLite database

### 4.2 Verify Database

```bash
# Check if database was created
ls -la library_content.db

# Test the bot briefly
python bot.py
# Press Ctrl+C to stop after seeing "Bot has connected to Discord!"
```

## Step 5: Create Service for Auto-Start

### 5.1 Create Systemd Service File

```bash
sudo nano /etc/systemd/system/scp-bot.service
```

Add this content:

```ini
[Unit]
Description=SCP Discord Bot
After=network.target

[Service]
Type=simple
User=scpbot
WorkingDirectory=/home/scpbot/scp-bot
Environment=PATH=/home/scpbot/scp-bot/venv/bin
ExecStart=/home/scpbot/scp-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=scp-bot

[Install]
WantedBy=multi-user.target
```

**Note:** Adjust paths if your setup is different.

### 5.2 Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable scp-bot

# Start the service
sudo systemctl start scp-bot

# Check status
sudo systemctl status scp-bot
```

### 5.3 Monitor Logs

```bash
# View real-time logs
sudo journalctl -u scp-bot -f

# View recent logs
sudo journalctl -u scp-bot --since "1 hour ago"
```

## Step 6: Setup Auto-Updates

### 6.1 Create Update Script

```bash
nano ~/scp-bot/update_library.sh
```

Add this content:

```bash
#!/bin/bash
cd /home/scpbot/scp-bot
source venv/bin/activate

# Run incremental update
python scraper.py --update

# Restart bot if it's running
sudo systemctl restart scp-bot
```

Make it executable:
```bash
chmod +x ~/scp-bot/update_library.sh
```

### 6.2 Setup Cron Job

```bash
crontab -e
```

Add this line to run updates daily at 2 AM:
```cron
0 2 * * * /home/scpbot/scp-bot/update_library.sh >> /home/scpbot/scp-bot/update.log 2>&1
```

## Step 7: Firewall and Security

### 7.1 Configure Firewall

```bash
# Allow SSH (if not already allowed)
sudo ufw allow ssh

# Allow any ports your bot might need
sudo ufw enable

# Check status
sudo ufw status
```

### 7.2 Secure Environment File

```bash
# Make .env file readable only by owner
chmod 600 ~/scp-bot/.env
```

## Step 8: Testing and Verification

### 8.1 Test Bot Commands

In Discord, try these commands:
- `/library` - Should open the interactive library browser
- `/library-stats` - Should show database statistics (admin only)

### 8.2 Test Auto-Restart

```bash
# Simulate a crash
sudo systemctl stop scp-bot
sudo systemctl start scp-bot

# Check if it's running
sudo systemctl status scp-bot
```

### 8.3 Test Updates

```bash
# Run manual update
~/scp-bot/update_library.sh

# Check logs
tail -f ~/scp-bot/update.log
```

## Step 9: Monitoring and Maintenance

### 9.1 Health Check Script

Create a simple health check:

```bash
nano ~/scp-bot/health_check.sh
```

```bash
#!/bin/bash
# Check if bot is running
if systemctl is-active --quiet scp-bot; then
    echo "✅ Bot is running"
else
    echo "❌ Bot is not running - restarting"
    sudo systemctl restart scp-bot
fi

# Check database size
DB_SIZE=$(du -h ~/scp-bot/library_content.db | cut -f1)
echo "📊 Database size: $DB_SIZE"

# Check recent logs for errors
ERROR_COUNT=$(journalctl -u scp-bot --since "1 hour ago" | grep -i error | wc -l)
echo "⚠️  Errors in last hour: $ERROR_COUNT"
```

Make it executable:
```bash
chmod +x ~/scp-bot/health_check.sh
```

### 9.2 Regular Maintenance

Add to crontab for weekly health checks:
```cron
0 8 * * 1 /home/scpbot/scp-bot/health_check.sh
```

## Troubleshooting

### Bot Won't Start

1. Check logs:
```bash
sudo journalctl -u scp-bot -f
```

2. Common issues:
   - Missing Discord token in `.env`
   - Database file missing (run scraper first)
   - Permission issues

### Database Issues

1. Check database file:
```bash
ls -la ~/scp-bot/library_content.db
```

2. Rebuild if corrupted:
```bash
cd ~/scp-bot
source venv/bin/activate
python scraper.py --full
```

### Permission Issues

1. Fix ownership:
```bash
sudo chown -R scpbot:scpbot ~/scp-bot
```

2. Fix permissions:
```bash
chmod 600 ~/scp-bot/.env
chmod +x ~/scp-bot/*.sh
```

### Memory Issues

If the bot uses too much memory:

1. Monitor usage:
```bash
htop
# or
free -h
```

2. Consider upgrading your SparkedHost plan

## Performance Optimization

### For Larger Libraries

1. **Increase timeout values** in `scraper.py`:
```python
self.request_delay = 2.0  # Increase delay between requests
```

2. **Limit concurrent operations** in `bot.py`:
```python
# Add rate limiting for admin commands
```

3. **Database optimization**:
```bash
# Run VACUUM on SQLite database weekly
sqlite3 library_content.db "VACUUM;"
```

## Backup Strategy

### 1. Database Backup

Create backup script:
```bash
nano ~/scp-bot/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/scpbot/backups"
mkdir -p $BACKUP_DIR

# Create timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp ~/scp-bot/library_content.db $BACKUP_DIR/library_content_$TIMESTAMP.db

# Keep only last 7 days of backups
find $BACKUP_DIR -name "library_content_*.db" -mtime +7 -delete

echo "Backup created: library_content_$TIMESTAMP.db"
```

### 2. Automated Backups

Add to crontab:
```cron
0 3 * * * /home/scpbot/scp-bot/backup.sh
```

## Support and Updates

### Updating Your Bot

1. Pull latest changes:
```bash
cd ~/scp-bot
git pull origin main
```

2. Update dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

3. Restart service:
```bash
sudo systemctl restart scp-bot
```

### Getting Help

- Check SparkedHost documentation
- Review Discord.py documentation
- Check bot logs for specific errors

## Cost Optimization

### Resource Usage

Monitor your server usage:
```bash
# CPU and Memory
htop

# Disk usage
df -h

# Network usage
iftop
```

### Scaling Options

- **Start with shared hosting** if budget is tight
- **Upgrade to VPS** when you need more control
- **Consider dedicated server** for high-traffic bots

---

## Quick Reference Commands

```bash
# Start bot
sudo systemctl start scp-bot

# Stop bot
sudo systemctl stop scp-bot

# Restart bot
sudo systemctl restart scp-bot

# Check status
sudo systemctl status scp-bot

# View logs
sudo journalctl -u scp-bot -f

# Manual update
cd ~/scp-bot && source venv/bin/activate && python scraper.py --update

# Health check
~/scp-bot/health_check.sh
```

Your SCP bot should now be running 24/7 on SparkedHost! 🚀
