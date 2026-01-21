"""
AI Deployment Intelligence Agent - Step 1: Hello World
======================================================
This is the simplest possible Modal app.
We'll build on this foundation step by step.
"""

import modal

# Create a Modal App
# Think of this as a container for all your serverless functions
app = modal.App("ai-deployment-intel")


# @app.function() decorator tells Modal:
# "This function should run on Modal's cloud infrastructure"
@app.function()
def hello():
    """
    A simple function that runs in the cloud.
    When called, Modal spins up a container, runs this, and returns the result.
    """
    print("Hello from Modal! This is running in the cloud.")
    return {"status": "success", "message": "Hello from AI Deployment Intel!"}


# @app.local_entrypoint() is the entry point when you run:
# `modal run src/main.py`
# 
# This code runs LOCALLY, but it can call .remote() on Modal functions
# to execute them in the cloud.
@app.local_entrypoint()
def main():
    """
    Entry point for manual runs.
    This runs locally and calls the cloud function.
    """
    print("Starting local entrypoint...")
    print("Calling hello() remotely on Modal...")
    
    # .remote() sends the function to Modal's cloud to execute
    result = hello.remote()
    
    print(f"Got result back: {result}")
    print("Done!")
