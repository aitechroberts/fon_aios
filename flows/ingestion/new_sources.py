from flows.ingestion.base_ingestion_flow import DataSource
import feedparser
import httpx
import requests
from datetime import datetime
from typing import Dict, List, Any, Iterator
import hashlib
import itertools
import os

class DefenseNewsSource(DataSource):
    """Defense News RSS feed ingestion with streaming"""
    
    @property
    def source_name(self) -> str:
        return "defense_news"
    
    async def fetch_data_stream(self, params: Dict[str, Any]) -> Iterator[Dict]:
        """Stream articles from RSS feed"""
        feed_url = "https://www.defensenews.com/arc/outboundfeeds/rss/"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(feed_url)
            feed = feedparser.parse(response.text)
            
            for entry in feed.entries:
                # Filter by date if provided
                pub_date = datetime(*entry.published_parsed[:6])
                
                if 'start_date' in params:
                    start = datetime.fromisoformat(params['start_date'])
                    if pub_date < start:
                        continue
                
                yield {
                    'raw_entry': entry,
                    'fetched_at': datetime.utcnow().isoformat()
                }
    
    def transform_data(self, raw_item: Dict) -> Dict:
        """Transform a single RSS entry"""
        entry = raw_item['raw_entry']
        
        # Generate unique ID
        article_id = hashlib.md5(entry.link.encode()).hexdigest()
        
        # Extract and clean content
        content = entry.get('summary', '')
        if hasattr(entry, 'content'):
            content = entry.content[0].value if entry.content else content
        
        # Parse published date
        pub_date = datetime(*entry.published_parsed[:6])
        
        return {
            'doc_id': f"defense_news_{article_id}",
            'id': f"defense_news_{article_id}",  # Keep for backward compatibility
            'title': entry.title,
            'content': content,
            'description': entry.get('summary', ''),
            'link': entry.link,
            'published_at': pub_date.isoformat(),
            'source': 'Defense News',
            'source_type': 'news_article',
            'ingestion_timestamp': raw_item['fetched_at'],
            'categories': [tag.term for tag in entry.get('tags', [])]
        }

class NewsAPISource(DataSource):
    """NewsAPI with pagination streaming"""
    
    @property
    def source_name(self) -> str:
        return "newsapi"
    
    async def fetch_data_stream(self, params: Dict[str, Any]) -> Iterator[Dict]:
        """Stream NewsAPI results with pagination"""
        api_key = os.getenv("NEWSAPI_KEY")
        
        for page in itertools.count(1):
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": params.get("query", "defense"),
                        "pageSize": 100,
                        "page": page,
                        "from": params.get('start_date'),
                        "to": params.get('end_date'),
                        "apiKey": api_key
                    },
                    timeout=30
                )
                
                data = response.json()
                articles = data.get("articles", [])
                
                if not articles:
                    break
                    
                for article in articles:
                    yield {
                        'raw_article': article,
                        'fetched_at': datetime.utcnow().isoformat()
                    }
    
    def transform_data(self, raw_item: Dict) -> Dict:
        """Transform NewsAPI article"""
        article = raw_item['raw_article']
        
        # Generate unique ID from URL
        article_id = hashlib.md5(article['url'].encode()).hexdigest()
        
        return {
            'doc_id': f"newsapi_{article_id}",
            'id': f"newsapi_{article_id}",
            'title': article.get('title', ''),
            'content': article.get('content', ''),
            'description': article.get('description', ''),
            'link': article.get('url', ''),
            'published_at': article.get('publishedAt', ''),
            'source': article.get('source', {}).get('name', 'Unknown'),
            'source_type': 'news_article',
            'ingestion_timestamp': raw_item['fetched_at'],
            'categories': []
        }