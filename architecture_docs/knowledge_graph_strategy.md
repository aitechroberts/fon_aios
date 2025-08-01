# FON AIOS Graph Database & Entity Relationship Strategy

## Why Graph Database is Essential (Not Optional)

In defense investing, **relationships are often more valuable than entities**:

- **Investment Thesis**: "Company A partners with Company B, B has a contract with Agency C, C is funding Technology D that A specializes in" 
- **Risk Assessment**: Personnel networks, competitive landscapes, supply chain dependencies
- **Opportunity Discovery**: "Who else works on similar tech?" "What companies have relationships with our targets?"
- **Due Diligence**: Board connections, previous collaborations, technology dependencies

**Recommendation: Implement in Stage 1 (0-3 months)** as foundational infrastructure.

## Graph Database Architecture Decision

### Single Graph Database Approach (Recommended)

**Use Neo4j as primary graph database** with Azure AI Search as the search/discovery layer.

**Why single database:**
- **Dynamic Relationships**: Capture evolving partnerships, personnel moves, contract changes
- **Multi-hop Queries**: "Find companies 2-3 degrees separated from target that work on similar tech"
- **Relationship Strength**: Weight edges based on interaction frequency, contract values, personnel overlap
- **Temporal Tracking**: Track relationship evolution over time
- **Cross-Domain Insights**: Connect technology trends with market movements with personnel changes

### Entity Types & Relationship Schema

```cypher
// Core Entity Types
(:Company {name, type, size, founded, headquarters, focus_areas, ticker})
(:Person {name, title, linkedin, background, expertise})
(:Technology {name, category, maturity_level, applications})
(:Contract {id, value, duration, phase, status})
(:Agency {name, department, budget, focus_areas})
(:ResearchProject {title, budget, duration, phase, objectives})
(:Funding {amount, round, date, valuation})
(:Patent {id, title, filing_date, inventors, assignee})

// Critical Relationships
(:Company)-[:EMPLOYS {role, start_date, end_date}]->(:Person)
(:Company)-[:PARTNERS_WITH {type, start_date, contract_value, project}]->(:Company)
(:Company)-[:COMPETES_WITH {market_segment, overlap_score}]->(:Company)
(:Company)-[:AWARDED {date, value, role}]->(:Contract)
(:Company)-[:DEVELOPS {investment, role, timeline}]->(:Technology)
(:Company)-[:FUNDED_BY {amount, date, round}]->(:Company)
(:Person)-[:WORKED_AT {title, start_date, end_date}]->(:Company)
(:Person)-[:EDUCATED_AT {degree, year}]->(:Institution)
(:Agency)-[:FUNDS {amount, duration}]->(:Contract)
(:Agency)-[:SPONSORS {amount, duration}]->(:ResearchProject)
(:Contract)-[:REQUIRES]->(:Technology)
(:Technology)-[:DEPENDS_ON]->(:Technology)
(:Patent)-[:ASSIGNED_TO]->(:Company)
(:Person)-[:INVENTED]->(:Patent)
```

## Information Architecture & Data Flow

### 1. Entity Resolution Pipeline

```python
# Pseudo-code for entity resolution
class EntityResolver:
    def resolve_company(self, mention: str, context: dict) -> str:
        """
        Resolve company mentions to canonical entities
        'Lockheed' -> 'Lockheed Martin Corporation'
        'LMT' -> 'Lockheed Martin Corporation'
        """
        
    def resolve_person(self, name: str, title: str, company: str) -> str:
        """
        Resolve person mentions with context
        'John Smith, CEO at Acme Defense' -> unique person ID
        """
        
    def resolve_technology(self, tech_mention: str, context: str) -> str:
        """
        Resolve technology terms to standardized categories
        'AI', 'artificial intelligence', 'machine learning' -> 'Artificial Intelligence'
        """
```

### 2. Relationship Extraction Pipeline

```python
class RelationshipExtractor:
    def extract_partnerships(self, text: str, entities: dict) -> List[Relationship]:
        """Extract partnership relationships from text"""
        
    def extract_employment(self, text: str, entities: dict) -> List[Relationship]:
        """Extract employment relationships"""
        
    def extract_contracts(self, text: str, entities: dict) -> List[Relationship]:
        """Extract contract award relationships"""
        
    def extract_technology_development(self, text: str, entities: dict) -> List[Relationship]:
        """Extract technology development relationships"""
```

