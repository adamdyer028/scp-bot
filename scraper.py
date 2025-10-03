# scraper.py
import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import re
from urllib.parse import urljoin, urlparse
import os
import sys

# Fix Windows console encoding for emojis
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform.startswith('win'):
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

class Scraper:
    def __init__(self, base_url="https://sacredcommunityproject.org", db_path="library_content.db"):
        self.base_url = base_url
        self.db_path = db_path
        self.sitemap_urls = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap.index.xml"
        ]
        self.request_delay = 1.5  # Seconds between requests
        self.max_retries = 3
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; LibraryBot/1.0)'
        })
        
        # Archive dates mapping - will be populated when needed
        self.archive_dates_map = {}
        
        self.stats = {
            'urls_found': 0,
            'articles_found': 0,
            'pages_scraped': 0,
            'errors': 0,
            'start_time': None,
            'dates_extracted': 0
        }
        
        self.setup_database()
    
    def setup_database(self):
        """Create database and tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main content table - add description column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                categories TEXT,
                author TEXT,
                published_date TEXT,
                tags TEXT,
                description TEXT,
                last_modified TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scrape_success BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Scraping log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraping_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                urls_found INTEGER,
                articles_found INTEGER,
                pages_scraped INTEGER,
                errors INTEGER,
                duration_minutes REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Database setup complete: {self.db_path}")
    
    def is_article_url(self, url):
        """Determine if URL is an actual article (not category/tag/author page)"""
        
        # Must contain /digital-library/
        if '/digital-library' not in url:
            return False
            
        # Exclude main library page
        if url.endswith('/digital-library') or url.endswith('/digital-library/'):
            return False
            
        # Exclude category pages: /digital-library/category/something
        if '/digital-library/category/' in url:
            return False
            
        # Exclude tag pages: /digital-library/tag/something  
        if '/digital-library/tag/' in url:
            return False
            
        # Exclude author pages: /digital-library?author=123
        if '?author=' in url or '&author=' in url:
            return False
            
        # Exclude other filter pages with query parameters
        if '/digital-library?' in url:
            return False
            
        # If it contains /digital-library/ followed by content, it's likely an article
        # Pattern: /digital-library/article-title-here
        if '/digital-library/' in url and not any(x in url for x in ['category/', 'tag/', '?']):
            return True
            
        return False
    
    def get_all_urls_from_sitemap(self):
        """Parse sitemap(s) and extract all URLs"""
        all_urls = []
        
        for sitemap_url in self.sitemap_urls:
            print(f"📄 Checking sitemap: {sitemap_url}")
            
            try:
                response = self.session.get(sitemap_url, timeout=30)
                response.raise_for_status()
                
                # Parse XML
                root = ET.fromstring(response.content)
                
                # Handle both regular sitemaps and sitemap index files
                if 'sitemapindex' in root.tag:
                    # This is a sitemap index, get individual sitemaps
                    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                        loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                        if loc is not None:
                            sub_urls = self.parse_individual_sitemap(loc.text)
                            all_urls.extend(sub_urls)
                else:
                    # This is a regular sitemap
                    urls = self.parse_individual_sitemap(sitemap_url)
                    all_urls.extend(urls)
                    
            except Exception as e:
                print(f"❌ Error reading sitemap {sitemap_url}: {e}")
        
        self.stats['urls_found'] = len(all_urls)
        print(f"📊 Total URLs found in sitemap: {len(all_urls)}")
        
        return all_urls
    
    def parse_individual_sitemap(self, sitemap_url):
        """Parse a single sitemap file"""
        urls = []
        
        try:
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                lastmod = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
                
                if loc is not None:
                    url_data = {
                        'url': loc.text,
                        'lastmod': lastmod.text if lastmod is not None else None
                    }
                    urls.append(url_data)
        
        except Exception as e:
            print(f"❌ Error parsing sitemap {sitemap_url}: {e}")
        
        return urls
    
    def filter_article_urls(self, all_urls):
        """Filter URLs to only include actual articles"""
        article_urls = []
        
        print("🔍 Filtering URLs to find actual articles...")
        
        for url_data in all_urls:
            if self.is_article_url(url_data['url']):
                article_urls.append(url_data)
        
        self.stats['articles_found'] = len(article_urls)
        
        print(f"✅ Found {len(article_urls)} article URLs (filtered from {len(all_urls)} total)")
        print(f"📝 Sample article URLs:")
        for i, url_data in enumerate(article_urls[:3]):
            print(f"   {i+1}. {url_data['url']}")
        if len(article_urls) > 3:
            print(f"   ... and {len(article_urls) - 3} more")
        
        return article_urls
    
    def extract_description(self, soup):
        """Extract first substantial paragraph as description"""
        try:
            # Look for the main content area
            content_area = soup.find('div', class_='sqs-html-content')
            
            if content_area:
                # Get all paragraphs
                paragraphs = content_area.find_all('p')
                
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    # Skip very short paragraphs, empty ones, and promotional content
                    if (len(text) > 50 and 
                        not any(word in text.lower() for word in ['order', 'buy', 'purchase', 'copy today'])):
                        # Return first 300 characters as description
                        return text[:300] + "..." if len(text) > 300 else text
            
            # If no good paragraph found, try blockquote
            blockquote = soup.find('blockquote')
            if blockquote:
                text = blockquote.get_text(strip=True)
                return text[:300] + "..." if len(text) > 300 else text
            
            return ""
            
        except Exception as e:
            print(f"   ⚠️  Error extracting description: {e}")
            return ""

    def scrape_dates_from_archives(self):
        """Scrape dates from archive pages for better sorting"""
        print("📅 Extracting dates from archive pages...")
        dates = {}  # URL -> date mapping
        
        archive_url = f"{self.base_url}/digital-library"
        page_count = 0
        
        while archive_url and page_count < 50:  # Safety limit
            try:
                print(f"   📄 Archive page {page_count + 1}: {archive_url}")
                response = self.session.get(archive_url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                articles = soup.find_all('article', class_='blog-basic-grid--container')
                print(f"   Found {len(articles)} articles on this page")
                
                for article in articles:
                    # Extract URL
                    title_link = article.find('h1', class_='blog-title')
                    if title_link:
                        link_tag = title_link.find('a')
                        if link_tag and link_tag.has_attr('href'):
                            url = f"{self.base_url}{link_tag.get('href')}"
                            
                            # Extract date from archive listing
                            date_element = article.find('time', class_='blog-date')
                            if date_element:
                                date_text = date_element.get_text(strip=True)
                                # Convert "7/19/25" to "2025-07-19" format for sorting
                                try:
                                    parsed_date = datetime.strptime(date_text, '%m/%d/%y')
                                    formatted_date = parsed_date.strftime('%Y-%m-%d')
                                    dates[url] = formatted_date
                                    self.stats['dates_extracted'] += 1
                                except ValueError:
                                    # Try alternative formats if needed
                                    dates[url] = date_text  # Keep original if parsing fails
                                    print(f"   ⚠️  Could not parse date '{date_text}' for {url}")
                
                # Find next page
                older_posts = soup.find('div', class_='older')
                if older_posts and older_posts.find('a'):
                    next_href = older_posts.find('a').get('href')
                    archive_url = f"{self.base_url}{next_href}"
                    page_count += 1
                    time.sleep(self.request_delay)
                else:
                    archive_url = None
                    
            except Exception as e:
                print(f"❌ Error scraping archive page {page_count + 1}: {e}")
                break
        
        print(f"✅ Extracted {len(dates)} dates from {page_count + 1} archive pages")
        return dates
    
    def scrape_page(self, url_data):
        """Scrape a single page and extract metadata"""
        url = url_data['url']
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                data = self.extract_metadata(soup, url_data)
                
                return data
                
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)  # Wait before retry
                else:
                    self.stats['errors'] += 1
                    return None
    
    def extract_metadata(self, soup, url_data):
        """Extract metadata from HTML with improved category and date handling"""
        data = {
            'url': url_data['url'],
            'last_modified': url_data.get('lastmod'),
            'scrape_success': True
        }
        
        try:
            # Title
            title_element = soup.find('h1', class_='entry-title')
            data['title'] = title_element.text.strip() if title_element else 'No title found'
            
            # Categories (IMPROVED - gets ALL categories)
            category_element = soup.find('div', {'data-content-field': 'categories'})
            if category_element:
                # Find all category links within the wrapper spans
                category_links = category_element.find_all('a', class_='blog-item-category')
                categories = [link.text.strip() for link in category_links]
                data['categories'] = ', '.join(categories) if categories else 'Uncategorized'
            else:
                data['categories'] = 'Uncategorized'
            
            # Author
            author_element = soup.find('div', {'data-content-field': 'author'})
            if author_element:
                author_link = author_element.find('a')
                data['author'] = author_link.text.strip() if author_link else 'Unknown'
            else:
                data['author'] = 'Unknown'
            
            # Date - enhanced to use archive date if available
            date_element = soup.find('time', {'data-content-field': 'published-on'})
            if date_element:
                date_value = date_element.get('datetime') or date_element.text.strip()
                data['published_date'] = date_value
            else:
                data['published_date'] = 'Unknown'

            # If we have archive date from archive_dates_map, use that instead (more reliable)
            if hasattr(self, 'archive_dates_map') and data['url'] in self.archive_dates_map:
                data['published_date'] = self.archive_dates_map[data['url']]

            # Tags
            tags_element = soup.find('div', {'data-content-field': 'tags'})
            if tags_element:
                tag_links = tags_element.find_all('a', class_='blog-item-tag')
                tags = [tag.text.strip() for tag in tag_links]
                data['tags'] = json.dumps(tags)
            else:
                data['tags'] = json.dumps([])
            
            # Description - extract first substantial paragraph
            data['description'] = self.extract_description(soup)
            
            # Validate that we got a real article (has title)
            if data['title'] == 'No title found' or not data['title']:
                data['scrape_success'] = False
                print(f"⚠️  Warning: No title found for {data['url']} - might not be an article")
            
        except Exception as e:
            print(f"❌ Error extracting metadata from {data['url']}: {e}")
            data['scrape_success'] = False
        
        return data
    
    def store_data(self, data):
        """Store data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO library_content 
                (url, title, categories, author, published_date, tags, description, last_modified, scrape_success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['url'],
                data['title'],
                data['categories'],
                data['author'],
                data['published_date'],
                data['tags'],
                data['description'],
                data['last_modified'],
                data['scrape_success']
            ))
            
            conn.commit()
            
        except Exception as e:
            print(f"❌ Error storing data: {e}")
        
        finally:
            conn.close()
    
    def check_for_updates(self):
        """Check for new or updated articles without scraping"""
        print("🔍 Checking for library updates...")
        
        # Get all URLs from sitemap
        all_urls = self.get_all_urls_from_sitemap()
        article_urls = self.filter_article_urls(all_urls)
        
        if not article_urls:
            print("❌ No article URLs found.")
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        new_articles = []
        updated_articles = []
        
        for url_data in article_urls:
            cursor.execute('SELECT last_modified, scraped_at FROM library_content WHERE url = ?', (url_data['url'],))
            result = cursor.fetchone()
            
            if result is None:
                # New article we haven't seen before
                new_articles.append(url_data)
            else:
                stored_lastmod = result[0]
                sitemap_lastmod = url_data.get('lastmod')
                
                # If lastmod is newer or different, we need to update
                if sitemap_lastmod and sitemap_lastmod != stored_lastmod:
                    updated_articles.append(url_data)
        
        conn.close()
        
        print(f"🆕 New articles found: {len(new_articles)}")
        print(f"📝 Articles to update: {len(updated_articles)}")
        
        if new_articles:
            print("📄 New articles:")
            for i, url_data in enumerate(new_articles[:5], 1):
                print(f"   {i}. {url_data['url']}")
            if len(new_articles) > 5:
                print(f"   ... and {len(new_articles) - 5} more")
        
        if updated_articles:
            print("🔄 Articles to update:")
            for i, url_data in enumerate(updated_articles[:5], 1):
                print(f"   {i}. {url_data['url']}")
            if len(updated_articles) > 5:
                print(f"   ... and {len(updated_articles) - 5} more")
        
        return new_articles + updated_articles
    
    def run_incremental_update(self):
        """Run incremental update - only scrape new/changed articles"""
        print("🔄 Starting incremental library update...")
        print("=" * 60)
        
        self.stats['start_time'] = datetime.now()
        
        # Find articles that need updating
        articles_to_update = self.check_for_updates()
        
        if not articles_to_update:
            print("✅ Library is up to date! No changes needed.")
            return
        
        # Extract dates from archives for better dating
        print("📅 Extracting dates from archive pages first...")
        self.archive_dates_map = self.scrape_dates_from_archives()
        
        print(f"📍 Scraping {len(articles_to_update)} articles...")
        print(f"⏱️  Estimated time: {(len(articles_to_update) * self.request_delay) / 60:.1f} minutes")
        
        successful_scrapes = 0
        
        for i, url_data in enumerate(articles_to_update, 1):
            print(f"📄 [{i}/{len(articles_to_update)}] {url_data['url']}")
            
            # Scrape page
            data = self.scrape_page(url_data)
            
            if data:
                # Store in database
                self.store_data(data)
                self.stats['pages_scraped'] += 1
                
                # Show progress for successful scrapes
                if data['scrape_success'] and data['title'] != 'No title found':
                    successful_scrapes += 1
                    categories_display = data['categories'][:50] + "..." if len(data['categories']) > 50 else data['categories']
                    description_display = data['description'][:50] + "..." if len(data['description']) > 50 else data['description']
                    date_display = data['published_date']
                    print(f"   ✅ {data['title'][:30]}... | {date_display} | {description_display}")
                else:
                    print(f"   ⚠️  Issue with this page")
            
            # Rate limiting
            time.sleep(self.request_delay)
        
        # Summary
        duration = (datetime.now() - self.stats['start_time']).total_seconds() / 60
        
        print("\n" + "=" * 60)
        print("🎉 INCREMENTAL UPDATE COMPLETE!")
        print("=" * 60)
        print(f"📄 Articles updated: {len(articles_to_update)}")
        print(f"✅ Successful: {successful_scrapes}")
        print(f"📅 Dates extracted: {self.stats['dates_extracted']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"⏱️  Duration: {duration:.1f} minutes")
        
        # Log to database
        self.log_incremental_update(len(articles_to_update), successful_scrapes, duration)
    
    def log_incremental_update(self, articles_updated, successful, duration):
        """Log incremental update to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add incremental update log table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                articles_checked INTEGER,
                articles_updated INTEGER,
                successful_updates INTEGER,
                duration_minutes REAL,
                update_type TEXT
            )
        ''')
        
        # Get total articles in database for context
        cursor.execute('SELECT COUNT(*) FROM library_content')
        total_articles = cursor.fetchone()[0]
        
        cursor.execute('''
            INSERT INTO update_log (articles_checked, articles_updated, successful_updates, duration_minutes, update_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (total_articles, articles_updated, successful, duration, 'incremental'))
        
        conn.commit()
        conn.close()
    
    def run_full_scrape(self):
        """Run complete scraping process with improved filtering and date extraction"""
        print("🚀 Starting full library scrape...")
        print("=" * 60)
        
        self.stats['start_time'] = datetime.now()
        
        # Step 1: Get all URLs from sitemap
        print("📍 Step 1: Discovering all URLs from sitemap...")
        all_urls = self.get_all_urls_from_sitemap()
        
        if not all_urls:
            print("❌ No URLs found. Check sitemap URLs.")
            return
        
        # Step 2: Filter for actual articles only
        print("📍 Step 2: Filtering for actual articles...")
        article_urls = self.filter_article_urls(all_urls)
        
        if not article_urls:
            print("❌ No article URLs found after filtering.")
            return
        
        # Step 3: Extract dates from archive pages
        print("📍 Step 3: Extracting dates from archive pages...")
        self.archive_dates_map = self.scrape_dates_from_archives()
        
        # Step 4: Scrape all article pages
        print(f"📍 Step 4: Scraping {len(article_urls)} article pages...")
        print(f"⏱️  Estimated time: {(len(article_urls) * self.request_delay) / 60:.1f} minutes")
        
        successful_scrapes = 0
        
        for i, url_data in enumerate(article_urls, 1):
            print(f"📄 [{i}/{len(article_urls)}] {url_data['url']}")
            
            # Scrape page
            data = self.scrape_page(url_data)
            
            if data:
                # Store in database
                self.store_data(data)
                self.stats['pages_scraped'] += 1
                
                # Show progress for successful scrapes
                if data['scrape_success'] and data['title'] != 'No title found':
                    successful_scrapes += 1
                    categories_display = data['categories'][:50] + "..." if len(data['categories']) > 50 else data['categories']
                    description_display = data['description'][:50] + "..." if len(data['description']) > 50 else data['description']
                    date_display = data['published_date']
                    print(f"   ✅ {data['title'][:30]}... | {date_display} | {description_display}")
                else:
                    print(f"   ⚠️  Issue with this page - check if it's really an article")
            
            # Rate limiting
            time.sleep(self.request_delay)
            
            # Progress update every 10 pages
            if i % 10 == 0:
                elapsed = (datetime.now() - self.stats['start_time']).total_seconds() / 60
                success_rate = (successful_scrapes / i) * 100
                print(f"📊 Progress: {i}/{len(article_urls)} ({i/len(article_urls)*100:.1f}%) - {success_rate:.1f}% success rate - {elapsed:.1f} min elapsed")
        
        # Step 5: Summary
        self.log_scraping_session()
        self.print_summary()
        self.show_sample_data()
    
    def log_scraping_session(self):
        """Log scraping session to database"""
        duration = (datetime.now() - self.stats['start_time']).total_seconds() / 60
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO scraping_log (urls_found, articles_found, pages_scraped, errors, duration_minutes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            self.stats['urls_found'],
            self.stats['articles_found'],
            self.stats['pages_scraped'],
            self.stats['errors'],
            duration
        ))
        
        conn.commit()
        conn.close()
    
    def print_summary(self):
        """Print scraping summary"""
        duration = (datetime.now() - self.stats['start_time']).total_seconds() / 60
        
        print("\n" + "=" * 60)
        print("🎉 SCRAPING COMPLETE!")
        print("=" * 60)
        print(f"📊 Total URLs in sitemap: {self.stats['urls_found']}")
        print(f"🎯 Article URLs identified: {self.stats['articles_found']}")
        print(f"📄 Pages scraped: {self.stats['pages_scraped']}")
        print(f"📅 Dates extracted from archives: {self.stats['dates_extracted']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"⏱️  Duration: {duration:.1f} minutes")
        print(f"💾 Database: {self.db_path}")
        
        if self.stats['errors'] > 0:
            print(f"\n⚠️  {self.stats['errors']} pages had errors - check logs above")
    
    def show_sample_data(self):
        """Show sample of scraped data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get successful scrapes ordered by date
        cursor.execute('''
            SELECT title, categories, author, published_date, tags, description 
            FROM library_content 
            WHERE scrape_success = 1 AND title != "No title found"
            ORDER BY published_date DESC
            LIMIT 5
        ''')
        rows = cursor.fetchall()
        
        print(f"\n📊 SAMPLE SCRAPED DATA (Most Recent):")
        print("-" * 60)
        
        for row in rows:
            title, categories, author, date, tags, description = row
            tags_list = json.loads(tags) if tags else []
            
            print(f"Title: {title}")
            print(f"Categories: {categories}")
            print(f"Author: {author}")
            print(f"Date: {date}")
            print(f"Tags: {', '.join(tags_list[:3])}{'...' if len(tags_list) > 3 else ''}")
            print(f"Description: {description[:100]}{'...' if len(description) > 100 else ''}")
            print("-" * 40)
        
        # Get counts
        cursor.execute('SELECT COUNT(*) FROM library_content WHERE scrape_success = 1')
        successful_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT categories) FROM library_content WHERE scrape_success = 1')
        unique_categories = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT author) FROM library_content WHERE scrape_success = 1')
        unique_authors = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM library_content WHERE scrape_success = 1 AND description != ""')
        articles_with_descriptions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM library_content WHERE scrape_success = 1 AND published_date != "Unknown"')
        articles_with_dates = cursor.fetchone()[0]
        
        print(f"✅ Successfully scraped articles: {successful_count}")
        print(f"📂 Unique category combinations: {unique_categories}")
        print(f"✍️  Unique authors: {unique_authors}")
        print(f"📝 Articles with descriptions: {articles_with_descriptions}")
        print(f"📅 Articles with dates: {articles_with_dates}")
        
        conn.close()

