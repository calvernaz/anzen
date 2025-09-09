# Anzen - Enterprise Safety Layer for LLM Applications

**Production-grade demo of safety guardrails for AI applications with real-time PII detection, policy enforcement, and compliance logging.**

## Overview

Anzen provides enterprise-grade safety controls for LLM applications:

- **Real-time PII Detection** - Emails, phones, SSNs, credit cards, IBANs, and custom patterns
- **Advanced Content Safety** - NeMo Guardrails for hate speech, toxicity, and harmful content detection
- **Policy Enforcement** - Route-based policies (block, redact, log) with configurable rules
- **Comprehensive Audit Trails** - Detailed traces for compliance with data minimization (no raw PII stored)
- **Low Latency** - <50ms p95 overhead for production workloads
- **Simple Integration** - Drop-in Python client for existing applications

## Architecture

```
┌─────────────────┐    HTTP     ┌─────────────────┐    Actions    ┌─────────────────┐
│   Lambda/App    │ ──────────► │  Anzen Gateway  │ ────────────► │ Presidio Engine │
│                 │             │                 │               │                 │
│ Safety Client   │ ◄────────── │ NeMo Guardrails │ ◄──────────── │ PII Detection   │
└─────────────────┘   Response  │                 │               │ • Emails        │
                                │ • Hate Speech   │               │ • SSNs          │
                                │ • Toxicity      │               │ • Credit Cards  │
                                │ • Custom Rules  │               │ • Custom Regex  │
                                └─────────────────┘               └─────────────────┘
                                          │
                                          ▼
                                ┌─────────────────┐
                                │   AI Agent      │
                                │                 │
                                │ OpenAI + Tools  │
                                │ Plan → Execute  │
                                └─────────────────┘
```

## Safety Capabilities

### NeMo Guardrails Integration

Anzen leverages NVIDIA's NeMo Guardrails for advanced content safety beyond deterministic PII detection:

- **Hate Speech Detection** - Identifies and blocks discriminatory language
- **Toxicity Filtering** - Prevents harmful or abusive content
- **Bias Mitigation** - Reduces unfair or prejudicial outputs
- **Custom Safety Rules** - Configurable guardrails for domain-specific risks
- **Context-Aware Filtering** - Understands nuanced content in conversational context

Unlike simple keyword filtering, NeMo Guardrails uses advanced NLP models to understand intent and context, making it ideal for:
- Customer service applications with diverse user inputs
- Educational platforms requiring content moderation
- Healthcare applications with sensitive topics
- Financial services with compliance requirements

### Presidio PII Detection

Deterministic pattern-based detection for structured data:
- Email addresses, phone numbers, SSNs, credit cards
- Custom regex patterns for domain-specific identifiers
- High-precision detection with minimal false positives

## Policy Configuration

Rules are configurable through YAML files and route-based policies:

```yaml
# packages/gateway/config/config.yml
policies:
  public:
    block_entities: ["CREDIT_CARD", "US_SSN", "US_PASSPORT", "IBAN_CODE"]
    redact_entities: ["EMAIL_ADDRESS", "PHONE_NUMBER"]
    risk_threshold: 0.8

  private:
    block_entities: ["CREDIT_CARD", "US_SSN", "US_PASSPORT"]
    redact_entities: ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"]
    risk_threshold: 0.9

  internal:
    block_entities: ["CREDIT_CARD", "US_SSN"]
    redact_entities: []
    risk_threshold: 0.95
```

### Route-Based Policies

- **`public:*`** - Strict blocking for public-facing applications
- **`private:*`** - Moderate redaction for internal tools
- **`internal:*`** - Permissive logging for development/ops

### Configurable Parameters

- **Entity Types** - Add/remove PII types to detect
- **Risk Thresholds** - Adjust confidence scores (0.0-1.0)
- **Actions** - BLOCK (reject), REDACT (mask), ALLOW (log only)
- **Route Patterns** - Custom hierarchies like `private:support`, `public:chat`

## Audit & Compliance Traces

Anzen produces comprehensive audit trails for compliance and monitoring. All traces are logged with data minimization principles - **no raw PII is stored**.

