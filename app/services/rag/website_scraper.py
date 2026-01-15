"""
Website Scraper - Scrapes content from websites
"""
import logging
from typing import Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WebsiteScraper:
    """Scrape content from websites"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        logger.info("Initialized WebsiteScraper")
    
    def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Scrape content from a URL
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with scraped content and metadata
        """
        try:
            logger.info(f"Scraping URL: {url}")
            
            # Check if URL is accessible
            response = httpx.get(url, headers=self.headers, timeout=self.timeout, follow_redirects=True)
            
            # Check for authentication required
            if response.status_code == 401:
                raise ValueError("Website requires authentication. Cannot scrape protected content.")
            
            if response.status_code == 403:
                raise ValueError("Access forbidden. Website may require authentication.")
            
            if response.status_code != 200:
                raise ValueError(f"Failed to scrape URL. Status code: {response.status_code}")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Extract text
            text = soup.get_text(separator='\n', strip=True)
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text() if title else url
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content') if meta_desc else None
            
            # Clean up text (remove excessive whitespace)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            logger.info(f"✅ Successfully scraped URL: {url} ({len(cleaned_text)} characters)")
            
            return {
                "url": url,
                "title": title_text,
                "description": description,
                "text": cleaned_text,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
            }
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping URL {url}: {str(e)}")
            raise ValueError(f"Failed to access URL: {str(e)}")
        except ValueError as e:
            # Re-raise authentication/access errors
            raise
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {str(e)}")
            raise ValueError(f"Failed to scrape URL: {str(e)}")
