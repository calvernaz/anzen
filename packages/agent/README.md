# Anzen AI Agent

AI workflow agent with safety guardrails integration for secure AI agent interactions.

## Features

- **Plan → Execute Workflow**: 2-step process: (1) plan → (2) execute with external APIs
- **Safety Integration**: All inputs/outputs processed through Anzen Safety Gateway
- **External APIs**: Wikipedia and Weather API integration
- **Audit Logging**: Complete trail of agent interactions and safety decisions
- **Multi-tenant**: Support for multiple users with API keys

## Quick Start

```bash
# Install
uv sync

# Start the agent
uv run anzen-agent --reload --log-level debug

# Test the API
curl -X POST http://localhost:8001/v1/agents/secure \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the weather like in Paris?"}'
```

## API Endpoints

- `POST /v1/agents/secure` - Secure agent interaction
- `GET /v1/reports` - Fetch compliance logs
- `GET /health` - Health check

## Configuration

Configure via environment variables:
- `ANZEN_GATEWAY_URL` - URL of the Anzen Safety Gateway
- `OPENAI_API_KEY` - OpenAI API key for LLM calls
- `ANZEN_LOG_LEVEL` - Log level (debug, info, warning, error)
