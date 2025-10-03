#!/bin/bash

# SCP Bot Startup Script
# This script ensures proper environment setup and starts the bot

set -e  # Exit on any error

echo "🚀 Starting SCP Discord Bot..."

# Change to bot directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if requirements are installed
if [ ! -f "venv/.installed" ]; then
    echo "📥 Installing requirements..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch venv/.installed
    echo "✅ Requirements installed"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please copy env.template to .env and add your Discord token"
    exit 1
fi

# Check if database exists
if [ ! -f "library_content.db" ]; then
    echo "⚠️  Database not found. Running initial scraper..."
    python scraper.py --full
    echo "✅ Database created"
fi

# Start the bot
echo "🤖 Starting Discord bot..."
python bot.py
