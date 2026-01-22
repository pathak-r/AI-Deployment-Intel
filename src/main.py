"""
AI Deployment Intelligence Agent - Step 6: Storage Layer
=========================================================
Building on Step 5, we now add:
1. Supabase integration to store evaluated content
2. Persistence for discovered deployment stories
3. Deduplication via unique URL constraint
"""

import modal
import json

app = modal.App("ai-deployment-intel")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "anthropic>=0.40.0",
    "tavily-python>=0.5.0",
    "firecrawl>=1.0.0",
    "supabase>=2.0.0",
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-secret")],
)
def store_deployment(evaluation: dict, content_snippet: str = "") -> dict:
    """
    Store an evaluated deployment story in Supabase.
    
    Uses upsert to handle duplicates (same URL = update existing).
    """
    from supabase import create_client
    import os
    
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )
    
    url = evaluation.get("url", "")
    if not url:
        return {"success": False, "error": "No URL provided"}
    
    # Prepare the record
    record = {
        "url": url,
        "title": evaluation.get("title", ""),
        "company": evaluation.get("company"),
        "use_case": evaluation.get("use_case"),
        "is_deployment_story": evaluation.get("is_deployment_story", False),
        "confidence": evaluation.get("confidence"),
        "quality_score": evaluation.get("quality_score"),
        "deployment_stage": evaluation.get("deployment_stage"),
        "content_type": evaluation.get("content_type"),
        "technology_stack": evaluation.get("technology_stack", []),
        "results": evaluation.get("results", []),
        "lessons_learned": evaluation.get("lessons_learned", []),
        "content_snippet": content_snippet[:2000] if content_snippet else "",
    }
    
    print(f"Storing: {url[:60]}...")
    
    try:
        # Upsert: insert or update if URL exists
        result = supabase.table("deployments").upsert(
            record,
            on_conflict="url"
        ).execute()
        
        print(f"  ✓ Stored successfully")
        return {"success": True, "url": url}
        
    except Exception as e:
        print(f"  ✗ Storage error: {e}")
        return {"success": False, "error": str(e), "url": url}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-secret")],
)
def get_deployments(min_quality: int = 5, limit: int = 50) -> dict:
    """
    Retrieve stored deployment stories from Supabase.
    
    Filters by quality score and returns newest first.
    """
    from supabase import create_client
    import os
    
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )
    
    print(f"Fetching deployments (min quality: {min_quality}, limit: {limit})...")
    
    try:
        result = supabase.table("deployments")\
            .select("*")\
            .eq("is_deployment_story", True)\
            .gte("quality_score", min_quality)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        deployments = result.data
        print(f"  ✓ Found {len(deployments)} deployments")
        
        return {
            "success": True,
            "count": len(deployments),
            "deployments": deployments,
        }
        
    except Exception as e:
        print(f"  ✗ Fetch error: {e}")
        return {"success": False, "error": str(e), "deployments": []}


