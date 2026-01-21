"""
AI Deployment Intelligence Agent - Step 4: Fetch Layer
=======================================================
Building on Step 3, we now add:
1. Firecrawl integration to fetch full page content
2. Convert web pages to clean markdown
3. Prepare content for evaluation
"""

import modal

app = modal.App("ai-deployment-intel")

# Image now includes anthropic, tavily, and firecrawl
# Note: using 'firecrawl' package (not 'firecrawl-py')
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "anthropic>=0.40.0",
    "tavily-python>=0.5.0",
    "firecrawl>=1.0.0",  # Updated package name
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("firecrawl-secret")],
    timeout=120,
)
def fetch_content(url: str) -> dict:
    """
    Fetch full content from a URL using Firecrawl.
    
    Firecrawl handles:
    - JavaScript rendering (SPAs, dynamic content)
    - Removing ads, navigation, footers
    - Extracting main content as clean markdown
    """
    from firecrawl import Firecrawl
    import os
    
    # New API: use Firecrawl class (not FirecrawlApp)
    client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    
    print(f"Fetching: {url}")
    
    try:
        # New API: use scrape() method with formats as direct parameter
        result = client.scrape(
            url=url,
            formats=["markdown"],
        )
        
        markdown_content = result.get("markdown", "")
        metadata = result.get("metadata", {})
        
        print(f"  Title: {metadata.get('title', 'No title')[:60]}")
        print(f"  Content length: {len(markdown_content)} characters")
        
        return {
            "url": url,
            "success": True,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "content": markdown_content,
            "content_length": len(markdown_content),
        }
        
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return {
            "url": url,
            "success": False,
            "error": str(e),
            "content": "",
            "content_length": 0,
        }


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("firecrawl-secret")],
    timeout=300,
)
def fetch_multiple(urls: list[str]) -> dict:
    """
    Fetch content from multiple URLs.
    Returns successful fetches and tracks failures.
    """
    from firecrawl import Firecrawl
    import os
    
    client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    
    results = []
    success_count = 0
    fail_count = 0
    
    for url in urls:
        print(f"\nFetching: {url[:60]}...")
        
        try:
            result = client.scrape(
                url=url,
                formats=["markdown"],
            )
            
            markdown_content = result.get("markdown", "")
            metadata = result.get("metadata", {})
            
            results.append({
                "url": url,
                "success": True,
                "title": metadata.get("title", ""),
                "content": markdown_content,
                "content_length": len(markdown_content),
            })
            success_count += 1
            print(f"  ✓ Got {len(markdown_content)} chars")
            
        except Exception as e:
            results.append({
                "url": url,
                "success": False,
                "error": str(e),
                "content": "",
            })
            fail_count += 1
            print(f"  ✗ Failed: {e}")
    
    print(f"\n{'='*50}")
    print(f"Fetched {success_count}/{len(urls)} successfully")
    print(f"{'='*50}")
    
    return {
        "total": len(urls),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    }


# ============ Previous functions (Steps 2-3) ============

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("tavily-secret")],
)
def search_deployments(query: str, max_results: int = 5) -> dict:
    """Search for AI deployment content using Tavily."""
    from tavily import TavilyClient
    import os
    
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    
    print(f"Searching for: {query}")
    
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
    )
    
    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:500],
        })
        print(f"  Found: {item.get('title', 'No title')[:60]}...")
    
    return {
        "query": query,
        "num_results": len(results),
        "results": results,
    }


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
)
def call_claude(prompt: str) -> dict:
    """Call Claude API."""
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
    """Original hello function."""
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


@app.local_entrypoint()
def main():
    """Test the fetch functionality."""
    print("=" * 60)
    print("AI Deployment Intel - Step 4: Fetch Layer Test")
    print("=" * 60)
    
    # Test URL - a real AI deployment article
    test_url = "https://www.zenml.io/blog/llmops-in-production-457-case-studies-of-what-actually-works"
    
    print(f"\nFetching: {test_url}")
    result = fetch_content.remote(test_url)
    
    if result["success"]:
        print(f"\n✓ Success!")
        print(f"  Title: {result['title']}")
        print(f"  Length: {result['content_length']} characters")
        print(f"\n  First 500 chars of content:")
        print(f"  {'-'*40}")
        print(f"  {result['content'][:500]}")
    else:
        print(f"\n✗ Failed: {result.get('error')}")