### 3. Temporal Relationship Management

**Key Principle**: All relationships have temporal properties and confidence scores.

```python
class TemporalRelationship:
    relationship_type: str
    source_entity: str
    target_entity: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]  # None = ongoing
    confidence_score: float  # 0.0 - 1.0
    evidence_sources: List[str]  # URLs, documents that support this
    last_updated: datetime
    
    def update_confidence(self, new_evidence: Evidence):
        """Update confidence based on new supporting evidence"""
        
    def mark_superseded(self, new_relationship: 'TemporalRelationship'):
        """Handle relationship changes (e.g., person changes jobs)"""
```

## Integration with Azure AI Search

### Hybrid Architecture: Graph + Search

**Azure AI Search**: Discovery and full-text search  
**Neo4j Graph**: Relationship queries and network analysis  
**Integration Layer**: Synchronizes between both systems

### Enhanced Azure Search Index Schema

```python
# Enhanced search index with graph-derived fields
search_index_fields = [
    # Original fields
    SearchField(name="id", type=SearchFieldDataType.String, key=True),
    SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
    SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
    
    # Enhanced entity fields
    SearchField(name="primary_companies", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    SearchField(name="secondary_companies", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    SearchField(name="key_personnel", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    SearchField(name="technologies", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    
    # Graph-derived relationship fields
    SearchField(name="company_partnerships", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    SearchField(name="competitive_landscape", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    SearchField(name="supply_chain_entities", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    SearchField(name="personnel_network", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
    
    # Relationship strength scores
    SearchField(name="entity_centrality_scores", type=SearchFieldDataType.Collection(SearchFieldDataType.Double), filterable=True),
    SearchField(name="relationship_strength_max", type=SearchFieldDataType.Double, sortable=True),
    
    # Graph-enhanced relevance
    SearchField(name="network_relevance_score", type=SearchFieldDataType.Double, sortable=True),
    SearchField(name="relationship_density", type=SearchFieldDataType.Double, sortable=True),
]
```

### Graph-Enhanced Document Processing

```python
class GraphEnhancedProcessor(ArticleProcessor):
    def __init__(self, graph_client: Neo4jClient):
        super().__init__()
        self.graph = graph_client
    
    def process_article(self, article: NewsArticle) -> Dict[str, Any]:
        # Standard processing
        processed = super().process_article(article)
        
        # Graph enhancement
        processed.update(self.enhance_with_graph_data(processed))
        
        return processed
    
    def enhance_with_graph_data(self, article_data: dict) -> dict:
        """Enhance article with graph-derived insights"""
        
        entities = article_data['entities']
        
        enhancements = {
            'company_partnerships': self.get_partnerships(entities['companies']),
            'competitive_landscape': self.get_competitors(entities['companies']),
            'supply_chain_entities': self.get_supply_chain(entities['companies']),
            'personnel_network': self.get_personnel_connections(entities['companies']),
            'entity_centrality_scores': self.calculate_centrality_scores(entities),
            'network_relevance_score': self.calculate_network_relevance(entities),
            'relationship_density': self.calculate_relationship_density(entities)
        }
        
        return enhancements
    
    def get_partnerships(self, companies: List[str]) -> List[str]:
        """Get known partnerships for mentioned companies"""
        query = """
        MATCH (c1:Company)-[:PARTNERS_WITH]-(c2:Company)
        WHERE c1.name IN $companies
        RETURN DISTINCT c2.name
        """
        return self.graph.execute_query(query, companies=companies)
    
    def calculate_network_relevance(self, entities: dict) -> float:
        """Calculate how connected these entities are in our knowledge graph"""
        query = """
        MATCH (e1)-[r]-(e2)
        WHERE e1.name IN $all_entities AND e2.name IN $all_entities
        RETURN count(r) as connection_count
        """
        all_entities = (entities.get('companies', []) + 
                       entities.get('agencies', []) + 
                       entities.get('technologies', []))
        
        result = self.graph.execute_query(query, all_entities=all_entities)
        return min(result[0]['connection_count'] / 10.0, 1.0)  # Normalize to 0-1
```

## Implementation Timeline & Strategy

### Stage 1 (0-3 months): Core Graph Infrastructure

