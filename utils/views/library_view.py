import discord
from discord.ext import commands
from typing import List, Dict, Optional
import logging

logger = logging.getLogger('DigitalLibrarian.Views')

# --- Fix CategorySelect and AuthorSelect to allow None for current_category/current_author ---
class CategorySelect(discord.ui.Select):
    """
    Dropdown for selecting categories from the digital library.
    """
    
    def __init__(self, categories: List[str], current_category: Optional[str] = None):
        # Discord Select menus have a 25 option limit
        options = [discord.SelectOption(
            label="All Categories",
            value="all",
            description="Show content from all categories",
            emoji="📚",
            default=(current_category is None or current_category == "all")
        )]
        
        # Add category options (limit to 24 to leave room for "All Categories")
        for category in categories[:24]:
            options.append(discord.SelectOption(
                label=category,
                value=category,
                description=f"Filter by {category}",
                emoji="🏷️",
                default=(current_category == category)
            ))
        
        super().__init__(
            placeholder="Choose a category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="category_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection."""
        selected_category = self.values[0] if self.values[0] != "all" else None
        
        # Get the parent view to update filters
        view = self.view
        if view and hasattr(view, 'update_filters'):
            await view.update_filters(interaction, category=selected_category)

class AuthorSelect(discord.ui.Select):
    """
    Dropdown for selecting authors from the digital library.
    """
    
    def __init__(self, authors: List[str], current_author: Optional[str] = None):
        options = [discord.SelectOption(
            label="All Authors",
            value="all",
            description="Show content from all authors",
            emoji="✍️",
            default=(current_author is None or current_author == "all")
        )]
        
        # Add author options (limit to 24)
        for author in authors[:24]:
            # Clean up author names for display
            display_name = author if author != "Unknown" else "Unknown Author"
            options.append(discord.SelectOption(
                label=display_name,
                value=author,
                description=f"Filter by {display_name}",
                emoji="👤",
                default=(current_author == author)
            ))
        
        super().__init__(
            placeholder="Choose an author...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="author_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle author selection."""
        selected_author = self.values[0] if self.values[0] != "all" else None
        
        # Get the parent view to update filters
        view = self.view
        if view and hasattr(view, 'update_filters'):
            await view.update_filters(interaction, author=selected_author)

# --- Fix SearchModal view access ---
class SearchModal(discord.ui.Modal):
    """
    Modal dialog for entering search queries.
    """
    
    def __init__(self, current_query: str = "", parent_view=None):
        super().__init__(title="Search Digital Library")
        
        self.parent_view = parent_view
        self.search_input = discord.ui.TextInput(
            label="Enter your search terms",
            placeholder="e.g., grief, meditation, retreat...",
            default=current_query,
            max_length=100,
            style=discord.TextStyle.short
        )
        self.add_item(self.search_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle search submission."""
        search_query = self.search_input.value.strip()
        
        # Get the original view from the interaction
        if self.parent_view and hasattr(self.parent_view, 'update_search'):
            await self.parent_view.update_search(interaction, search_query)
        else:
            message_view = getattr(interaction.message, 'view', None) if interaction.message else None
            if message_view and hasattr(message_view, 'update_search'):
                await message_view.update_search(interaction, search_query)
            else:
                await interaction.response.send_message("❌ Could not process search. Please try again.", ephemeral=True)

class LibraryView(discord.ui.View):
    """
    Main persistent view for the digital library interface.
    """
    
    def __init__(self, rss_parser, search_engine):
        super().__init__(timeout=None)  # Persistent view never times out
        self.rss_parser = rss_parser
        self.search_engine = search_engine
        
        # Current filter state
        self.current_category: Optional[str] = None
        self.current_author: Optional[str] = None
        self.current_query = ""
        self.current_results = []
        self.current_page = 0
        self.results_per_page = 5
        
        # Metadata
        self.categories = []
        self.authors = []
        
        logger.info("Library view initialized")
    
    async def initialize_metadata(self):
        """Load categories and authors from RSS feed."""
        try:
            metadata = await self.rss_parser.discover_metadata()
            self.categories = metadata.get('categories', [])
            self.authors = metadata.get('authors', [])
            
            # Add the dropdowns to the view
            self.clear_items()
            self.add_item(CategorySelect(self.categories, self.current_category))
            self.add_item(AuthorSelect(self.authors, self.current_author))
            self.add_search_button()
            self.add_navigation_buttons()
            
            logger.info(f"Metadata initialized: {len(self.categories)} categories, {len(self.authors)} authors")
            
        except Exception as e:
            logger.error(f"Failed to initialize metadata: {e}")
            raise
    
    def add_search_button(self):
        """Add the search button to the view."""
        search_button = discord.ui.Button(
            label="🔍 Search",
            style=discord.ButtonStyle.primary,
            custom_id="search_button",
            row=2
        )
        search_button.callback = self.search_button_callback
        self.add_item(search_button)
    
    def add_navigation_buttons(self):
        """Add navigation buttons for pagination."""
        # Previous page button
        prev_button = discord.ui.Button(
            label="◀️ Previous",
            style=discord.ButtonStyle.secondary,
            custom_id="prev_button",
            disabled=True,  # Initially disabled
            row=3
        )
        prev_button.callback = self.prev_page_callback
        self.add_item(prev_button)
        
        # Refresh button
        refresh_button = discord.ui.Button(
            label="🔄 Refresh",
            style=discord.ButtonStyle.secondary,
            custom_id="refresh_button",
            row=3
        )
        refresh_button.callback = self.refresh_callback
        self.add_item(refresh_button)
        
        # Next page button
        next_button = discord.ui.Button(
            label="Next ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="next_button",
            disabled=True,  # Initially disabled
            row=3
        )
        next_button.callback = self.next_page_callback
        self.add_item(next_button)
        
        # Clear filters button
        clear_button = discord.ui.Button(
            label="🗑️ Clear Filters",
            style=discord.ButtonStyle.danger,
            custom_id="clear_button",
            row=4
        )
        clear_button.callback = self.clear_filters_callback
        self.add_item(clear_button)
    
    async def search_button_callback(self, interaction: discord.Interaction):
        """Handle search button clicks."""
        modal = SearchModal(self.current_query, self)
        await interaction.response.send_modal(modal)
    
    async def prev_page_callback(self, interaction: discord.Interaction):
        """Handle previous page button."""
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_display(interaction)
    
    async def next_page_callback(self, interaction: discord.Interaction):
        """Handle next page button."""
        max_pages = (len(self.current_results) - 1) // self.results_per_page
        if self.current_page < max_pages:
            self.current_page += 1
            await self.update_display(interaction)
    
    async def refresh_callback(self, interaction: discord.Interaction):
        """Handle refresh button."""
        # Clear cache and reload results
        self.rss_parser.clear_cache()
        await self.load_results()
        await self.update_display(interaction)
    
    async def clear_filters_callback(self, interaction: discord.Interaction):
        """Handle clear filters button."""
        self.current_category = None
        self.current_author = None
        self.current_query = ""
        self.current_page = 0
        
        # Rebuild the interface with cleared filters
        await self.initialize_metadata()
        await self.load_results()
        await self.update_display(interaction)
    
    async def update_filters(self, interaction: discord.Interaction, category: Optional[str] = None, author: Optional[str] = None):
        """Update filters and reload results."""
        if category is not None:
            self.current_category = category
        if author is not None:
            self.current_author = author
        
        self.current_page = 0  # Reset to first page
        await self.load_results()
        await self.update_display(interaction)
    
    async def update_search(self, interaction: discord.Interaction, query: str):
        """Update search query and reload results."""
        self.current_query = query
        self.current_page = 0  # Reset to first page
        await self.load_results()
        await self.update_display(interaction)
    
    async def load_results(self):
        """Load search results based on current filters."""
        try:
            logger.info(f"Loading results: category={self.current_category}, author={self.current_author}, query='{self.current_query}'")
            
            # Search with current filters
            results = await self.rss_parser.search_content(
                query=self.current_query,
                category=self.current_category,
                author=self.current_author
            )
            
            # If we have a search query, enhance results with search engine
            if self.current_query:
                self.current_results = self.search_engine.search(results, self.current_query)
            else:
                self.current_results = results
            
            logger.info(f"Loaded {len(self.current_results)} results")
            
        except Exception as e:
            logger.error(f"Failed to load results: {e}")
            self.current_results = []
    
    def update_navigation_buttons(self):
        """Update navigation button states based on current page."""
        max_pages = max(0, (len(self.current_results) - 1) // self.results_per_page)
        
        # Find and update buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                custom_id = getattr(item, 'custom_id', None)
                if custom_id == "prev_button":
                    item.disabled = (self.current_page == 0)
                elif custom_id == "next_button":
                    item.disabled = (self.current_page >= max_pages)
    
    async def update_display(self, interaction: discord.Interaction):
        """Update the Discord message with current results."""
        try:
            # Update navigation button states
            self.update_navigation_buttons()
            
            # Create the main embed
            embed = self.create_results_embed()
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except discord.InteractionResponded:
            # Interaction already responded, use followup
            embed = self.create_results_embed()
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Failed to update display: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error updating display.", ephemeral=True)
    
    def create_results_embed(self) -> discord.Embed:
        """Create the main results embed."""
        # Create filter description
        filters = []
        if self.current_category:
            filters.append(f"📚 {self.current_category}")
        if self.current_author:
            filters.append(f"✍️ {self.current_author}")
        if self.current_query:
            filters.append(f"🔍 \"{self.current_query}\"")
        
        filter_text = " • ".join(filters) if filters else "All Content"
        
        # Create main embed
        embed = discord.Embed(
            title="📚 Digital Library Browser",
            description=f"**Current Filters:** {filter_text}",
            color=0x5865F2
        )
        
        # Add results
        if not self.current_results:
            embed.add_field(
                name="No Results Found",
                value="Try adjusting your filters or search terms.",
                inline=False
            )
        else:
            # Pagination
            start_idx = self.current_page * self.results_per_page
            end_idx = start_idx + self.results_per_page
            page_results = self.current_results[start_idx:end_idx]
            
            # Add each result
            for i, result in enumerate(page_results, start_idx + 1):
                title = result.get('highlighted_title', result.get('title', 'Untitled'))
                author = result.get('author', 'Unknown')
                description = result.get('search_snippet', result.get('description', 'No description'))
                link = result.get('link', '#')
                
                # Clean up highlighted title (remove markdown for embed)
                clean_title = title.replace('**', '')
                
                field_value = f"*By: {author}*\n{description[:100]}...\n[📖 View Content]({link})"
                
                embed.add_field(
                    name=f"{i}. {clean_title}",
                    value=field_value,
                    inline=False
                )
            
            # Add pagination info
            total_pages = max(1, (len(self.current_results) - 1) // self.results_per_page + 1)
            embed.set_footer(
                text=f"Page {self.current_page + 1} of {total_pages} • {len(self.current_results)} total results"
            )
        
        return embed
    
    async def create_initial_embed(self) -> discord.Embed:
        """Create the initial embed when first setting up the interface."""
        embed = discord.Embed(
            title="📚 Digital Library Browser",
            description="Welcome to the Sacred Community Project Digital Library! Use the dropdowns and search to explore our content.",
            color=0x5865F2
        )
        
        embed.add_field(
            name="🔍 How to Use",
            value="• Select a **category** from the first dropdown\n• Choose an **author** from the second dropdown\n• Click **🔍 Search** to add keywords\n• Use **navigation buttons** to browse results",
            inline=False
        )
        
        embed.add_field(
            name="📊 Library Stats",
            value=f"**Categories:** {len(self.categories)}\n**Authors:** {len(self.authors)}\n**Content Types:** Lectures, Meditations, Music, Podcasts, Retreats",
            inline=True
        )
        
        embed.set_footer(text="Select filters above to start browsing • Interface stays active until manually removed")
        
        return embed