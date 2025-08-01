# Free News APIs & Sources for FON AIOS Defense Intelligence

## Tier 1: Free APIs with Programmatic Access

### 1. **NewsAPI.org** ⭐⭐⭐⭐⭐
**Free Tier**: 1,000 requests/day, 30-day history
**Perfect for Your Use Case**: Excellent coverage of defense and tech news
**Relevant Sources Available**:
- Defense News, Breaking Defense, C4ISRNET
- TechCrunch, VentureBeat, IEEE Spectrum
- Reuters, Associated Press, Wall Street Journal

**FON-Specific Search Terms**:
```python
defense_queries = [
    "DARPA contract", "SBIR award", "defense contractor",
    "naval systems", "space systems", "unmanned platforms",
    "Lockheed Martin", "Boeing", "Raytheon", "General Dynamics",
    "autonomous systems", "cybersecurity defense"
]

healthcare_queries = [
    "surgical robotics", "medical devices FDA", "diagnostic systems",
    "wearable health technology", "medical AI", "robotic surgery"
]

manufacturing_queries = [
    "Industry 4.0", "smart manufacturing", "predictive maintenance",
    "digital twin", "factory automation", "IoT manufacturing"
]
```

### 2. **The Guardian API** ⭐⭐⭐⭐
**Free Tier**: Unlimited requests, high-quality journalism
**Strength**: Excellent technology and business coverage
**API Endpoint**: `https://content.guardianapis.com/search`
**Relevant Sections**: Technology, Business, Science, World News

### 3. **Reddit API** ⭐⭐⭐⭐
**Free Tier**: 100 requests/minute
**Value**: Industry discussions, early signals, technical communities
**Relevant Subreddits**:
- r/DefenseContracting, r/MilitaryTech, r/SpaceX
- r/Robotics, r/MachineLearning, r/IoT
- r/Manufacturing, r/Industry40, r/PredictiveMaintenance
- r/MedTech, r/SurgicalRobotics

### 4. **Hacker News API** ⭐⭐⭐
**Free Tier**: Unlimited
**Value**: Early tech signals, startup news, technical discussions
**Endpoint**: `https://hacker-news.firebaseio.com/v0/`

## Tier 2: RSS Feeds from Key Defense Publications

### **Defense & Government Sources**
```python
defense_rss_feeds = {
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/",
    "Breaking Defense": "https://breakingdefense.com/feed/",
    "C4ISRNET": "https://www.c4isrnet.com/arc/outboundfeeds/rss/",
    "Defense One": "https://www.defenseone.com/rss/",
    "Federal News Network": "https://federalnewsnetwork.com/feed/",
    "Military.com": "https://www.military.com/rss",
    "National Defense Magazine": "https://www.nationaldefensemagazine.org/RSS",
    "Jane's Defence Weekly": "https://www.janes.com/feeds/defence-weekly"
}
```

### **Space & Aerospace Sources**
```python
space_rss_feeds = {
    "SpaceNews": "https://spacenews.com/feed/",
    "Space Force Magazine": "https://www.spaceforce.com/rss",
    "Aviation Week": "https://aviationweek.com/rss.xml",
    "SpaceFlightNow": "https://spaceflightnow.com/feed/",
    "NASA News": "https://www.nasa.gov/rss/dyn/breaking_news.rss"
}
```

### **Technology & Industry Sources**
```python
tech_rss_feeds = {
    "IEEE Spectrum": "https://spectrum.ieee.org/rss",
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Wired": "https://www.wired.com/feed/rss",
    "MIT Technology Review": "https://www.technologyreview.com/feed/"
}
```

### **Healthcare & Medical Tech Sources**
```python
medtech_rss_feeds = {
    "MedTech Dive": "https://www.medtechdive.com/feeds/news/",
    "Medical Device Network": "https://www.medicaldevice-network.com/feed/",
    "FDA News": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds",
    "Modern Healthcare": "https://www.modernhealthcare.com/rss",
    "Healthcare IT News": "https://www.healthcareitnews.com/rss.xml"
}
```

## Tier 3: Government & Agency Sources (Direct RSS)

### **Contract & Funding Sources**
```python
government_feeds = {
    # DARPA
    "DARPA News": "https://www.darpa.mil/news/rss",
    
    # SBIR/STTR
    "SBIR.gov": "https://www.sbir.gov/rss",
    
    # Federal Contract Opportunities
    "SAM.gov Opportunities": "https://sam.gov/api/prod/opps/v3/opportunities/rss",
    
    # Department of Defense
    "DoD News": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945",
    "Air Force Research Lab": "https://www.afrl.af.mil/News/RSS/",
    "Office of Naval Research": "https://www.onr.navy.mil/RSS",
    "Army Research Lab": "https://www.arl.army.mil/RSS/",
    
    # NASA
    "NASA Contracts": "https://www.nasa.gov/rss/dyn/contracts.rss",
    "NASA Technology": "https://www.nasa.gov/rss/dyn/technology.rss",
    
    # Department of Energy
    "DOE ARPA-E": "https://arpa-e.energy.gov/rss.xml",
    
    # National Science Foundation
    "NSF Awards": "https://www.nsf.gov/news/rss/rss_awards.xml"
}
```

