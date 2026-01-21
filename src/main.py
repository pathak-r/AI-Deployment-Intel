"""
AI Deployment Intelligence Agent - Step 5: Evaluate Layer
==========================================================
Building on Step 4, we now add:
1. Claude-powered content evaluation
2. Structured data extraction from articles
3. Quality scoring to filter signal from noise
"""

import modal
import json

app = modal.App("ai-deployment-intel")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "anthropic>=0.40.0",
    "tavily-python>=0.5.0",
    "firecrawl>=1.0.0",
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=120,
)
def evaluate_content(content: str, url: str = "", title: str = "") -> dict:
    """
    Use Claude to evaluate if content is a real AI deployment case study.
    
    Returns structured evaluation with:
    - is_deployment_story: bool
    - company, use_case, results, lessons_learned
    - quality_score: 1-10
    """
    from anthropic import Anthropic
    
    client = Anthropic()
    
    # Don't evaluate if content is too short
    if not content or len(content) < 300:
        return {
            "url": url,
            "is_deployment_story": False,
            "reason": "Content too short or empty",
            "quality_score": 0,
        }
    
    # Truncate very long content to save tokens
    content_truncated = content[:12000] if len(content) > 12000 else content
    
    print(f"Evaluating: {title[:60] or url[:60]}...")
    print(f"  Content length: {len(content_truncated)} chars")
    
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
        
        # Clean up response if it has markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        evaluation = json.loads(response_text)
        evaluation["url"] = url
        evaluation["title"] = title
        
        # Log result
        if evaluation.get("is_deployment_story"):
            print(f"  ✓ IS deployment story (score: {evaluation.get('quality_score', 'N/A')})")
            print(f"    Company: {evaluation.get('company', 'Unknown')}")
            print(f"    Use case: {evaluation.get('use_case', 'N/A')[:60]}...")
        else:
            print(f"  ✗ NOT a deployment story: {evaluation.get('reason', 'No reason')[:60]}")
        
        return evaluation
        
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON parse error: {e}")
        return {
            "url": url,
            "is_deployment_story": False,
            "reason": f"Failed to parse evaluation response: {e}",
            "quality_score": 0,
        }
    except Exception as e:
        print(f"  ✗ Evaluation error: {e}")
        return {
            "url": url,
            "is_deployment_story": False,
            "reason": f"Evaluation failed: {e}",
            "quality_score": 0,
        }


# ============ Previous functions (Steps 2-4) ============

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
        return {
            "url": url,
            "success": False,
            "error": str(e),
            "content": "",
            "content_length": 0,
        }


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


@app.function()
def hello():
    """Original hello function."""
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


@app.local_entrypoint()
def main():
    """Test the full search → fetch → evaluate flow."""
    print("=" * 60)
    print("AI Deployment Intel - Step 5: Evaluate Layer Test")
    print("=" * 60)
    
    # Test with a known good URL
    test_url = "https://www.zenml.io/blog/llmops-in-production-457-case-studies-of-what-actually-works"
    
    # Fetch content
    print(f"\n[1] Fetching content...")
    fetch_result = fetch_content.remote(test_url)
    
    if not fetch_result["success"]:
        print(f"Fetch failed: {fetch_result.get('error')}")
        return
    
    # Evaluate content
    print(f"\n[2] Evaluating content...")
    evaluation = evaluate_content.remote(
        content=fetch_result["content"],
        url=test_url,
        title=fetch_result["title"],
    )
    
    # Show results
    print(f"\n{'=' * 60}")
    print("EVALUATION RESULT:")
    print(f"{'=' * 60}")
    print(json.dumps(evaluation, indent=2))
