# Digital Librarian Bot Setup Guide

## Prerequisites

1. **Python 3.8+** installed on your system
2. **Discord Bot Token** - You'll need to create a Discord application and bot

## Step 1: Install Dependencies

First, install the required Python packages:

```bash
pip install -r requirements.txt
```

## Step 2: Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Copy the bot token (you'll need this for the next step)

## Step 3: Configure Environment Variables

Create a `.env` file in your project directory with the following content:

```
DISCORD_TOKEN=your_actual_bot_token_here
BOT_PREFIX=!
DEBUG_MODE=False
RSS_BASE_URL=https://your-digital-library-url.com
```

**Important:** Replace `your_actual_bot_token_here` with the token you copied from the Discord Developer Portal.

## Step 4: Invite Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" → "URL Generator"
2. Select "bot" under scopes
3. Select the permissions you want (at minimum: Send Messages, Use Slash Commands)
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

## Step 5: Run the Bot

```bash
python bot.py
```

If everything is configured correctly, you should see:
- "Digital Librarian Bot initialized"
- "Running setup_hook..."
- "Synced X command(s)"
- "Bot has connected to Discord!"

## Troubleshooting

### "DISCORD_TOKEN not found" Error
- Make sure you created a `.env` file
- Check that the token is copied correctly from Discord Developer Portal
- Ensure there are no extra spaces or quotes around the token

### "Invalid Discord token" Error
- Double-check your bot token in the Discord Developer Portal
- Make sure you're using the bot token, not the application ID

### Bot doesn't respond to commands
- Make sure the bot has the necessary permissions in your Discord server
- Check that you've enabled the required intents in the Discord Developer Portal

## Available Commands

Once the bot is running, you can use these slash commands:
- `/ping` - Check if the bot is responsive
- `/info` - Get information about the bot
- `/help` - Show help information

## Next Steps

The bot is currently set up with basic functionality. You can extend it by:
- Adding more slash commands
- Implementing the digital library features
- Adding calendar integration
- Setting up newsletter subscriptions 