**Month 1-2: Setup & Basic Entity Resolution**
```python
# 1. Neo4j setup and core schema
# 2. Basic entity resolution for companies/agencies
# 3. Simple relationship extraction (partnerships, contracts)
# 4. Integration with existing pipeline

docker run \
    --name neo4j \
    -p7474:7474 -p7687:7687 \
    -d \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/import:/var/lib/neo4j/import \
    -v $HOME/neo4j/plugins:/plugins \
    --env NEO4J_AUTH=neo4j/password \
    neo4j:latest
```

**Month 3: Azure Search Integration**
```python
# Enhanced search indexing with basic graph data
# Graph-derived fields in search results
# Basic network analysis for relevance scoring
```

### Stage 2 (3-9 months): Advanced Relationships

**Enhanced Relationship Extraction**
- Personnel movement tracking
- Technology dependency mapping
- Contract prime/sub relationships
- Board/investor connections

**Temporal Relationship Management**
- Relationship lifecycle tracking
- Confidence scoring updates
- Conflict resolution between sources

### Stage 3 (9-15 months): Network Intelligence

**Advanced Network Analysis**
- Community detection (identify clusters of related companies)
- Centrality analysis (identify key players)
- Path analysis (find connection paths between entities)
- Trend analysis (track relationship changes over time)

## Data Update Strategy

### 1. Incremental Updates
```python
class GraphUpdater:
    def update_entity(self, entity_data: dict):
        """Update entity properties, merge with existing"""
        
    def add_relationship(self, relationship: TemporalRelationship):
        """Add new relationship, check for conflicts"""
        
    def resolve_conflicts(self, conflicting_relationships: List[TemporalRelationship]):
        """Resolve conflicting information using confidence scores"""
```

### 2. Confidence-Based Merging
- **Source Authority**: Government contracts > Press releases > News articles
- **Recency**: More recent information has higher weight
- **Consistency**: Information confirmed by multiple sources gets boosted
- **Domain Expertise**: Defense-focused sources weighted higher for defense topics

### 3. Relationship Lifecycle Management
```python
# Example: Person changes jobs
old_relationship = Employment(person="John Smith", company="Acme Corp", end_date=None)
new_relationship = Employment(person="John Smith", company="Defense Inc", start_date="2024-01-15")

# System automatically:
# 1. Sets end_date on old relationship
# 2. Creates new relationship
# 3. Updates search index with current employment
# 4. Maintains historical record for analysis
```

## Performance & Scaling Considerations

### Query Optimization
- **Index Strategy**: Index on entity names, relationship types, date ranges
- **Query Patterns**: Optimize for common patterns (2-hop relationships, centrality, temporal queries)
- **Caching**: Cache frequently accessed relationship data

### Data Volume Management
- **Archival Strategy**: Archive old relationships while maintaining searchability
- **Partitioning**: Partition by relationship type or time period
- **Compression**: Use graph-specific compression for historical data

## Agent Integration Strategy

### Graph-Aware Agent Tools
```python
class GraphSearchTool:
    def find_partnerships(self, company: str, max_hops: int = 2) -> List[dict]:
        """Find partnership network around a company"""
        
    def find_personnel_connections(self, person: str) -> List[dict]:
        """Find professional network of a person"""
        
    def find_technology_suppliers(self, technology: str) -> List[dict]:
        """Find companies that supply components for a technology"""
        
    def analyze_competitive_landscape(self, companies: List[str]) -> dict:
        """Analyze competitive relationships and market positioning"""
```

### Multi-Team Graph Access
- **Team 1 (Technology Research)**: Focus on technology dependency graphs
- **Team 2 (Market Intelligence)**: Focus on company relationship networks  
- **Team 3 (Strategic Synthesis)**: Access to full graph for opportunity mapping

Each team gets specialized graph queries optimized for their analysis patterns, but all teams work from the same unified knowledge graph.

## Conclusion

**Implement graph database in Stage 1** as foundational infrastructure. The relationship data is as critical as the entity data for investment intelligence, and trying to retrofit it later would require significant rework of the search and agent systems.

The hybrid approach (Neo4j for relationships + Azure Search for discovery) gives you the best of both worlds: powerful relationship queries and fast full-text search, with the graph data enhancing search relevance and providing the foundation for sophisticated agent reasoning about entity networks.