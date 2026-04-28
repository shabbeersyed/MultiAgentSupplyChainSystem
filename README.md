![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Tests](https://img.shields.io/badge/Tests-7%20passing-brightgreen)
![Agents](https://img.shields.io/badge/Agents-4-orange)
![Cloud](https://img.shields.io/badge/Cloud-GCP-blue)

# Autonomous Supply Chain: Vision × Vector × Agents

An end-to-end **enterprise-grade agentic supply chain system** — combining computer vision, semantic vector search, governance, observability, logistics, and real-world MCP integrations to automate physical inventory management.

**Live Demo:** https://visual-commerce-demo-693699778723.us-central1.run.app/

---

## The Problem

Traditional warehouse inventory systems depend on humans to:
- Physically count items on shelves
- Manually look up supplier catalogs by SKU
- Decide when and what to reorder
- Calculate shipping costs and ETAs manually
- Send order confirmations and update spreadsheets

This is slow, error-prone, and unscalable. This system eliminates all of it.

---

## The Solution

Upload a photo of a warehouse shelf. Four specialized agents collaborate to:

1. **Count** what's on the shelf using deterministic computer vision
2. **Find** the best-matched supplier part via semantic vector search
3. **Calculate** shipping cost, carrier, and ETA
4. **Confirm** the order via Gmail, Google Calendar, and Google Sheets

No human in the loop. No manual SKU lookup. No guessing.

---

## Business Impact

| Problem | Without This System | With This System |
|---|---|---|
| Inventory counting | Manual, hours of labor, error-prone | Automated in seconds via vision AI |
| Stockout detection | Discovered after the fact | Detected proactively from shelf image |
| Supplier matching | Manual SKU lookup, catalog search | Semantic search across millions of parts |
| Shipping calculation | Manual carrier lookup, calls | Automated zone-based cost + ETA |
| Audit compliance | No trace of decisions | Full audit log per request and agent |
| Large order risk | No controls or approval gates | Human approval enforced automatically |
| Order confirmation | Manual emails, calendar entries | Automated via Gmail, Calendar, Sheets |

**KPIs this system improves:**
- Reduces inventory counting time from hours to seconds
- Eliminates manual supplier lookup entirely
- Automates shipping calculation and carrier selection
- Enforces compliance automatically with zero human overhead
- Provides full decision audit trail for enterprise governance
- Flags high-risk orders before they execute

---

## Enterprise Architecture

```
User uploads image
        │
        ▼
Governance Layer (agents/governance.py)
        Validates input, blocks prompt injection,
        enforces policies, logs every request
        │
        ▼
Control Tower (8080)  ← WebSocket + FastAPI + Observability
        Assigns workflow ID, traces all agents
        │
        │  A2A Protocol (agent discovery via /.well-known/agent-card.json)
        │
        ├──▶ Vision Agent (8081)
        │       Gemini 3 Flash + Code Execution → deterministic item count
        │       Gemini 2.5 Flash Lite → structured semantic search query
        │
        ├──▶ Supplier Agent (8082)
        │       Vertex AI text-embedding-005 → embedding generation
        │       AlloyDB ScaNN vector search → best-matched part + supplier
        │
        ├──▶ Logistics Agent (8083)
        │       Supplier location lookup → zone-based shipping calculation
        │       Returns: cost, carrier (FedEx/UPS), ETA, origin → destination
        │
        └──▶ MCP Integrations (post-order)
                Gmail → HTML order confirmation email
                Google Calendar → delivery date event
                Google Sheets → order log row appended
```

All agents expose `/.well-known/agent-card.json` following the **A2A Protocol** — discoverable and composable without hard-coded wiring.

---

## Agents

| Agent | Port | Technology | Responsibility |
|-------|------|-----------|----------------|
| Vision Agent | 8081 | Gemini 3 Flash + Code Execution | Counts items deterministically from image, returns semantic query |
| Supplier Agent | 8082 | AlloyDB ScaNN + Vertex AI Embeddings | Finds best-matched part and supplier via vector similarity search |
| Logistics Agent | 8083 | Zone-based shipping calculator | Calculates shipping cost, carrier, and ETA from supplier to destination |
| Control Tower | 8080 | FastAPI + WebSocket | Orchestrates all agents via A2A, streams results live to UI |

### MCP Integrations (post-order)

After an order is placed, the Control Tower triggers three real-world integrations:

- **Gmail** — sends an HTML order confirmation email
- **Google Calendar** — creates a delivery date event on the primary calendar
- **Google Sheets** — appends an order log row (order ID, part, supplier, cost, carrier, ETA, origin)

---

## Enterprise Features

### Governance Layer
Every request is validated before any agent runs:
- Image type and size validation (jpeg, png, webp only, max 5MB)
- Prompt injection detection — 11 known patterns blocked
- High-risk order flagging — quantities over 1000 require human approval
- Full audit logging with unique request IDs and timestamps

### Observability and Audit Trail
Every agent execution is fully traceable:
- Per-agent execution tracing (start time, duration, status)
- Workflow-level tracking across all agents via workflow ID
- Structured audit logs written to file for compliance
- Complete decision history retrievable by workflow ID
- Success and failure capture with full error context

### Security and Guardrails

**Vision Agent:**
- Image size capped at 10MB; unsupported MIME types rejected before any model call
- Prompt injection detection — 11 known injection patterns blocked
- Queries sanitized and truncated to 500 characters before reaching Gemini

**Supplier Agent:**
- Query length capped at 300 characters
- Character allowlist enforced (alphanumeric + common punctuation only)
- Internal stack traces never returned to caller — generic error surfaced instead
- Confidence scores computed from validated ScaNN cosine distance, not hardcoded

**Infrastructure:**
- IAM-based AlloyDB access — no credentials in code or Docker images
- All secrets loaded from `.env` / Cloud Run environment, excluded from Git
- Each agent runs as an isolated service on a separate port
- CORS restricted to configured allowed origins only

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Governance | Custom Python layer | Enterprise policy enforcement before agent execution |
| Observability | Structured logging + tracing | Full audit trail across every workflow |
| Vision | Gemini 3 Flash + Code Execution | Deterministic counting, not hallucination |
| Query Gen | Gemini 2.5 Flash Lite | Fast structured output with Pydantic models |
| Vector DB | AlloyDB AI + ScaNN | 10x faster filtered search vs HNSW, 8x faster index builds |
| Embeddings | Vertex AI text-embedding-005 | Real semantic similarity across part descriptions |
| DB Connection | AlloyDB Python Connector | IAM auth + managed SSL, no Auth Proxy needed |
| Backend | FastAPI + WebSocket | Async-native, real-time event streaming to UI |
| Agent Protocol | A2A | Plug-and-play agent discovery and composability |
| Integrations | Gmail, Google Calendar, Google Sheets | Real-world order confirmation and logging |

---

## Repository Structure

```
MultiAgentSupplyChainSystem/
├── agents/
│   ├── governance.py              # Input validation, prompt injection protection
│   ├── observability.py           # Per-agent tracing, audit logging
│   ├── vision-agent/
│   │   ├── agent.py               # Gemini 3 Flash vision + bounding box logic
│   │   ├── agent_executor.py      # A2A server executor
│   │   └── main.py                # FastAPI entrypoint
│   ├── supplier-agent/
│   │   ├── inventory.py           # AlloyDB ScaNN vector search
│   │   ├── agent_executor.py      # A2A executor + input guardrails
│   │   └── main.py                # FastAPI entrypoint
│   └── logistics-agent/
│       ├── shipping.py            # Zone-based shipping cost + ETA calculator
│       ├── agent_executor.py      # A2A executor
│       └── main.py                # FastAPI entrypoint
├── tests/
│   ├── test_governance.py         # 4 passing tests
│   └── test_observability.py      # 3 passing tests
├── frontend/
│   ├── app.py                     # Control Tower: orchestration + WebSocket + MCP
│   └── static/                    # UI (index.html, app.js, styles.css)
├── database/
│   ├── seed.py                    # AlloyDB seeding via Connector
│   └── seed_data.sql              # Schema + 20 inventory items
├── deploy/
│   └── deploy.sh                  # Cloud Run deployment script
├── test-images/                   # Sample warehouse shelf images
├── Dockerfile                     # Container configuration
├── setup.sh                       # Environment setup script
├── run.sh                         # Launches all four services
└── .env.example                   # Config template
```

---

## Getting Started

### Prerequisites
- Google Cloud Project with billing enabled
- gcloud CLI configured
- Python 3.9+

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | Vertex AI region (default: global) |
| `ALLOYDB_REGION` | Yes | GCP region of AlloyDB instance |
| `ALLOYDB_CLUSTER` | Yes | AlloyDB cluster name |
| `ALLOYDB_INSTANCE` | Yes | AlloyDB instance name |
| `DB_PASS` | Yes | AlloyDB postgres password |
| `OAUTH_CLIENT_ID` | Yes (MCP) | Google OAuth client ID |
| `OAUTH_CLIENT_SECRET` | Yes (MCP) | Google OAuth client secret |
| `OAUTH_REFRESH_TOKEN` | Yes (MCP) | OAuth refresh token |
| `VISION_AGENT_URL` | No | Default: http://localhost:8081 |
| `SUPPLIER_AGENT_URL` | No | Default: http://localhost:8082 |
| `LOGISTICS_AGENT_URL` | No | Default: http://localhost:8083 |

### Run Locally

```bash
git clone https://github.com/shabbeersyed/MultiAgentSupplyChainSystem.git
cd MultiAgentSupplyChainSystem
sh setup.sh
sh run.sh
```

Open http://localhost:8080 for the Control Tower.

### Deploy to Cloud Run

```bash
sh deploy/deploy.sh
```

---

## Running Tests

```bash
# Governance layer tests (4 tests)
python tests/test_governance.py

# Observability tests (3 tests)
python tests/test_observability.py
```

Expected output:
```
🔒 Running Governance Layer Tests...
✅ test_valid_request PASSED
✅ test_prompt_injection_blocked PASSED
✅ test_high_quantity_blocked PASSED
✅ test_invalid_image_type PASSED
✅ All governance tests passed!

🔍 Running Observability Tests...
✅ test_successful_agent_trace PASSED
✅ test_failed_agent_trace PASSED
✅ test_full_workflow_trace PASSED
✅ All observability tests passed!
```

---

## Branch Workflow

This repository follows a structured Git workflow:

```
main
 └── dev
      └── feature/your-feature-name
```

- All changes are developed on feature branches
- Feature branches are merged into dev via pull request
- Dev is merged into main after review
- No direct pushes to main

---

## Troubleshooting

**Port conflicts**
```bash
lsof -ti:8080 | xargs kill -9
lsof -ti:8081 | xargs kill -9
lsof -ti:8082 | xargs kill -9
lsof -ti:8083 | xargs kill -9
```

**AlloyDB connection refused**
- Confirm `.env` has correct `ALLOYDB_REGION`, `ALLOYDB_CLUSTER`, `ALLOYDB_INSTANCE`
- Enable Public IP: AlloyDB Console → Instance → Edit → Connectivity
- Wait 1–2 min after provisioning before connecting

**Agent health checks**
```bash
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8083/health
curl http://localhost:8080/api/health
```

**Cleanup**
```bash
sh deploy/cleanup.sh
```

---

## Design Decisions

**Why code execution for vision?**
Asking an LLM to count items and return a number is unreliable. Giving it a Python interpreter and asking it to write counting logic, then run it, produces deterministic, auditable results with exact bounding boxes per detected object.

**Why a governance layer?**
Enterprises cannot allow agents to run unchecked. Every request must be validated, policy-enforced, and logged before any agent executes.

**Why observability?**
Decisions without audit trails are liabilities. Every agent action is traceable by workflow ID for compliance, debugging, and enterprise reporting.

**Why a separate Logistics Agent?**
Shipping calculation is deterministic and domain-specific. Keeping it as a dedicated A2A agent keeps the system modular and the shipping logic independently testable and replaceable.

**Why ScaNN over pgvector HNSW?**
ScaNN delivers 10x faster filtered search vs HNSW with a 3-4x smaller memory footprint and 8x faster index builds — material for searching millions of supplier parts with attribute filters.

**Why A2A Protocol?**
Hard-coding agent interactions couples the system too tightly. A2A lets each agent advertise its capabilities via a standard card, making the system composable — swap the supplier agent, add a pricing agent, or integrate a logistics agent without touching orchestration code.

**Why MCP for post-order integrations?**
MCP provides a standardized way to connect agents to external tools like Gmail, Calendar, and Sheets without custom API wrappers for each. It keeps integrations modular and replaceable.

---

## References

- [Gemini 3 Flash Code Execution](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/code-execution-api)
- [AlloyDB ScaNN vs HNSW Benchmarks](https://cloud.google.com/blog/products/databases/how-scann-for-alloydb-vector-search-compares-to-pgvector-hnsw)
- [AlloyDB Python Connector](https://github.com/GoogleCloudPlatform/alloydb-python-connector)
- [A2A Protocol](https://google.github.io/A2A/)
- [AlloyDB AI Docs](https://cloud.google.com/alloydb/docs/ai)

---

## License
Apache-2.0
