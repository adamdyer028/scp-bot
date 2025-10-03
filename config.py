# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is required")

# Database Configuration
DATABASE_PATH = "library_content.db"

# Library Configuration
LIBRARY_BASE_URL = "https://sacredcommunityproject.org"
SCRAPER_SCRIPT = "scraper.py"

# Bot Settings
COMMAND_PREFIX = "!"
BOT_DESCRIPTION = "Digital Library Assistant for Sacred Community Project"

# Admin Settings
ADMIN_ROLE_NAMES = ["Admin", "Moderator", "Library Manager"]  # Roles that can run update commands

# Interface Settings
MAX_DROPDOWN_OPTIONS = 25  # Discord limit
RESULTS_PER_PAGE = 5
SEARCH_RESULTS_LIMIT = 20

# Colors for embeds (hex colors)
COLORS = {
    "primary": 0x5865F2,      # Discord blue
    "success": 0x57F287,      # Green
    "warning": 0xFEE75C,      # Yellow
    "error": 0xED4245,        # Red
    "info": 0x5865F2          # Blue
}