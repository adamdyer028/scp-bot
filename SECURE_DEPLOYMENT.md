# Secure Token Deployment Guide

## 🔐 Keeping Your Discord Token Secure

### Step 1: Prepare Files for Upload

**Remove or rename your local .env file before uploading:**
```bash
# Option 1: Temporarily rename it
mv .env .env.local

# Option 2: Copy template for upload
cp env.template .env.upload
```

### Step 2: Upload Files to Server

```bash
# Upload all files except sensitive ones
scp -r bot.py config.py requirements.txt scraper.py queries.py utils/ start_bot.sh scp-bot.service deploy.sh env.template username@server:~/scp-bot/
```

### Step 3: Create .env on Server

**Method 1: Using nano (recommended)**
```bash
ssh username@your-server-ip
sudo su - scpbot
cd scp-bot
nano .env
```

Add your token:
```env
DISCORD_TOKEN=your_actual_discord_bot_token_here
```

**Method 2: Using echo (quick)**
```bash
echo "DISCORD_TOKEN=your_actual_discord_bot_token_here" > .env
```

### Step 4: Secure the .env File

```bash
# Make .env readable only by owner
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- 1 scpbot scpbot
```

### Step 5: Restore Local .env

```bash
# Back on your local machine
mv .env.local .env
```

## 🛡️ Additional Security Measures

### 1. Use SSH Key Authentication
Instead of passwords, use SSH keys:
```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096

# Copy to server
ssh-copy-id username@your-server-ip
```

### 2. Secure File Permissions
```bash
# On server, ensure proper permissions
sudo chown -R scpbot:scpbot ~/scp-bot
chmod 700 ~/scp-bot
chmod 600 ~/scp-bot/.env
```

### 3. Environment Variable Alternative
You can also set the token as a system environment variable:
```bash
# Add to ~/.bashrc or ~/.profile
echo 'export DISCORD_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

Then modify config.py to check for environment variable first:
```python
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_TOKEN')
```

## ⚠️ Important Security Notes

1. **Never commit .env to git** - it should be in .gitignore
2. **Never share your Discord token** - treat it like a password
3. **Use different tokens for different environments** (dev/prod)
4. **Rotate tokens periodically** if compromised
5. **Monitor your bot's activity** for unauthorized usage

## 🔄 Token Rotation Process

If you need to change your Discord token:

1. **Generate new token** in Discord Developer Portal
2. **Update server .env file**:
   ```bash
   nano ~/scp-bot/.env
   # Update the DISCORD_TOKEN value
   ```
3. **Restart the bot**:
   ```bash
   sudo systemctl restart scp-bot
   ```
4. **Update local .env** for development
5. **Revoke old token** in Discord Developer Portal

## 🚨 Emergency Response

If your token is compromised:

1. **Immediately revoke** the token in Discord Developer Portal
2. **Generate new token**
3. **Update server .env file**
4. **Restart bot service**
5. **Check bot logs** for suspicious activity
6. **Review server access logs**

## ✅ Security Checklist

- [ ] .env file not uploaded to server
- [ ] .env file has 600 permissions on server
- [ ] Discord token only in secure locations
- [ ] SSH key authentication enabled
- [ ] Bot running under dedicated user (not root)
- [ ] Regular security updates applied
- [ ] Bot activity monitored
