# queries.py
import sqlite3
import json
from typing import List, Dict, Tuple, Optional
from config import DATABASE_PATH

class LibraryDatabase:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_all_categories(self) -> List[str]:
        """Get all unique categories from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT DISTINCT categories 
                FROM library_content 
                WHERE scrape_success = 1 AND categories != "Uncategorized"
                ORDER BY categories
            ''')
            
            all_categories = set()
            for row in cursor.fetchall():
                if row[0]:
                    # Split comma-separated categories
                    categories = [cat.strip() for cat in row[0].split(',')]
                    all_categories.update(categories)
            
            return sorted(list(all_categories))
            
        finally:
            conn.close()
    
    def get_all_authors(self) -> List[str]:
        """Get all unique authors from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT DISTINCT author 
                FROM library_content 
                WHERE scrape_success = 1 AND author != "Unknown"
                ORDER BY author
            ''')
            
            return [row[0] for row in cursor.fetchall()]
            
        finally:
            conn.close()
    
    def get_all_tags_with_counts(self) -> List[str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT tags FROM library_content 
                WHERE scrape_success = 1 AND tags != "[]"
            ''')
            
            tag_counts = {}
            for row in cursor.fetchall():
                if row[0]:
                    try:
                        tags = json.loads(row[0])
                        for tag in tags:
                            tag_counts[tag] = tag_counts.get(tag, 0) + 1
                    except json.JSONDecodeError:
                        continue
            
            # Get top 24 most popular tags
            sorted_by_popularity = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
            top_24_tags = [tag for tag, count in sorted_by_popularity[:24]]
        
            # Sort those 24 alphabetically for display
            return sorted(top_24_tags)
            
        finally:
            conn.close()
    
    def search_content(self, 
                      category: Optional[str] = None,
                      author: Optional[str] = None, 
                      tag: Optional[str] = None,
                      search_term: Optional[str] = None,
                      limit: int = 20) -> List[Dict]:
        """Search library content with filters"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Build query dynamically based on filters
            query = '''
                SELECT url, title, categories, author, published_date, tags, description
                FROM library_content 
                WHERE scrape_success = 1
            '''
            params = []
            
            if category:
                query += ' AND categories LIKE ?'
                params.append(f'%{category}%')
            
            if author:
                query += ' AND author = ?'
                params.append(author)
            
            if tag:
                query += ' AND tags LIKE ?'
                params.append(f'%"{tag}"%')  # JSON search
            
            if search_term:
                query += ' AND (title LIKE ? OR categories LIKE ? OR author LIKE ? OR tags LIKE ? OR description LIKE ?)'
                search_param = f'%{search_term}%'
                params.extend([search_param, search_param, search_param, search_param, search_param])
            
            query += ' ORDER BY published_date DESC, scraped_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                url, title, categories, author, published_date, tags, description = row
                
                # Parse tags JSON
                try:
                    parsed_tags = json.loads(tags) if tags else []
                except json.JSONDecodeError:
                    parsed_tags = []
                
                results.append({
                    'url': url,
                    'title': title,
                    'categories': categories,
                    'author': author,
                    'published_date': published_date,
                    'tags': parsed_tags,
                    'description': description or ''
                })
            
            return results
            
        finally:
            conn.close()
    
    def get_content_stats(self) -> Dict:
        """Get overall library statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Total articles
            cursor.execute('SELECT COUNT(*) FROM library_content WHERE scrape_success = 1')
            total_articles = cursor.fetchone()[0]
            
            # Unique categories
            categories = self.get_all_categories()
            
            # Unique authors
            authors = self.get_all_authors()
            
            # Unique tags
            tags = self.get_all_tags_with_counts()
            
            # Last update
            cursor.execute('SELECT MAX(scraped_at) FROM library_content')
            last_update = cursor.fetchone()[0]
            
            return {
                'total_articles': total_articles,
                'total_categories': len(categories),
                'total_authors': len(authors),
                'total_tags': len(tags),
                'last_update': last_update
            }
            
        finally:
            conn.close()
    
    def get_recent_content(self, limit: int = 10) -> List[Dict]:
        """Get most recently added content"""
        return self.search_content(limit=limit)
    
    def validate_database(self) -> bool:
        """Check if database exists and has content"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM library_content WHERE scrape_success = 1')
            count = cursor.fetchone()[0]
            
            conn.close()
            return count > 0
            
        except sqlite3.Error:
            return False

# Convenience functions for bot commands
def get_library_stats():
    """Quick function to get library statistics"""
    db = LibraryDatabase()
    return db.get_content_stats()

def search_library(category=None, author=None, tag=None, search_term=None, limit=20):
    """Quick function to search library"""
    db = LibraryDatabase()
    return db.search_content(category, author, tag, search_term, limit)

def get_dropdown_options():
    """Get options for Discord dropdowns"""
    db = LibraryDatabase()
    return {
        'categories': db.get_all_categories()[:25],  # Discord limit
        'authors': db.get_all_authors()[:25],
        'tags': db.get_all_tags_with_counts()[:25]
    }