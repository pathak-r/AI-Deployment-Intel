"""
AI Deployment Intelligence Agent - Step 3: Search Layer
========================================================
Building on Step 2, we now add:
1. Tavily search integration
2. Queries designed to find AI deployment case studies
3. See raw search results
"""

import modal

app = modal.App("ai-deployment-intel")

# Image now includes both anthropic and tavily
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "anthropic>=0.40.0",
    "tavily-python>=0.5.0",
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("tavily-secret")],
)
def search_deployments(query: str, max_results: int = 5) -> dict:
    """
    Search for AI deployment content using Tavily.
    
    Tavily is a search API designed for AI agents - it returns
    clean, structured results optimized for LLM consumption.
    """
    from tavily import TavilyClient
    import os
    
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    
    print(f"Searching for: {query}")
    
    response = client.search(
        query=query,
        search_depth="advanced",  # More thorough search
        max_results=max_results,
        include_answer=False,  # We don't need Tavily's AI summary
    )
    
    # Extract and structure the results
    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:500],  # First 500 chars
        })
        print(f"  Found: {item.get('title', 'No title')[:60]}...")
    
    return {
        "query": query,
        "num_results": len(results),
        "results": results,
    }


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("tavily-secret")],
)
def search_with_multiple_queries(queries: list[str] = None) -> dict:
    """
    Run multiple search queries designed to find AI deployment stories.
    
    These queries are crafted to find real-world case studies,
    not announcements or speculation.
    """
    from tavily import TavilyClient
    import os
    
    # Default queries - designed to find real deployment stories
    default_queries = [
        '"we deployed" LLM production',
        '"lessons learned" "AI agent" production',
        '"case study" "generative AI" enterprise results',
    ]
    
    queries = queries or default_queries
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    
    all_results = []
    seen_urls = set()  # Avoid duplicates across queries
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print('='*50)
        
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
            )
            
            for item in response.get("results", []):
                url = item.get("url", "")
                
                # Skip if we've seen this URL
                if url in seen_urls:
                    print(f"  [SKIP] Duplicate: {url[:50]}...")
                    continue
                    
                seen_urls.add(url)
                
                result = {
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("content", "")[:500],
                    "source_query": query,
                }
                all_results.append(result)
                print(f"  [NEW] {item.get('title', 'No title')[:60]}...")
                
        except Exception as e:
            print(f"  [ERROR] Search failed: {e}")
            continue
    
    print(f"\n{'='*50}")
    print(f"Total unique results: {len(all_results)}")
    print('='*50)
    
    return {
        "queries_run": queries,
        "total_results": len(all_results),
        "results": all_results,
    }


# Keep previous functions
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
)
def call_claude(prompt: str) -> dict:
    """Call Claude API (from Step 2)"""
    from anthropic import Anthropic
    
    client = Anthropic()
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {
        "status": "success",
        "response": response.content[0].text,
    }


@app.function()
def hello():
    """Original hello function"""
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


@app.local_entrypoint()
def main():
    """
    Test the search functionality.
    """
    print("=" * 60)
    print("AI Deployment Intel - Step 3: Search Layer Test")
    print("=" * 60)
    
    # Test single search
    print("\n[Test 1] Single search query...")
    result = search_deployments.remote(
        query='"deployed" "LLM" production case study',
        max_results=3
    )
    print(f"Found {result['num_results']} results")
    for r in result['results']:
        print(f"  - {r['title'][:50]}...")
    
    # Test multiple queries
    print("\n[Test 2] Multiple queries...")
    multi_result = search_with_multiple_queries.remote()
    print(f"Total unique results: {multi_result['total_results']}")
