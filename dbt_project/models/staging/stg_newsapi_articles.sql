{{ config(
    materialized='view',
    tags=['staging', 'newsapi']
) }}

with source_data as (
    select
        article_id,
        title,
        content,
        description,
        published_at,
        source_name,
        url,
        author,
        url_to_image,
        search_terms,
        ingestion_timestamp
    from {{ source('raw_data', 'newsapi_articles') }}
),

cleaned as (
    select
        article_id,
        
        -- Clean title
        trim(regexp_replace(title, '\s+', ' ', 'g')) as title_clean,
        
        -- Clean content
        case 
            when content is not null 
            then trim(regexp_replace(content, '\s+', ' ', 'g'))
            else null 
        end as content_clean,
        
        -- Clean description
        case 
            when description is not null 
            then trim(regexp_replace(description, '\s+', ' ', 'g'))
            else null 
        end as description_clean,
        
        published_at,
        
        -- Standardize source names
        case 
            when lower(source_name) like '%reuters%' then 'Reuters'
            when lower(source_name) like '%associated press%' then 'Associated Press'
            when lower(source_name) like '%wall street journal%' then 'Wall Street Journal'
            when lower(source_name) like '%defense%news%' then 'Defense News'
            else initcap(source_name)
        end as source_name_standardized,
        
        url,
        author,
        url_to_image,
        search_terms,
        ingestion_timestamp
        
    from source_data
    where title is not null
      and url is not null
      and published_at is not null
)

select * from cleaned
