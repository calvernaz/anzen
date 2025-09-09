# Anzen Safety Gateway

FastAPI + NeMo Guardrails + Presidio for PII detection and masking in AI agent workflows.

## Features

- **PII Detection**: Microsoft Presidio for detecting emails, phones, SSNs, credit cards, etc.
- **Policy Enforcement**: NeMo Guardrails for flow orchestration and policy decisions
- **Route-based Policies**: Different rules for public, private, and internal routes
- **Real-time Processing**: Fast API endpoints for input/output safety checks
- **Audit Logging**: Complete trail of all safety decisions

## Quick Start

```bash
# Install
uv sync

# Start the gateway
uv run anzen-gateway --reload --log-level debug

# Test the API
curl -X POST http://localhost:8000/v1/anzen/check/input \
  -H "Content-Type: application/json" \
  -d '{"text": "My email is john@example.com", "route": "public:chat"}'
```

## API Endpoints

- `POST /v1/anzen/check/input` - Check and mask input text
- `POST /v1/anzen/check/output` - Check and mask output text  
- `GET /health` - Health check

## Configuration

Configure via environment variables:
- `ANZEN_CONFIG_PATH` - Path to NeMo Guardrails config directory
- `ANZEN_LOG_LEVEL` - Log level (debug, info, warning, error)
