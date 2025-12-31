# Tool endpoints
TOOLS_SERVER_BASE_ENDPOINT_URL = [
    "<your_docker_url_endpoint1>",
]

# Whether to use cache for web-based tools, such as web_search, fetch_web_page, browse_url, visit, etc.  
WEB_BASED_TOOLS_USE_CACHE = True    

# Whether to return in JSON format or natural language format
USE_TONGYI_FORMAT_RETURN = True

# Maximum wait time (in seconds) for vllm and aihubmix API
CLIENTTIMEOUT = 900

# aihubmix API key
AIHUBMIX_KEY = "<your_aihubmix_key>"
# azure API key
AZURE_KEY = "<your_azure_key>"
# volcano API key
volcano_KEY = "<your_volcano_key>"

# Online platform names
ONLINE_PLATFORM = ["aihubmix", "aihubmix_claude", "azure", "volcano"]