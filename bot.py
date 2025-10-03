# bot.py
import discord
from discord.ext import commands
import asyncio
import subprocess
import sys
from datetime import datetime, timedelta
import json

# Import our custom modules
from config import *
from queries import LibraryDatabase, get_library_stats, search_library, get_dropdown_options

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, description=BOT_DESCRIPTION, intents=intents)

# Global admin operation lock
admin_operation_lock = asyncio.Lock()

def get_database():
    """Get a new database connection for each operation"""
    return LibraryDatabase()

@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'🤖 {bot.user} has connected to Discord!')
    print(f'📊 Bot is in {len(bot.guilds)} guilds')
    
    # Validate database
    db = get_database()
    if db.validate_database():
        stats = get_library_stats()
        print(f'📚 Database connected: {stats["total_articles"]} articles available')
    else:
        print('⚠️  Warning: Database not found or empty. Run the scraper first!')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')

# Utility Functions
def create_embed(title, description=None, color=COLORS["primary"]):
    """Create a standard embed"""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Sacred Community Project Digital Library")
    return embed

def format_article(article, show_description=True):
    """Format an article with category/author on one line, tags on separate line"""
    title = article['title'][:100] + "..." if len(article['title']) > 100 else article['title']
    
    # Get essential info
    categories = article['categories'] if article['categories'] != 'Uncategorized' else 'General'
    category = categories.split(',')[0]  # Just first category
    author = article['author'] if article['author'] != 'Unknown' else 'Unknown'
    
    # ALL tags
    tags = article['tags'] if article['tags'] else []
    tags_text = ', '.join(tags) if tags else 'No tags'
    
    # Clean format: category/author on one line, tags on next, no description
    return (f"**[{title}]({article['url']})**\n"
            f"📂 {category[:40]} • ✍️ {author[:30]}\n"
            f"🏷️ {tags_text}\n")

def has_admin_role(member):
    """Check if member has admin permissions"""
    if member.guild_permissions.administrator:
        return True
    
    member_roles = [role.name for role in member.roles]
    return any(role in ADMIN_ROLE_NAMES for role in member_roles)

# Description Modal for individual articles
class DescriptionModal(discord.ui.Modal):
    def __init__(self, article):
        super().__init__(title=f"Description: {article['title'][:50]}...")
        self.article = article
    
    async def on_submit(self, interaction: discord.Interaction):
        # This modal is just for display, so just acknowledge
        await interaction.response.defer()

