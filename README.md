# ComplyFi — Financial Compliance Automation on Azure

An enterprise compliance platform for financial services, built on **Azure AI Agent Service + Azure AI Content Safety**. Automates KYC verification, AML screening, sanctions checking, and regulatory reporting across three workflow patterns: sequential onboarding, concurrent transaction screening, and risk-based escalation handoff. Every agent call passes through guardrails middleware; every decision is audit-logged.

## Architecture

```
Azure Container Apps
    ├── FastAPI Gateway
    │       ├── POST /compliance/verify   (sequential: KYC → AML → Risk → Report)
    │       ├── POST /compliance/screen   (concurrent: KYC + AML + Fraud + Sanctions)
    │       └── POST /compliance/escalate (handoff: auto_approve | manual_review | escalate)
    │
    └── Middleware Pipeline
            ├── PII Detection      → Azure AI Content Safety
            ├── Sanctions Screening → Azure AI Content Safety
            └── Idempotency        → Azure Cache for Redis

Azure AI Agent Service   ← workflow orchestration
Azure OpenAI             ← all agent inference
Azure AI Content Safety  ← PII, sanctions, harmful content filtering
Azure Cache for Redis    ← idempotency keys, rate limiting
Application Insights     ← audit trail, compliance metrics
```

## Stack

| Layer | Local Development | Azure Production |
|-------|------------------|-----------------|
| API | FastAPI + ASP.NET Core | Azure Container Apps |
| Agent Runtime | Custom (MAF-compatible) | Azure AI Agent Service |
| Guardrails | Python middleware | Azure AI Content Safety |
| Idempotency | Redis | Azure Cache for Redis |
| Telemetry | OpenTelemetry | Application Insights |
| Database | PostgreSQL | Azure PostgreSQL Flexible |

## Quick Start (Local)

```bash
cd complyfi
docker-compose up --build
```

## Deploy to Azure

```bash
az containerapp compose create \
  --resource-group azure-agentic-rg \
  --environment agentic-env \
  --compose-file docker-compose.yml
```

Requires: Azure subscription, Azure OpenAI, Azure AI Content Safety, Azure Cache for Redis, PostgreSQL Flexible Server.

## Why This Architecture

**Guardrails as middleware, not agent instructions.** Compliance rules must apply uniformly across all workflows regardless of which agent processes the request. Middleware ensures every call passes through PII detection, sanctions screening, and transaction limit checks — no agent can bypass them.

**Three workflow patterns for three compliance tasks.** Onboarding is sequential (identity verification depends on KYC results). Transaction screening is parallel (AML, fraud, and sanctions are independent). Escalation requires handoff. One workflow pattern cannot serve all three efficiently.

**Evaluation harness from day one.** Financial compliance has measurable quality criteria: false positive rate, false negative rate, screening latency. The evaluation suite runs 8 test cases per deployment and produces a structured report. This pattern maps directly to **Azure AI Foundry Evaluations** in production.

## Compliance Posture

This system demonstrates patterns applicable to SOC 2, PCI DSS, and GDPR compliance. It is not itself certified. Production deployment requires independent security review, penetration testing, and regulatory approval before handling real financial data.

## License

MIT