def main():
    """Run the scraper with different modes"""
    import sys
    
    print("ENHANCED SCRAPER WITH DATE EXTRACTION")
    print("Features:")
    print("✅ Smart article detection (excludes category/tag/author pages)")
    print("✅ Multiple category extraction")
    print("✅ First paragraph description extraction")
    print("✅ Archive page date extraction with proper formatting")
    print("✅ Better error handling and validation")
    print("✅ Incremental updates (only scrape changed content)")
    print("✅ Detailed progress reporting")
    print()
    
    # Initialize scraper
    scraper = Scraper()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode in ['--update', '-u', 'update']:
            # Incremental update mode
            scraper.run_incremental_update()
            
        elif mode in ['--check', '-c', 'check']:
            # Just check what needs updating
            articles_to_update = scraper.check_for_updates()
            if articles_to_update:
                print(f"\nRun with --update to scrape these {len(articles_to_update)} articles")
            else:
                print("\n✅ No updates needed")
            return
            
        elif mode in ['--full', '-f', 'full']:
            # Full scrape mode
            scraper.run_full_scrape()
            
        elif mode in ['--help', '-h', 'help']:
            print("Usage:")
            print("  python scraper.py [mode]")
            print()
            print("Modes:")
            print("  --full, -f, full     Full scrape (rebuild entire database)")
            print("  --update, -u, update Incremental update (only new/changed)")
            print("  --check, -c, check   Check what needs updating (no scraping)")
            print("  --help, -h, help     Show this help message")
            print()
            print("Default: Full scrape")
            return
            
        else:
            print(f"❌ Unknown mode: {mode}")
            print("Use --help for usage information")
            return
    else:
        # Default: Full scrape
        scraper.run_full_scrape()
    
    print("\nNext steps:")
    print("1. Verify data looks correct")
    print("2. Set up Discord bot commands")
    print("3. Test incremental updates")
    print()
    print("Quick commands:")
    print("   python scraper.py --update   # Daily updates")
    print("   python scraper.py --check    # See what's new")
    print("   python scraper.py --full     # Full rebuild")

if __name__ == "__main__":
    main()