"""
AI Deployment Intelligence Agent - Step 2: Secrets + API Call
==============================================================
Building on Step 1, we now:
1. Use Modal secrets to securely access API keys
2. Make a real API call to Claude
3. See results in Modal logs
"""

import modal

# Create the Modal App (same as before)
app = modal.App("ai-deployment-intel")

# NEW: Define a container image with dependencies
# This tells Modal what Python packages to install in the container
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "anthropic>=0.40.0",  # Anthropic's Python SDK
)


# NEW: @app.function() now has parameters:
# - image: use our custom image with anthropic installed
# - secrets: list of Modal secrets to inject as environment variables
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
)
def call_claude(prompt: str) -> dict:
    """
    Call Claude API and return the response.
    
    The ANTHROPIC_API_KEY is automatically available as an 
    environment variable because we specified the secret above.
    """
    # Import inside function - this code runs in Modal's container
    # where anthropic is installed
    from anthropic import Anthropic
    import os
    
    # The secret is injected as an environment variable
    # We don't need to explicitly read it - the Anthropic client
    # automatically looks for ANTHROPIC_API_KEY
    client = Anthropic()
    
    print(f"Calling Claude with prompt: {prompt[:100]}...")
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Extract the text response
    result_text = response.content[0].text
    
    print(f"Claude responded: {result_text[:100]}...")
    
    return {
        "status": "success",
        "prompt": prompt,
        "response": result_text,
        "model": response.model,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    }


# Keep the simple hello function for testing
@app.function()
def hello():
    """Original hello function - still works!"""
    print("Hello from Modal!")
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


# Updated entrypoint to test our Claude integration
@app.local_entrypoint()
def main():
    """
    Test the Claude API call.
    Run with: modal run src/main.py
    """
    print("=" * 50)
    print("AI Deployment Intel - Step 2: Claude API Test")
    print("=" * 50)
    
    # Test prompt - asking Claude something simple
    test_prompt = "In one sentence, what makes a good AI deployment case study?"
    
    print(f"\nSending prompt to Claude...")
    result = call_claude.remote(test_prompt)
    
    print(f"\n{'=' * 50}")
    print("RESULT:")
    print(f"{'=' * 50}")
    print(f"Status: {result['status']}")
    print(f"Model: {result['model']}")
    print(f"Tokens used: {result['usage']}")
    print(f"\nResponse:\n{result['response']}")
    print("=" * 50)