# ============ Previous functions (Steps 2-5) ============

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=120,
)
def evaluate_content(content: str, url: str = "", title: str = "") -> dict:
    """Use Claude to evaluate if content is a real AI deployment case study."""
    from anthropic import Anthropic
    
    client = Anthropic()
    
    if not content or len(content) < 300:
        return {
            "url": url,
            "is_deployment_story": False,
            "reason": "Content too short or empty",
            "quality_score": 0,
        }
    
    content_truncated = content[:12000] if len(content) > 12000 else content
    
    print(f"Evaluating: {title[:60] or url[:60]}...")
    
    evaluation_prompt = f"""Analyze this content and determine if it describes a real-world AI/LLM deployment or case study.

URL: {url}
TITLE: {title}

CONTENT:
{content_truncated}

Evaluate based on these criteria:
1. SPECIFICITY: Does it name a real company and describe concrete implementation details?
2. PRACTITIONER VOICE: Is it written by someone who built/deployed the system?
3. DEPLOYMENT EVIDENCE: Is this in production (not just a POC or announcement)?
4. QUANTIFIED RESULTS: Are there metrics, percentages, or measurable outcomes?
5. LESSONS LEARNED: Does it share what went wrong or what they'd do differently?

Respond with a JSON object (no markdown, just raw JSON):
{{
    "is_deployment_story": true or false,
    "confidence": 0.0 to 1.0,
    "reason": "Brief explanation of your assessment",
    "company": "Company name or null if not found",
    "use_case": "Brief description of what they built (1-2 sentences)",
    "technology_stack": ["List", "of", "technologies", "mentioned"],
    "results": ["List of quantified outcomes if mentioned"],
    "lessons_learned": ["Key learnings or insights"],
    "deployment_stage": "production" or "pilot" or "poc" or "unknown",
    "content_type": "blog_post" or "case_study" or "talk_transcript" or "interview" or "other",
    "quality_score": 1 to 10
}}

Be strict. Marketing fluff, announcements without details, and speculation should get is_deployment_story=false.
Only return valid JSON, nothing else."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": evaluation_prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        evaluation = json.loads(response_text)
        evaluation["url"] = url
        evaluation["title"] = title
        
        if evaluation.get("is_deployment_story"):
            print(f"  ✓ IS deployment story (score: {evaluation.get('quality_score', 'N/A')})")
        else:
            print(f"  ✗ NOT a deployment story: {evaluation.get('reason', 'No reason')[:60]}")
        
        return evaluation
        
    except json.JSONDecodeError as e:
        return {"url": url, "is_deployment_story": False, "reason": f"JSON parse error: {e}", "quality_score": 0}
    except Exception as e:
        return {"url": url, "is_deployment_story": False, "reason": f"Evaluation failed: {e}", "quality_score": 0}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("firecrawl-secret")],
    timeout=120,
)
def fetch_content(url: str) -> dict:
    """Fetch full content from a URL using Firecrawl."""
    from firecrawl import Firecrawl
    import os
    
    client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    
    print(f"Fetching: {url}")
    
    try:
        result = client.scrape(url=url, formats=["markdown"])
        
        markdown_content = result.markdown or ""
        title = ""
        description = ""
        if result.metadata:
            title = result.metadata.title or ""
            description = result.metadata.description or ""
        
        print(f"  Title: {title[:60]}")
        print(f"  Content length: {len(markdown_content)} characters")
        
        return {
            "url": url,
            "success": True,
            "title": title,
            "description": description,
            "content": markdown_content,
            "content_length": len(markdown_content),
        }
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return {"url": url, "success": False, "error": str(e), "content": "", "content_length": 0}


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
    
    response = client.search(query=query, search_depth="advanced", max_results=max_results)
    
    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:500],
        })
        print(f"  Found: {item.get('title', 'No title')[:60]}...")
    
    return {"query": query, "num_results": len(results), "results": results}


@app.function()
def hello():
    """Original hello function."""
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


@app.local_entrypoint()
def main():
    """Test the full pipeline: search → fetch → evaluate → store."""
    print("=" * 60)
    print("AI Deployment Intel - Step 6: Full Pipeline Test")
    print("=" * 60)
    
    # Step 1: Search
    print("\n[1/4] Searching...")
    search_result = search_deployments.remote("LLM deployment case study production", max_results=2)
    
    if search_result["num_results"] == 0:
        print("No results found")
        return
    
    # Process first result
    first_result = search_result["results"][0]
    url = first_result["url"]
    
    # Step 2: Fetch
    print(f"\n[2/4] Fetching: {url[:50]}...")
    fetch_result = fetch_content.remote(url)
    
    if not fetch_result["success"]:
        print(f"Fetch failed: {fetch_result.get('error')}")
        return
    
    # Step 3: Evaluate
    print(f"\n[3/4] Evaluating...")
    evaluation = evaluate_content.remote(
        content=fetch_result["content"],
        url=url,
        title=fetch_result["title"],
    )
    
    # Step 4: Store (only if it's a deployment story)
    print(f"\n[4/4] Storing...")
    if evaluation.get("is_deployment_story") and evaluation.get("quality_score", 0) >= 5:
        store_result = store_deployment.remote(
            evaluation=evaluation,
            content_snippet=fetch_result["content"][:2000],
        )
        print(f"Store result: {store_result}")
    else:
        print(f"Skipping storage - not a quality deployment story")
        print(f"  Reason: {evaluation.get('reason', 'N/A')}")
    
    # Show final evaluation
    print(f"\n{'=' * 60}")
    print("EVALUATION:")
    print(json.dumps(evaluation, indent=2))