### Request Trace Example
```json
{
  "timestamp": "2025-09-09T07:30:15.123Z",
  "trace_id": "req_abc123def456",
  "route": "public:chat",
  "action": "assess_input",
  "decision": "BLOCK",
  "reason": "PII_DETECTED",
  "entities_detected": [
    {
      "type": "EMAIL_ADDRESS",
      "confidence": 0.95,
      "location": "char_15_35",
      "hash": "sha256:a1b2c3..."
    },
    {
      "type": "PHONE_NUMBER",
      "confidence": 0.88,
      "location": "char_45_57",
      "hash": "sha256:d4e5f6..."
    }
  ],
  "policy_applied": "public_strict",
  "processing_time_ms": 23,
  "client_ip_hash": "sha256:x7y8z9...",
  "user_agent_hash": "sha256:m1n2o3..."
}
```

### Content Safety Trace Example
```json
{
  "timestamp": "2025-09-09T07:30:15.145Z",
  "trace_id": "req_abc123def456",
  "route": "public:chat",
  "action": "nemo_guardrails_check",
  "decision": "BLOCK",
  "reason": "HATE_SPEECH_DETECTED",
  "safety_scores": {
    "toxicity": 0.92,
    "hate_speech": 0.87,
    "bias": 0.34
  },
  "triggered_rules": ["hate_speech_filter", "toxicity_threshold"],
  "input_hash": "sha256:p9q8r7...",
  "processing_time_ms": 45
}
```

### Agent Workflow Trace Example
```json
{
  "timestamp": "2025-09-09T07:30:15.200Z",
  "trace_id": "req_abc123def456",
  "route": "private:support",
  "action": "agent_execution",
  "decision": "ALLOW",
  "workflow": {
    "plan": "analyze_customer_issue",
    "tools_used": ["search_knowledge_base", "create_ticket"],
    "safety_checks": 3,
    "redactions_applied": 1
  },
  "output_safety": {
    "pii_detected": false,
    "content_safe": true,
    "redacted_entities": ["CUSTOMER_ID"]
  },
  "processing_time_ms": 1250,
  "tokens_used": 450
}
```

### Audit Dashboard Metrics
- **Safety Events/Hour** - Real-time blocking and redaction rates
- **Policy Effectiveness** - Success rates by route and entity type
- **Performance Impact** - Latency percentiles and throughput
- **Compliance Coverage** - Audit trail completeness and retention
- **False Positive Rates** - Manual review and tuning insights

All traces are stored in structured logs with configurable retention periods and can be exported to SIEM systems or compliance platforms.

## Quick Start

```bash
# Setup environment
cp .env.example .env
# Edit .env with your API keys and passwords

# Start all services
make docker-up

# Services available at:
# - Gateway: http://localhost:8000
# - Agent: http://localhost:8001
# - Client: http://localhost:3000
# - Monitoring: http://localhost:3001 (Grafana)
# - Metrics: http://localhost:9090 (Prometheus)
```

### Manual Setup
```bash
# Install dependencies
make install

# Start services (separate terminals)
make start-gateway  # Port 8000
make start-agent    # Port 8001
make start-client   # Port 3001
```

## Testing

Visit http://localhost:3000 for a ChatGPT-like interface with real-time safety checks.

Test with examples like:
- **High-Risk**: "My SSN is 123-45-6789" → BLOCK
- **Medium-Risk**: "Email me at john@example.com" → REDACT
- **Safe**: "What's the weather in Paris?" → ALLOW

## Integration

```python
from anzen_client import SafetyClient

safety_client = SafetyClient(gateway_url="https://anzen.example.com")

# Check input for PII
response = safety_client.assess_input(user_input, route="public:chat")
if response.should_block:
    return {"error": "Content blocked"}

# Use safe text for LLM processing
llm_response = call_llm(response.safe_text)

# Check output
output_response = safety_client.assess_output(llm_response)
return {"response": output_response.safe_text}
```

### Edge Deployment

For low latency scenarios, the Anzen Gateway can be deployed as a **Cloudflare Edge Worker**, bringing safety checks closer to users worldwide with sub-10ms response times.

## Enterprise Support

For production deployments, custom integrations, or enterprise features, we offer consulting services to help implement Anzen in your organization.

---
