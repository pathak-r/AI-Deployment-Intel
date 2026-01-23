"""
AI Deployment Intelligence Agent - Step 7: Static Site Generation
==================================================================
Building on Step 6, we now add:
1. Generate a static HTML page from Supabase data
2. Clean, readable design for deployment stories
3. Ready to push to GitHub Pages
"""

import modal
import json
from datetime import datetime

app = modal.App("ai-deployment-intel")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        "anthropic>=0.40.0",
        "tavily-python>=0.5.0",
        "firecrawl>=1.0.0",
        "supabase>=2.0.0",
    )
)

# Search query bank for diverse content discovery
SEARCH_QUERY_BANK = [
    # LLM specific
    "LLM deployment production lessons learned 2025",
    "GPT-4 enterprise implementation case study",
    "Claude API production deployment",
    "open source LLM deployment production",
    "fine-tuning LLM production challenges",
    "LLM serving infrastructure production",
    "prompt engineering production systems",

    # RAG and retrieval
    "RAG implementation production enterprise",
    "vector database deployment production scale",
    "semantic search production deployment",
    "document AI production deployment",

    # Industry specific
    "AI deployment healthcare case study",
    "machine learning fintech production",
    "recommendation system e-commerce scale",
    "computer vision manufacturing deployment",
    "NLP production deployment enterprise",

    # Technical challenges
    "AI model monitoring production",
    "LLM cost optimization production",
    "ML inference latency optimization",
    "model serving infrastructure production",
    "AI reliability production deployment",

    # Specific use cases
    "chatbot deployment enterprise lessons",
    "AI code assistant production deployment",
    "fraud detection ML production",
    "AI agent deployment production",

    # Scaling & operations
    "scaling machine learning production 2026",
    "MLOps best practices production",
    "AI infrastructure production case study",
    "model performance production monitoring",
    "multimodal AI deployment production",
]


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-secret")],
)
def generate_site(min_quality: int = 5) -> dict:
    """
    Generate a static HTML site from stored deployments.
    Returns the HTML content ready to be saved/pushed.
    """
    from supabase import create_client
    import os
    
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )
    
    # Fetch all quality deployments
    print("Fetching deployments from Supabase...")
    result = supabase.table("deployments")\
        .select("*")\
        .eq("is_deployment_story", True)\
        .gte("quality_score", min_quality)\
        .order("quality_score", desc=True)\
        .execute()
    
    deployments = result.data
    print(f"Found {len(deployments)} deployments")
    
    # Generate HTML
    html = generate_html(deployments)
    
    return {
        "success": True,
        "deployment_count": len(deployments),
        "html": html,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("supabase-secret"),
        modal.Secret.from_name("github-secret"),
    ],
    timeout=300,
)
def publish_site(min_quality: int = 5) -> dict:
    """
    Generate the static site and push it to GitHub Pages.
    Clones repo, generates HTML, commits to /docs, and pushes.
    """
    import os
    import tempfile
    import subprocess
    from pathlib import Path

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        return {"success": False, "error": "GITHUB_TOKEN not found in secrets"}

    repo_url = f"https://{github_token}@github.com/pathak-r/ai-deployment-intel.git"

    # Generate the site HTML
    print("Generating site HTML...")
    site_result = generate_site.local(min_quality=min_quality)

    if not site_result.get("success"):
        return {"success": False, "error": "Failed to generate site"}

    html_content = site_result["html"]
    deployment_count = site_result["deployment_count"]

    # Use temporary directory for git operations
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Cloning repository to {tmpdir}...")

        try:
            # Clone the repo
            print("Cloning repository...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, tmpdir],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return {"success": False, "error": f"Git clone failed: {result.stderr}"}

            # Create docs directory
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir(exist_ok=True)

            # Write HTML file
            index_path = docs_dir / "index.html"
            index_path.write_text(html_content)
            print(f"Wrote {len(html_content)} bytes to docs/index.html")

            # Configure git
            subprocess.run(
                ["git", "config", "user.name", "AI Deployment Agent"],
                cwd=tmpdir,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "bot@ai-deployment-intel.com"],
                cwd=tmpdir,
                check=True,
            )

            # Check if there are any changes
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            if not status_result.stdout.strip():
                print("No changes detected - site is already up to date")
                return {
                    "success": True,
                    "deployment_count": deployment_count,
                    "commit_message": "No changes",
                    "site_url": "https://pathak-r.github.io/ai-deployment-intel/",
                }

            # Add, commit, and push
            subprocess.run(["git", "add", "docs/index.html"], cwd=tmpdir, check=True)

            commit_msg = f"Update site - {deployment_count} deployments - {datetime.utcnow().strftime('%Y-%m-%d')}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=tmpdir,
                check=True,
                capture_output=True,
            )

            print("Pushing to GitHub...")
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            if push_result.returncode != 0:
                return {"success": False, "error": f"Git push failed: {push_result.stderr}"}

            print("Successfully pushed to GitHub!")
            return {
                "success": True,
                "deployment_count": deployment_count,
                "commit_message": commit_msg,
                "site_url": "https://pathak-r.github.io/ai-deployment-intel/",
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"Git command failed: {e.cmd}. Error: {e.stderr if e.stderr else e.stdout}"
            print(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}


def generate_html(deployments: list) -> str:
    """Generate the HTML page content."""
    
    generated_date = datetime.utcnow().strftime("%B %d, %Y")
    
    # Build deployment cards
    cards_html = ""
    for d in deployments:
        company = d.get("company") or "Unknown Company"
        use_case = d.get("use_case") or "AI Deployment"
        url = d.get("url", "#")
        title = d.get("title") or use_case
        quality = d.get("quality_score", 0)
        stage = d.get("deployment_stage", "unknown")
        
        # Technology tags
        tech_stack = d.get("technology_stack", [])
        if isinstance(tech_stack, str):
            tech_stack = json.loads(tech_stack) if tech_stack else []
        tech_tags = "".join(f'<span class="tag">{tech}</span>' for tech in tech_stack[:5])
        
        # Results list
        results = d.get("results", [])
        if isinstance(results, str):
            results = json.loads(results) if results else []
        results_html = ""
        if results:
            results_items = "".join(f"<li>{r}</li>" for r in results[:3])
            results_html = f'<ul class="results">{results_items}</ul>'
        
        # Lessons learned
        lessons = d.get("lessons_learned", [])
        if isinstance(lessons, str):
            lessons = json.loads(lessons) if lessons else []
        lessons_html = ""
        if lessons:
            lessons_html = f'<p class="lesson">💡 {lessons[0][:150]}{"..." if len(lessons[0]) > 150 else ""}</p>'
        
        cards_html += f'''
        <article class="card">
            <div class="card-header">
                <span class="company">{company}</span>
                <span class="quality">Score: {quality}/10</span>
            </div>
            <h2><a href="{url}" target="_blank" rel="noopener">{title[:100]}{"..." if len(title) > 100 else ""}</a></h2>
            <p class="use-case">{use_case}</p>
            {results_html}
            {lessons_html}
            <div class="tags">
                {tech_tags}
                <span class="tag stage">{stage}</span>
            </div>
        </article>
        '''
    
    # If no deployments, show a message
    if not cards_html:
        cards_html = '''
        <div class="empty-state">
            <p>No deployment stories found yet. Check back soon!</p>
        </div>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Deployment Intel - Real-World AI Case Studies</title>
    <meta name="description" content="Curated collection of real-world AI and LLM deployment case studies, lessons learned, and production insights.">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1rem;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid #2a2a2a;
        }}
        
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .subtitle {{
            color: #888;
            font-size: 1.1rem;
        }}
        
        .stats {{
            margin-top: 1rem;
            font-size: 0.9rem;
            color: #666;
        }}
        
        .card {{
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: border-color 0.2s;
        }}
        
        .card:hover {{
            border-color: #667eea;
        }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }}
        
        .company {{
            font-weight: 600;
            color: #667eea;
        }}
        
        .quality {{
            font-size: 0.85rem;
            color: #888;
            background: #252525;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
        }}
        
        .card h2 {{
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
        }}
        
        .card h2 a {{
            color: #fff;
            text-decoration: none;
        }}
        
        .card h2 a:hover {{
            color: #667eea;
        }}
        
        .use-case {{
            color: #aaa;
            margin-bottom: 1rem;
        }}
        
        .results {{
            background: #151515;
            border-left: 3px solid #4ade80;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
            list-style: none;
        }}
        
        .results li {{
            color: #4ade80;
            font-size: 0.95rem;
            padding: 0.25rem 0;
        }}
        
        .results li::before {{
            content: "✓ ";
        }}
        
        .lesson {{
            font-style: italic;
            color: #f59e0b;
            font-size: 0.95rem;
            margin-bottom: 1rem;
        }}
        
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        
        .tag {{
            font-size: 0.8rem;
            padding: 0.25rem 0.75rem;
            background: #252525;
            border-radius: 20px;
            color: #888;
        }}
        
        .tag.stage {{
            background: #1e3a5f;
            color: #60a5fa;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            color: #666;
        }}
        
        footer {{
            text-align: center;
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid #2a2a2a;
            color: #666;
            font-size: 0.9rem;
        }}
        
        footer a {{
            color: #667eea;
            text-decoration: none;
        }}
        
        @media (max-width: 600px) {{
            h1 {{
                font-size: 1.75rem;
            }}
            
            .card {{
                padding: 1rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 AI Deployment Intel</h1>
            <p class="subtitle">Real-world AI deployment case studies and lessons learned</p>
            <p class="stats">{len(deployments)} stories • Updated {generated_date}</p>
        </header>
        
        <main>
            {cards_html}
        </main>
        
        <footer>
            <p>Curated by an AI agent • Data sourced from engineering blogs and case studies</p>
            <p style="margin-top: 0.5rem;">
                <a href="https://github.com/pathak-r/ai-deployment-intel" target="_blank">View on GitHub</a>
            </p>
        </footer>
    </div>
</body>
</html>'''
    
    return html


# ============ Previous functions (Steps 2-6) ============

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
    """Store a deployment story in Supabase."""
    from supabase import create_client
    import os
    
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
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
    
    try:
        supabase.table("deployments").upsert(record, on_conflict="url").execute()
        return {"success": True, "url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-secret")],
)
def get_deployments(min_quality: int = 5, limit: int = 50) -> dict:
    """Retrieve stored deployment stories from Supabase."""
    from supabase import create_client
    import os
    
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
    try:
        result = supabase.table("deployments")\
            .select("*")\
            .eq("is_deployment_story", True)\
            .gte("quality_score", min_quality)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return {"success": True, "count": len(result.data), "deployments": result.data}
    except Exception as e:
        return {"success": False, "error": str(e), "deployments": []}


