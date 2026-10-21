# Product Tagline Creator

A Gradio web app that uses an LLM-powered, multi-agent workflow to turn product
details into a structured marketing brief. The generated brief includes a
tagline, elevator pitch, feature-and-benefit table, core value proposition, and
call to action.

## Features

- Generate a marketing brief from a product name, category, and target
  audience.
- Run a LangGraph workflow with separate generation, critique, refinement, and
  validation steps. Invalid output can be sent through an automatic refinement
  retry.
- Request a revision with human feedback and browse earlier brief versions.
- View reported token usage, estimated cost, and agent-node latency.
- Export a brief as a Markdown file or download the local session log.
- View a Mermaid diagram of the agent workflow in the app.

## Workflow

```text
Product details
      |
   Generator
      |
    Critique
      |
    Refiner <---- validation retry (up to two refiner attempts)
      |
   Validator
      |
Marketing brief
```

Human-requested revisions are sent through the refiner and validator. They do
not rerun the generator or critique steps.

## Requirements

- Python 3.11 or newer
- An API key for an LLM provider that supports the OpenAI-compatible chat
  completions API configured below
- Internet access for the configured LLM endpoint; the workflow diagram also
  loads Mermaid.js from a CDN

## Setup

In PowerShell, from the project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `OLLAMA_CLOUD_API_KEY` to your provider's API key. The
`.env` file is for local use only and should never be committed.

Run the app:

```powershell
python app.py
```

Open the local URL printed by Gradio in your browser.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `OLLAMA_CLOUD_API_KEY` | API key passed to the OpenAI-compatible client | `ollama` |
| `OLLAMA_CLOUD_BASE_URL` | OpenAI-compatible API base URL | `https://api.ollama.com/v1` |
| `OLLAMA_CLOUD_MODEL` | Model identifier sent to the API | `gpt-oss:20b` |

Set these values in `.env` or in the process environment. Confirm the endpoint,
model availability, and credentials with your LLM provider.

## Project files

| File | Description |
| --- | --- |
| `app.py` | Gradio interface, event handlers, version selection, and exports |
| `graph_engine.py` | LangGraph workflow, prompts, validation, telemetry, and logging |
| `requirements.txt` | Pinned direct Python dependencies |
| `.env.example` | Environment-variable template with no credentials |

Generated session data is written to `session_logs.json` in the working
directory. It can include product and audience inputs, so it is excluded from
Git. Exported Markdown briefs are also excluded by the repository's ignore
rules.

Token and latency values are reported by the configured model API. The
displayed cost is an estimate calculated using fixed rates in `graph_engine.py`
and may not match your provider's current pricing.

## Security

- Never commit `.env`, API keys, or other credentials.
- Review generated briefs and exported session data before sharing them; they
  may contain information you entered into the app.
- The model provider receives the product details and feedback submitted to
  the app.
