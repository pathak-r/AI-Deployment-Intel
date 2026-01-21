# AI Deployment Intelligence Agent

Learning to build an autonomous agent that discovers real-world AI deployment case studies.

## Current Status: Step 1 - Hello World

A minimal Modal app to validate the GitHub → Modal CI/CD pipeline.

## Setup

1. Add Modal secrets to GitHub (Settings → Secrets → Actions):
   - `MODAL_TOKEN_ID`
   - `MODAL_TOKEN_SECRET`
2. Push to `main` branch to trigger deployment
3. Check Modal dashboard for deployment status

## Manual Run

```bash
modal run src/main.py
```
