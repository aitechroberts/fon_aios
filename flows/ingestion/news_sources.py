# flows/ingestion/newsapi_sources.py
import os
import json
import hashlib
import httpx
from datetime import datetime
from typing import Dict, List, Any, Iterator

class NewsAPIaiTopicSource():
    """NewsAPI.ai Topic-based ingestion"""
    
    def __init__(self, topic_uri: str, topic_name: str, topic_key: str):
        self.topic_uri = topic_uri
        self.topic_name = topic_name
        self.topic_key = topic_key  # Used for file naming (e.g., 'defense_tech')
        self.base_url = "https://newsapi.ai/api/v1/article/getArticlesForTopicPage"
        self.api_key = os.getenv("NEWSAPI_AI_KEY")
        
    @property
    def source_name(self) -> str:
        return f"newsapi_ai_{self.topic_key}"
    
    async def fetch_data_stream(self, params: Dict[str, Any]) -> Iterator[Dict]:
        """Stream articles from NewsAPI.ai topic"""
        
        max_articles = params.get('max_articles', 100)
        sort_by = params.get('sort_by', 'fq')  # 'date' or 'fq' (relevance)
        
        articles_fetched = 0
        
        # Only these parameters go to the API
        request_params = {
            "apiKey": self.api_key,
            "uri": self.topic_uri,
            "infoArticleBodyLen": -1,
            "resultType": "articles",
            "articlesSortBy": sort_by,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json=request_params,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Error fetching {self.topic_name}: {response.status_code}")
                return
                
            data = response.json()
            articles = data.get('articles', {}).get('results', [])
            
            # Yield articles up to max_articles limit
            for article in articles[:max_articles]:
                yield {
                    'raw_article': article,
                    'fetched_at': datetime.utcnow().isoformat(),
                    'topic_name': self.topic_name,
                    'topic_key': self.topic_key
                }
                articles_fetched += 1
    
    def transform_data(self, raw_item: Dict) -> Dict:
        """Transform NewsAPI.ai article to standard format"""
        article = raw_item['raw_article']
        
        # Generate unique ID from URI or URL
        article_id = article.get('uri', '').replace('/', '_').replace(':', '_')
        if not article_id:
            article_id = hashlib.md5(article.get('url', '').encode()).hexdigest()
        
        # Parse datetime
        date_time = article.get('dateTime', '')
        if date_time:
            try:
                pub_date = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
            except:
                pub_date = datetime.utcnow()
        else:
            pub_date = datetime.utcnow()
        
        return {
            'doc_id': f"newsapi_ai_{article_id}",
            'title': article.get('title', ''),
            'content': article.get('body', ''),
            'description': article.get('body', '')[:500] if article.get('body') else '',
            'link': article.get('url', ''),
            'published_at': pub_date,
            'source': article.get('source', {}).get('title', 'Unknown'),
            'source_type': 'news_article',
            'topic_name': raw_item.get('topic_name'),
            'topic_key': raw_item.get('topic_key'),
            'ingestion_timestamp': datetime.fromisoformat(raw_item['fetched_at']),
            'categories': [raw_item.get('topic_name')],  # Use topic as category
            'metadata': {
                'uri': article.get('uri'),
                'sentiment': article.get('sentiment'),
                'wgt': article.get('wgt'),  # Weight/relevance score
                'image': article.get('image')
            }
        }