## Tier 4: Specialized Free Sources

### **Financial & Investment Sources**
```python
financial_feeds = {
    "SEC Filings (Defense Contractors)": "https://www.sec.gov/cgi-bin/browse-edgar",
    "Yahoo Finance (Defense Stocks)": "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Seeking Alpha": "https://seekingalpha.com/feed.xml"
}
```

### **Industry Trade Publications (Free Portions)**
```python
trade_publications = {
    "Manufacturing.net": "https://www.manufacturing.net/rss",
    "Control Engineering": "https://www.controleng.com/rss/",
    "Plant Engineering": "https://www.plantengineering.com/rss/",
    "Robotics Business Review": "https://www.roboticsbusinessreview.com/feed/",
    "IoT World Today": "https://www.iotworldtoday.com/feed/"
}
```

## Tier 5: Social Media & Discussion APIs

### **Twitter/X API** ⭐⭐⭐
**Free Tier**: 1,500 tweets/month (new restrictions)
**Value**: Real-time announcements from defense contractors, agencies
**Key Accounts to Monitor**:
```python
defense_twitter_accounts = [
    "@DARPA", "@SBIR_gov", "@DeptofDefense",
    "@LockheedMartin", "@Boeing", "@RaytheonTech",
    "@NorthropGrumman", "@GeneralDynamics",
    "@SpaceX", "@BlueOrigin", "@NASA"
]
```

### **LinkedIn API** ⭐⭐
**Free Tier**: Limited but useful for company announcements
**Value**: Executive announcements, company news, funding rounds

## Implementation Strategy for Your NiFi Pipeline

### **Priority 1 Sources (Implement First)**
1. **NewsAPI.org** - Broad coverage with good defense/tech sources
2. **Defense News RSS** - Primary defense industry publication
3. **DARPA RSS** - Direct government source for research funding
4. **Reddit API** - Early signals and technical discussions

### **Priority 2 Sources (Stage 2 Implementation)**
1. **Guardian API** - High-quality general technology coverage
2. **Space News RSS** - Space systems focus area coverage
3. **Government Contract RSS** - Direct contract award information
4. **Healthcare Trade Publication RSS** - Medical device coverage

### **NiFi Integration Pattern**
```python
# NiFi processor configuration for each source type
source_processors = {
    "NewsAPI": {
        "processor_type": "InvokeHTTP",
        "schedule": "0 */6 * * * ?",  # Every 6 hours
        "output_format": "JSON"
    },
    "RSS_Feeds": {
        "processor_type": "InvokeHTTP", 
        "schedule": "0 */2 * * * ?",  # Every 2 hours
        "output_format": "XML"
    },
    "Government_APIs": {
        "processor_type": "InvokeHTTP",
        "schedule": "0 */4 * * * ?",  # Every 4 hours
        "output_format": "Various"
    }
}
```

## Cost-Effective Keyword Strategy

Based on your subsector keywords, focus on these high-value search terms:

### **High-Priority Keywords (Use with Paid APIs if needed)**
```python
tier_1_keywords = [
    # Contract-specific
    "DARPA contract award", "SBIR Phase II", "defense contractor",
    
    # Technology-specific  
    "naval systems", "unmanned platforms", "autonomous systems",
    "surgical robotics", "medical devices", "predictive maintenance",
    
    # Company-specific
    "Lockheed Martin", "Boeing defense", "Raytheon contract"
]
```

### **Medium-Priority Keywords (Free APIs)**
```python
tier_2_keywords = [
    "space systems", "satellite", "cybersecurity", "IoT platform",
    "digital twin", "Industry 4.0", "robot collaboration",
    "energy storage", "renewable energy", "smart grid"
]
```

## Rate Limits & Management Strategy

### **Daily API Call Budget**
- **NewsAPI**: 800 calls/day (reserve 200 for urgent queries)
- **Guardian**: 500 calls/day (unlimited but be respectful)
- **Reddit**: 8,000 calls/day (100/minute × 16 hours)
- **RSS Feeds**: Unlimited (but cache to avoid redundant requests)

### **Airflow Schedule Optimization**
```python
# Stagger API calls to avoid rate limits
api_schedule = {
    "06:00": "NewsAPI_defense_keywords",
    "08:00": "Guardian_technology_search", 
    "10:00": "Reddit_defense_subreddits",
    "12:00": "RSS_feed_batch_1",
    "14:00": "NewsAPI_healthcare_keywords",
    "16:00": "Government_RSS_batch",
    "18:00": "RSS_feed_batch_2"
}
```

This approach gives you comprehensive coverage of your focus areas while staying within free tier limits. The combination of real-time APIs and RSS feeds ensures you capture both breaking news and regular industry updates relevant to your investment intelligence needs.