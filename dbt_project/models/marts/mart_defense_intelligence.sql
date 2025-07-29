{{ config(
    materialized='table',
    tags=['marts', 'defense']
) }}

with articles_with_entities as (
    select * from {{ ref('int_articles_with_entities') }}
),

defense_focused as (
    select
        article_id,
        title_clean as title,
        description_clean as description,
        content_clean as content,
        published_at,
        source_name_standardized as source_name,
        url,
        author,
        companies,
        agencies,
        technologies,
        funding_mentions,
        contract_mentions,
        final_relevance_score,
        
        -- Defense categorization
        case 
            when final_relevance_score >= 5.0 then 'High Priority'
            when final_relevance_score >= 2.0 then 'Medium Priority'
            when final_relevance_score >= 0.5 then 'Low Priority'
            else 'Background'
        end as priority_level,
        
        -- Technology categories
        case 
            when array_to_string(technologies, ',') ilike any(array['%ai%', '%artificial intelligence%', '%machine learning%']) 
            then true else false 
        end as has_ai_tech,
        
        case 
            when array_to_string(technologies, ',') ilike any(array['%cyber%', '%security%']) 
            then true else false 
        end as has_cyber_tech,
        
        case 
            when array_to_string(technologies, ',') ilike any(array['%space%', '%satellite%', '%orbital%']) 
            then true else false 
        end as has_space_tech,
        
        case 
            when array_to_string(technologies, ',') ilike any(array['%autonomous%', '%unmanned%', '%drone%']) 
            then true else false 
        end as has_autonomous_tech,
        
        ingestion_timestamp
        
    from articles_with_entities
    where final_relevance_score > 0  -- Only include articles with some defense relevance
)

select * from defense_focused