# Library View Class with Auto-Delete on Timeout
class LibraryView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)  # 10 minutes
        self.user_id = user_id
        self.created_at = datetime.now()
        
        # Each user gets their own independent state
        self.current_filters = {
            'category': None,
            'author': None,
            'tag': None,
            'search_term': None
        }
        self.current_results = []
        self.current_page = 0
        
        # Add dropdowns
        self.add_category_dropdown()
        self.add_author_dropdown()
        self.add_tag_dropdown()
    
    async def on_timeout(self):
        """Auto-delete the message when timed out"""
        if not hasattr(self, '_message') or not self._message:
            return  # No message to clean up
        
        try:
            # Try to delete the message directly
            await self._message.delete()
        except discord.NotFound:
            # Message already deleted
            pass
        except discord.Forbidden:
            # No permission to delete (ephemeral messages can't be deleted by bot)
            # Edit to show expired message instead
            try:
                timeout_embed = create_embed(
                    "⏰ Library Session Expired", 
                    f"This interface timed out after 10 minutes.\n"
                    f"📚 **Use `/library` to open a fresh interface!**",
                    COLORS["secondary"]
                )
                await self._message.edit(embed=timeout_embed, view=None)
            except:
                pass
        except Exception as e:
            print(f"Error during timeout cleanup: {e}")
    
    def add_category_dropdown(self):
        """Add category dropdown"""
        try:
            options = get_dropdown_options()['categories']
            
            if options:
                dropdown_options = [discord.SelectOption(label="All Categories", value="clear")]
                dropdown_options.extend([
                    discord.SelectOption(label=cat[:100], value=cat) for cat in options[:24]  # Leave room for "All"
                ])
                
                category_dropdown = discord.ui.Select(
                    placeholder="Choose a category...",
                    options=dropdown_options,
                    custom_id="category_select"
                )
                category_dropdown.callback = self.category_callback
                self.add_item(category_dropdown)
        except Exception as e:
            print(f"Error adding category dropdown: {e}")
    
    def add_author_dropdown(self):
        """Add author dropdown"""
        try:
            options = get_dropdown_options()['authors']
            
            if options:
                dropdown_options = [discord.SelectOption(label="All Authors", value="clear")]
                dropdown_options.extend([
                    discord.SelectOption(label=author[:100], value=author) for author in options[:24]
                ])
                
                author_dropdown = discord.ui.Select(
                    placeholder="Choose an author...",
                    options=dropdown_options,
                    custom_id="author_select"
                )
                author_dropdown.callback = self.author_callback
                self.add_item(author_dropdown)
        except Exception as e:
            print(f"Error adding author dropdown: {e}")
    
    def add_tag_dropdown(self):
        """Add tag dropdown"""
        try:
            options = get_dropdown_options()['tags']
            
            if options:
                dropdown_options = [discord.SelectOption(label="All Tags", value="clear")]
                dropdown_options.extend([
                    discord.SelectOption(label=tag[:100], value=tag) for tag in options[:24]
                ])
                
                tag_dropdown = discord.ui.Select(
                    placeholder="Choose a tag...",
                    options=dropdown_options,
                    custom_id="tag_select"
                )
                tag_dropdown.callback = self.tag_callback
                self.add_item(tag_dropdown)
        except Exception as e:
            print(f"Error adding tag dropdown: {e}")
    
    async def category_callback(self, interaction):
        """Handle category selection"""
        selected = interaction.data['values'][0]
        self.current_filters['category'] = None if selected == "clear" else selected
        
        # Update dropdown placeholder to show selected value
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id == "category_select":
                if selected == "clear":
                    item.placeholder = "Choose a category..."
                else:
                    item.placeholder = f"Category: {selected[:80]}{'...' if len(selected) > 80 else ''}"
                break
        
        await self.update_results(interaction)
    
    async def author_callback(self, interaction):
        """Handle author selection"""
        selected = interaction.data['values'][0]
        self.current_filters['author'] = None if selected == "clear" else selected
        
        # Update dropdown placeholder to show selected value
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id == "author_select":
                if selected == "clear":
                    item.placeholder = "Choose an author..."
                else:
                    item.placeholder = f"Author: {selected[:80]}{'...' if len(selected) > 80 else ''}"
                break
        
        await self.update_results(interaction)
    
    async def tag_callback(self, interaction):
        """Handle tag selection"""
        selected = interaction.data['values'][0]
        self.current_filters['tag'] = None if selected == "clear" else selected
        
        # Update dropdown placeholder to show selected value
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id == "tag_select":
                if selected == "clear":
                    item.placeholder = "Choose a tag..."
                else:
                    item.placeholder = f"Tag: {selected[:80]}{'...' if len(selected) > 80 else ''}"
                break
        
        await self.update_results(interaction)
    
    async def update_results(self, interaction):
        """Update and display search results"""
        await interaction.response.defer()
        
        try:
            # Search with current filters using fresh database connection
            self.current_results = search_library(
                category=self.current_filters['category'],
                author=self.current_filters['author'],
                tag=self.current_filters['tag'],
                search_term=self.current_filters['search_term'],
                limit=SEARCH_RESULTS_LIMIT
            )
            
            self.current_page = 0
            await self.show_results(interaction)
        except Exception as e:
            print(f"Error updating results for user {self.user_id}: {e}")
            embed = create_embed("❌ Search Error", "An error occurred while searching. Please try again.", COLORS["error"])
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def show_results(self, interaction):
        """Display current results page"""
        if not self.current_results:
            embed = create_embed("No Results Found", "Try adjusting your filters.", COLORS["warning"])
            await interaction.edit_original_response(embed=embed, view=self)
            return
        
        # Pagination
        start_idx = self.current_page * RESULTS_PER_PAGE
        end_idx = start_idx + RESULTS_PER_PAGE
        page_results = self.current_results[start_idx:end_idx]
        
        # Create embed
        title = f"Library Search Results ({len(self.current_results)} found)"
        description = ""
        
        # Show active filters prominently
        active_filters = []
        if self.current_filters['category']:
            active_filters.append(f"📂 **{self.current_filters['category']}**")
        if self.current_filters['author']:
            active_filters.append(f"✍️ **{self.current_filters['author']}**")
        if self.current_filters['tag']:
            active_filters.append(f"🏷️ **{self.current_filters['tag']}**")
        if self.current_filters['search_term']:
            active_filters.append(f"🔍 **\"{self.current_filters['search_term']}\"**")
        
        if active_filters:
            description += f"🎯 **Active Filters:** {' | '.join(active_filters)}\n\n"
        
        # Add article results to description
        for article in page_results:
            description += format_article(article, show_description=False) + "\n"
        
        # Page info
        total_pages = (len(self.current_results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        if total_pages > 1:
            description += f"\n📄 Page {self.current_page + 1} of {total_pages}"
        
        embed = create_embed(title, description)
        
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="🔍 Search", style=discord.ButtonStyle.primary)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open search modal"""
        modal = SearchModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔄 Reset", style=discord.ButtonStyle.secondary)
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset all filters and return to welcome page"""
        # Clear all filters
        self.current_filters = {'category': None, 'author': None, 'tag': None, 'search_term': None}
        self.current_results = []
        self.current_page = 0
        
        # Reset dropdown placeholders to original text
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                if item.custom_id == "category_select":
                    item.placeholder = "Choose a category..."
                elif item.custom_id == "author_select":
                    item.placeholder = "Choose an author..."
                elif item.custom_id == "tag_select":
                    item.placeholder = "Choose a tag..."
        
        # Return to initial welcome page
        await interaction.response.defer()
        
        try:
            # Get initial stats with fresh connection
            stats = get_library_stats()
            
            embed = create_embed(
                "📚 Sacred Community Project Digital Library",
                f"Welcome to our digital library!\n\n"
                f"📊 **Library Stats:**\n"
                f"📄 {stats['total_articles']} articles\n"
                f"📂 {stats['total_categories']} categories\n"
                f"✍️ {stats['total_authors']} authors\n"
                f"🏷️ {stats['total_tags']} tags\n\n"
                f"*Click the dropdowns below to start browsing, or use the Search button for keyword search. Click the Reset button to clear all filters and return to the welcome page.*"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            print(f"Error resetting view for user {self.user_id}: {e}")
            embed = create_embed("❌ Reset Error", "An error occurred while resetting. Please try `/library` again.", COLORS["error"])
            await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.defer()
            await self.show_results(interaction)
        else:
            await interaction.response.send_message("You're already on the first page!", ephemeral=True)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        total_pages = (len(self.current_results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        if self.current_page < total_pages - 1:
            self.current_page += 1
            await interaction.response.defer()
            await self.show_results(interaction)
        else:
            await interaction.response.send_message("You're already on the last page!", ephemeral=True)

# Search Modal
class SearchModal(discord.ui.Modal, title="Search Library"):
    def __init__(self, library_view):
        super().__init__()
        self.library_view = library_view
    
    search_input = discord.ui.TextInput(
        label="Search terms",
        placeholder="Enter keywords to search titles, categories, authors, and descriptions...",
        required=False,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.library_view.current_filters['search_term'] = self.search_input.value if self.search_input.value else None
        await self.library_view.update_results(interaction)

# Simplified Library Command - No Cleanup Needed!
@bot.tree.command(name="library", description="Browse the digital library")
async def library_command(interaction: discord.Interaction):
    """Main library browsing command - each interface auto-deletes itself"""
    
    try:
        db = get_database()
        if not db.validate_database():
            embed = create_embed("Database Error", "Library database not found. Please contact an admin.", COLORS["error"])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create user-specific library interface
        view = LibraryView(interaction.user.id)
        stats = get_library_stats()
        
        embed = create_embed(
            "📚 Sacred Community Project Digital Library",
            f"Welcome! Use the dropdowns below to browse.\n\n"
            f"📊 **Library Stats:**\n"
            f"📄 {stats['total_articles']} articles\n"
            f"📂 {stats['total_categories']} categories\n"
            f"✍️ {stats['total_authors']} authors\n"
            f"🏷️ {stats['total_tags']} tags\n\n"
            f"*This interface will auto-delete after 10 minutes of inactivity.*"
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        # Set the message reference for auto-delete functionality
        view._message = await interaction.original_response()
        
    except Exception as e:
        print(f"Error in library command for user {interaction.user.id}: {e}")
        embed = create_embed("❌ Library Error", "An error occurred while loading the library. Please try again.", COLORS["error"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="library-stats", description="Show library statistics (Admin only)")
async def stats_command(interaction: discord.Interaction):
    """Show library statistics - Admin only"""
    if not has_admin_role(interaction.user):
        embed = create_embed("Permission Denied", "You need admin permissions to use this command.", COLORS["error"])
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        db = get_database()
        if not db.validate_database():
            embed = create_embed("Database Error", "Library database not found.", COLORS["error"])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        stats = get_library_stats()
        
        embed = create_embed(
            "📊 Library Statistics",
            f"📄 **Total Articles:** {stats['total_articles']}\n"
            f"📂 **Categories:** {stats['total_categories']}\n"
            f"✍️ **Authors:** {stats['total_authors']}\n"
            f"🏷️ **Tags:** {stats['total_tags']}\n"
            f"🕒 **Last Updated:** {stats['last_update']}"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        print(f"Error in stats command: {e}")
        embed = create_embed("❌ Stats Error", "An error occurred while retrieving statistics.", COLORS["error"])
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Admin Commands with Proper Locking
@bot.tree.command(name="quick-update-library", description="Update library database (Admin only)")
async def update_library_command(interaction: discord.Interaction):
    """Update library database incrementally"""
    if not has_admin_role(interaction.user):
        embed = create_embed("Permission Denied", "You need admin permissions to use this command.", COLORS["error"])
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Check if another admin operation is running
    if admin_operation_lock.locked():
        embed = create_embed("⏳ Operation In Progress", 
                           "Another admin is currently updating the library. Please wait for it to complete.", 
                           COLORS["warning"])
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    async with admin_operation_lock:
        embed = create_embed("🔄 Library Update", "Starting incremental update... This may take a moment.", COLORS["info"])
        await interaction.response.send_message(embed=embed)
        
        try:
            # Run scraper update command
            result = subprocess.run([sys.executable, SCRAPER_SCRIPT, "--update"], 
                          capture_output=True, text=True, timeout=300, 
                          encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                embed = create_embed("✅ Update Complete", "Library database updated successfully!", COLORS["success"])
                
                # Get new stats
                stats = get_library_stats()
                embed.add_field(name="Current Stats", 
                              value=f"📄 {stats['total_articles']} articles\n"
                                    f"📂 {stats['total_categories']} categories\n"
                                    f"✍️ {stats['total_authors']} authors", 
                              inline=False)
            else:
                embed = create_embed("❌ Update Failed", f"Error running update: {result.stderr[:1000]}", COLORS["error"])
        
        except subprocess.TimeoutExpired:
            embed = create_embed("⏱️ Update Timeout", "Update took too long. Check manually.", COLORS["warning"])
        except Exception as e:
            embed = create_embed("❌ Update Error", f"Unexpected error: {str(e)}", COLORS["error"])
        
        await interaction.edit_original_response(embed=embed)

@bot.tree.command(name="rebuild-library", description="Full library rebuild (Admin only)")
async def refresh_library_command(interaction: discord.Interaction):
    """Full library database refresh"""
    if not has_admin_role(interaction.user):
        embed = create_embed("Permission Denied", "You need admin permissions to use this command.", COLORS["error"])
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Check if another admin operation is running
    if admin_operation_lock.locked():
        embed = create_embed("⏳ Operation In Progress", 
                           "Another admin is currently updating the library. Please wait for it to complete.", 
                           COLORS["warning"])
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    async with admin_operation_lock:
        embed = create_embed("🔄 Full Refresh", "Starting full library refresh... This will take several minutes.", COLORS["info"])
        await interaction.response.send_message(embed=embed)
        
        try:
            # Run scraper full command
            result = subprocess.run([sys.executable, SCRAPER_SCRIPT, "--full"], 
                          capture_output=True, text=True, timeout=600,
                          encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                embed = create_embed("✅ Refresh Complete", "Full library refresh completed successfully!", COLORS["success"])
                
                # Get new stats
                stats = get_library_stats()
                embed.add_field(name="Updated Stats", 
                              value=f"📄 {stats['total_articles']} articles\n"
                                    f"📂 {stats['total_categories']} categories\n"
                                    f"✍️ {stats['total_authors']} authors", 
                              inline=False)
            else:
                embed = create_embed("❌ Refresh Failed", f"Error during refresh: {result.stderr[:1000]}", COLORS["error"])
        
        except subprocess.TimeoutExpired:
            embed = create_embed("⏱️ Refresh Timeout", "Refresh took too long. Check manually.", COLORS["warning"])
        except Exception as e:
            embed = create_embed("❌ Refresh Error", f"Unexpected error: {str(e)}", COLORS["error"])
        
        await interaction.edit_original_response(embed=embed)

# Error handling
@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    """Handle application command errors"""
    if interaction.response.is_done():
        return
    
    print(f"Command error for user {interaction.user.id}: {error}")
    embed = create_embed("❌ Command Error", "An error occurred while processing your command.", COLORS["error"])
    
    try:
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except:
        # If response fails, try followup
        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            pass  # Give up gracefully

# Run the bot
if __name__ == "__main__":
    if DISCORD_TOKEN == "your_discord_bot_token_here":
        print("❌ Please set your Discord bot token in config.py")
        sys.exit(1)
    
    print("🚀 Starting Multi-User Safe Discord Library Bot with Auto-Delete...")
    bot.run(DISCORD_TOKEN)