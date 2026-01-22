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
def store_deployment(
    url: str,
    title: str = "",
    company: str = None,
    use_case: str = None,
    is_deployment_story: bool = False,
    confidence: float = 0.0,
    quality_score: int = 0,
    deployment_stage: str = None,
    content_type: str = None,
    technology_stack: list = None,
    results: list = None,
    lessons_learned: list = None,
    content_snippet: str = "",
) -> dict:
    """
    Store a deployment story in Supabase.
    Individual parameters instead of dict for Modal UI compatibility.
    """
    from supabase import create_client
    import os
    
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )
    
    if not url:
        return {"success": False, "error": "No URL provided"}
    
    record = {
        "url": url,
        "title": title,
        "company": company,
        "use_case": use_case,
        "is_deployment_story": is_deployment_story,
        "confidence": confidence,
        "quality_score": quality_score,
        "deployment_stage": deployment_stage,
        "content_type": content_type,
        "technology_stack": technology_stack or [],
        "results": results or [],
        "lessons_learned": lessons_learned or [],
        "content_snippet": content_snippet[:2000] if content_snippet else "",
    }
    
    print(f"Storing: {url[:60]}...")
    
    try:
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
    """Retrieve stored deployment stories from Supabase."""
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


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("tavily-secret"),
        modal.Secret.from_name("firecrawl-secret"),
        modal.Secret.from_name("anthropic-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
    timeout=300,
)
def run_pipeline(query: str = "LLM deployment case study production", max_results: int = 2) -> dict:
    """
    Run the full pipeline: search → fetch → evaluate → store.
    This is testable from Modal's "Try It" UI.
    """
    from tavily import TavilyClient
    from firecrawl import Firecrawl
    from anthropic import Anthropic
    from supabase import create_client
    import os
    
    stats = {
        "searched": 0,
        "fetched": 0,
        "evaluated": 0,
        "stored": 0,
        "errors": [],
    }
    
    print("=" * 60)
    print("AI Deployment Intel - Full Pipeline Run")
    print("=" * 60)
    
    # Initialize clients
    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    firecrawl = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    anthropic = Anthropic()
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
    # Step 1: Search
    print(f"\n[1/4] Searching: {query}")
    try:
        search_response = tavily.search(query=query, search_depth="advanced", max_results=max_results)
        search_results = search_response.get("results", [])
        stats["searched"] = len(search_results)
        print(f"  Found {len(search_results)} results")
    except Exception as e:
        stats["errors"].append(f"Search error: {e}")
        return stats
    
    # Process each result
    for item in search_results:
        url = item.get("url", "")
        title = item.get("title", "")
        
        print(f"\n{'─' * 40}")
        print(f"Processing: {title[:50]}...")
        
        # Step 2: Fetch
        print(f"  [2/4] Fetching...")
        try:
            fetch_result = firecrawl.scrape(url=url, formats=["markdown"])
            content = fetch_result.markdown or ""
            if fetch_result.metadata:
                title = fetch_result.metadata.title or title
            stats["fetched"] += 1
            print(f"    Got {len(content)} chars")
        except Exception as e:
            stats["errors"].append(f"Fetch error for {url}: {e}")
            print(f"    ✗ Fetch failed: {e}")
            continue
        
        if len(content) < 300:
            print(f"    ✗ Content too short, skipping")
            continue
        
        # Step 3: Evaluate
        print(f"  [3/4] Evaluating...")
        try:
            content_truncated = content[:12000]
            
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
    "reason": "Brief explanation",
    "company": "Company name or null",
    "use_case": "Brief description (1-2 sentences)",
    "technology_stack": ["List", "of", "technologies"],
    "results": ["Quantified outcomes"],
    "lessons_learned": ["Key learnings"],
    "deployment_stage": "production" or "pilot" or "poc" or "unknown",
    "content_type": "blog_post" or "case_study" or "talk_transcript" or "other",
    "quality_score": 1 to 10
}}

Be strict. Only return valid JSON."""

            response = anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": evaluation_prompt}]
            )
            
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            evaluation = json.loads(response_text)
            stats["evaluated"] += 1
            
            is_story = evaluation.get("is_deployment_story", False)
            quality = evaluation.get("quality_score", 0)
            print(f"    Is deployment story: {is_story}, Quality: {quality}")
            
        except Exception as e:
            stats["errors"].append(f"Evaluation error for {url}: {e}")
            print(f"    ✗ Evaluation failed: {e}")
            continue
        
        # Step 4: Store (only quality stories)
        if is_story and quality >= 5:
            print(f"  [4/4] Storing...")
            try:
                record = {
                    "url": url,
                    "title": title,
                    "company": evaluation.get("company"),
                    "use_case": evaluation.get("use_case"),
                    "is_deployment_story": True,
                    "confidence": evaluation.get("confidence"),
                    "quality_score": quality,
                    "deployment_stage": evaluation.get("deployment_stage"),
                    "content_type": evaluation.get("content_type"),
                    "technology_stack": evaluation.get("technology_stack", []),
                    "results": evaluation.get("results", []),
                    "lessons_learned": evaluation.get("lessons_learned", []),
                    "content_snippet": content[:2000],
                }
                
                supabase.table("deployments").upsert(record, on_conflict="url").execute()
                stats["stored"] += 1
                print(f"    ✓ Stored!")
                
            except Exception as e:
                stats["errors"].append(f"Storage error for {url}: {e}")
                print(f"    ✗ Storage failed: {e}")
        else:
            print(f"  [4/4] Skipping storage (quality too low or not a deployment story)")
    
    print(f"\n{'=' * 60}")
    print(f"Pipeline complete!")
    print(f"  Searched: {stats['searched']}")
    print(f"  Fetched: {stats['fetched']}")
    print(f"  Evaluated: {stats['evaluated']}")
    print(f"  Stored: {stats['stored']}")
    if stats["errors"]:
        print(f"  Errors: {len(stats['errors'])}")
    print("=" * 60)
    
    return stats


@app.function()
def hello():
    """Original hello function."""
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


@app.local_entrypoint()
def main():
    """Run pipeline from command line."""
    result = run_pipeline.remote()
    print(json.dumps(result, indent=2))