def select_queries(num_queries: int = 3) -> list:
    """
    Select random queries from the search query bank.
    Uses simple random selection for diversity.
    """
    import random

    # Return up to num_queries random queries
    return random.sample(SEARCH_QUERY_BANK, min(num_queries, len(SEARCH_QUERY_BANK)))


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("tavily-secret"),
        modal.Secret.from_name("firecrawl-secret"),
        modal.Secret.from_name("anthropic-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
    timeout=600,  # Increased timeout for multiple queries
)
def run_pipeline(num_queries: int = 3, results_per_query: int = 10, min_quality: int = 3) -> dict:
    """
    Run the full pipeline with multiple diverse queries.

    Args:
        num_queries: Number of different queries to run (default: 3)
        results_per_query: Max search results per query (default: 10)
        min_quality: Minimum quality score to store (default: 3)

    Returns:
        Aggregated stats across all queries
    """
    from tavily import TavilyClient
    from firecrawl import Firecrawl
    from anthropic import Anthropic
    from supabase import create_client
    import os

    stats = {
        "queries_executed": 0,
        "searched": 0,
        "fetched": 0,
        "evaluated": 0,
        "stored": 0,
        "errors": [],
        "queries_used": []
    }

    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    firecrawl = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    anthropic = Anthropic()
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    # Select diverse queries
    queries = select_queries(num_queries)
    print(f"Selected {len(queries)} queries to execute")

    # Process each query
    for query in queries:
        print(f"\nProcessing query: {query}")
        stats["queries_used"].append(query)
        stats["queries_executed"] += 1

        # Search
        try:
            search_response = tavily.search(query=query, search_depth="advanced", max_results=results_per_query)
            search_results = search_response.get("results", [])
            stats["searched"] += len(search_results)
            print(f"Found {len(search_results)} results")
        except Exception as e:
            stats["errors"].append(f"Search error for '{query}': {e}")
            continue

        for item in search_results:
            url = item.get("url", "")
            title = item.get("title", "")

            # Fetch
            try:
                fetch_result = firecrawl.scrape(url=url, formats=["markdown"])
                content = fetch_result.markdown or ""
                if fetch_result.metadata:
                    title = fetch_result.metadata.title or title
                stats["fetched"] += 1
            except Exception as e:
                stats["errors"].append(f"Fetch error for {url}: {e}")
                continue

            if len(content) < 300:
                continue

            # Evaluate
            try:
                content_truncated = content[:12000]
                evaluation_prompt = f"""Analyze this content and determine if it describes a practical AI/ML deployment experience or implementation story.

INCLUDE content that:
- Describes real production, pilot, or POC AI/ML implementations
- Shares lessons learned from deploying AI systems
- Discusses technical challenges and solutions in AI deployment
- Provides insights from building or operating AI systems
- Covers infrastructure, scaling, or operational aspects of AI

ACCEPT stories even if:
- Metrics or results are qualitative rather than quantitative
- It's a pilot or POC with real learnings (not just theory)
- It focuses more on lessons learned than success metrics
- It's about implementation challenges rather than perfect outcomes

REJECT content that is:
- Purely theoretical or conceptual (no real implementation)
- Just announcing a product or feature (no technical depth)
- Only about AI research (no deployment/production focus)
- Tutorial or how-to without real-world deployment context

URL: {url}
TITLE: {title}
CONTENT:
{content_truncated}

Respond with JSON only:
{{"is_deployment_story": bool, "confidence": 0-1, "reason": "string", "company": "string or null", "use_case": "string", "technology_stack": [], "results": [], "lessons_learned": [], "deployment_stage": "production/pilot/poc/unknown", "content_type": "blog_post/case_study/other", "quality_score": 1-10}}

Quality scoring guide:
- 8-10: Exceptional depth, specific metrics, multiple insights
- 5-7: Good practical content with real learnings
- 3-4: Basic deployment story with some useful information
- 1-2: Minimal practical value or mostly marketing"""

                response = anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": evaluation_prompt}]
                )

                response_text = response.content[0].text.strip()
                if "```" in response_text:
                    response_text = response_text.split("```")[1].replace("json", "").strip()

                evaluation = json.loads(response_text)
                stats["evaluated"] += 1

                is_story = evaluation.get("is_deployment_story", False)
                quality = evaluation.get("quality_score", 0)

            except Exception as e:
                stats["errors"].append(f"Evaluation error for {url}: {e}")
                continue

            # Store
            if is_story and quality >= min_quality:
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
                except Exception as e:
                    stats["errors"].append(f"Storage error for {url}: {e}")
    
    return stats


@app.function()
def hello():
    """Original hello function."""
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


@app.local_entrypoint()
def main():
    """Generate the static site and publish to GitHub Pages."""
    result = publish_site.remote()

    if result.get("success"):
        print(f"✓ Successfully published {result['deployment_count']} deployments")
        print(f"✓ Commit: {result['commit_message']}")
        print(f"✓ Site URL: {result['site_url']}")
    else:
        print(f"✗ Failed to publish site: {result.get('error')}")
