# config/newsapi_topics.py
"""NewsAPI.ai Topic Configuration"""

TEST_TOPIC = {
    "defense_technology": {
        "uri": "3d9d3ac4-4ee8-479a-bb16-040d8f7f13bd",  # e.g., "240f6a12-b9d8-40a6-b1c6-a220e31d08de"
        "name": "DefenseNews",
        "description": "DAll Topics Test",
        "max_articles": 100,
        "sort_by": "fq"  # or "fq" for relevance
    }
}

# Topic URIs from NewsAPI.ai dashboard
# Replace these with your actual topic URIs
TOPICS = {
    "defense_technology": {
        "uri": "3d9d3ac4-4ee8-479a-bb16-040d8f7f13bd",  # e.g., "240f6a12-b9d8-40a6-b1c6-a220e31d08de"
        "name": "DefenseNews",
        "description": "DAll Topics Test",
        "max_articles": 100,
        "sort_by": "fq"  # or "fq" for relevance
    },
    # "darpa_contracts": {
    #     "uri": "YOUR_DARPA_CONTRACTS_TOPIC_URI",
    #     "name": "DARPA Contracts",
    #     "description": "DARPA funding and contract awards",
    #     "max_articles": 100,
    #     "sort_by": "fq"
    # },
    # "autonomous_systems": {
    #     "uri": "YOUR_AUTONOMOUS_SYSTEMS_TOPIC_URI",
    #     "name": "Autonomous Systems",
    #     "description": "Autonomous and unmanned systems",
    #     "max_articles": 100,
    #     "sort_by": "fq"
    # },
    # "maintenance_tech": {
    #     "uri": "YOUR_MAINTENANCE_TECH_TOPIC_URI",
    #     "name": "Maintenance Technology",
    #     "description": "Automated maintenance and inspection",
    #     "max_articles": 100,
    #     "sort_by": "fq"
    # }
}

# Schedule configuration
TOPIC_SCHEDULES = {
    "alltopics_test": "0 8 * * *",  # Once daily at 8 AM
    # "darpa_contracts": "0 8 * * *",  # Once daily at 8 AM
    # "autonomous_systems": "0 8 * * *",  # Once daily at 8 AM
    # "maintenance_tech": "0 8 * * *"  # Once daily at 8 AM
}