{{ config(
    materialized='view',
    tags=['intermediate', 'entities']
) }}

with articles as (
    select * from {{ ref('stg_newsapi_articles') }}
),

-- This will be populated by our Python processing
entity_extractions as (
    select
        article_id,
        companies,
        agencies,
        technologies,
        funding_mentions,
        contract_mentions
    from {{ source('raw_data', 'article_entities') }}
),

combined as (
    select
        a.*,
        e.companies,
        e.agencies,
        e.technologies,
        e.funding_mentions,
        e.contract_mentions,
        
        -- Calculate relevance scores
        (
            coalesce(array_length(e.companies, 1), 0) * 0.2 +
            coalesce(array_length(e.agencies, 1), 0) * 0.3 +
            coalesce(array_length(e.technologies, 1), 0) * 0.1 +
            coalesce(array_length(e.funding_mentions, 1), 0) * 0.4 +
            coalesce(array_length(e.contract_mentions, 1), 0) * 0.3
        ) as base_relevance_score,
        
        -- Source authority weighting
        case 
            when source_name_standardized in ('Reuters', 'Associated Press', 'Wall Street Journal') 
            then 1.2 
            else 1.0 
        end as source_authority_multiplier
        
    from articles a
    left join entity_extractions e
        on a.article_id = e.article_id
)

select *,
    least(base_relevance_score * source_authority_multiplier, 10.0) as final_relevance_score
from combined
