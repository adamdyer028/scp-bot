#!/bin/bash

# SCP Bot Quick Deployment Script for SparkedHost
# Run this script on your server to set up the bot quickly

set -e

echo "🚀 SCP Bot Quick Deployment Script"
echo "=================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Running as root. This script will create a 'scpbot' user."
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create bot user if it doesn't exist
if ! id "scpbot" &>/dev/null; then
    echo "👤 Creating scpbot user..."
    sudo useradd -m -s /bin/bash scpbot
    sudo usermod -aG sudo scpbot
    echo "✅ User created"
else
    echo "✅ User scpbot already exists"
fi

# Switch to bot user
echo "🔄 Switching to scpbot user..."
sudo -u scpbot bash << 'EOF'
cd ~

# Create bot directory
if [ ! -d "scp-bot" ]; then
    echo "📁 Creating bot directory..."
    mkdir scp-bot
fi

cd scp-bot

# Check if files exist (assuming they were uploaded)
if [ ! -f "bot.py" ]; then
    echo "❌ Bot files not found in ~/scp-bot/"
    echo "Please upload your bot files first using:"
    echo "scp -r /path/to/your/bot/* username@server:~/scp-bot/"
    exit 1
fi

echo "✅ Bot files found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate and install requirements
echo "📦 Installing requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    if [ -f "env.template" ]; then
        cp env.template .env
        echo "📝 Please edit .env file and add your Discord token:"
        echo "nano .env"
    else
        echo "DISCORD_TOKEN=your_discord_bot_token_here" > .env
        echo "📝 Please edit .env file and add your Discord token:"
        echo "nano .env"
    fi
fi

# Make scripts executable
chmod +x *.sh

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file: nano .env"
echo "2. Add your Discord bot token"
echo "3. Run initial scraper: python scraper.py --full"
echo "4. Test the bot: python bot.py"
echo "5. Set up systemd service (see SPARKEDHOST_DEPLOYMENT.md)"

EOF

echo ""
echo "🎉 Deployment script completed!"
echo "Switch to the scpbot user to continue:"
echo "sudo su - scpbot"
