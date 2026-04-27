# Autonomous Supply Chain: Vision × Vector × Agents

An end-to-end agentic supply chain system — combining computer vision, semantic vector search, agent-to-agent orchestration, and real-world integrations to automate physical inventory management.

**Live Demo:** https://visual-commerce-demo-693699778723.us-central1.run.app/

---

## Problem Statement

Most warehouse inventory systems rely on humans to physically count stock, identify shortages, and place reorders. This is slow, error-prone, and doesn't scale. This system replaces that entire workflow: upload a photo of a shelf, and the system autonomously counts what's there, finds the best-matched supplier, calculates shipping cost and ETA, and confirms the order via email, calendar, and a live spreadsheet — no human required.

---

## What It Does

Upload a photo of a warehouse shelf. Four specialized agents collaborate to:

1. Count what's on the shelf using deterministic computer vision
2. Find the best-matched supplier part via semantic vector search
3. Calculate shipping cost, carrier, and ETA
4. Confirm the order via Gmail, Google Calendar, and Google Sheets

---

## Architecture

```
User uploads image
        │
        ▼
Control Tower (8080)  ← WebSocket + FastAPI + PIL image compression
        │
        │  A2A Protocol (agent discovery via /.well-known/agent-card.json)
        │
        ├──▶ Vision Agent (8081)
        │       Gemini 3 Flash + Code Execution → deterministic item count + bounding boxes
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

All agents expose `/.well-known/agent-card.json` following the A2A Protocol — discoverable and composable without hard-coded wiring.

---

## Agents

| Agent | Port | Technology | Responsibility |
|---|---|---|---|
| Vision Agent | 8081 | Gemini 3 Flash + Code Execution | Counts items deterministically from image, returns bounding boxes and semantic query |
| Supplier Agent | 8082 | AlloyDB ScaNN + Vertex AI Embeddings | Finds best-matched part and supplier via vector similarity search |
| Logistics Agent | 8083 | Zone-based shipping calculator | Calculates shipping cost, carrier, and ETA from supplier location to destination |
| Control Tower | 8080 | FastAPI + WebSocket | Orchestrates all agents via A2A, streams results live to UI |

---

## MCP Integrations

This system uses **MCP (Model Context Protocol)** to connect the AI pipeline to real-world business tools. After an order is confirmed, the Control Tower automatically triggers three MCP tools via `mcp_server.py` — no manual steps required.

### How it works

```
Order confirmed by Control Tower
        │
        ├──▶ send_gmail_email
        │       Sends an HTML order confirmation to the supplier
        │       Includes: part name, quantity, cost, carrier, ETA
        │
        ├──▶ create_calendar_event
        │       Creates a delivery date event on Google Calendar
        │       Title: "Delivery: <part> via <carrier>"
        │       Date: calculated from ETA days
        │
        └──▶ append_google_sheet_row
                Appends a row to the order log spreadsheet
                Columns: order ID, part, supplier, cost, carrier, ETA, origin
```

### MCP Tools

| Tool | Service | What it does |
|---|---|---|
| `send_gmail_email` | Gmail API | Sends HTML order confirmation email to supplier contact |
| `create_calendar_event` | Google Calendar API | Creates a delivery date event on the primary calendar |
| `append_google_sheet_row` | Google Sheets API | Appends order details as a new row in the order log |

### MCP Server

The MCP server is built with **FastMCP** and runs alongside the Control Tower (`frontend/mcp_server.py`):

```python
from fastmcp import FastMCP

mcp = FastMCP("Supply Chain Google MCP Tools")

@mcp.tool()
def send_gmail_email(to: str, subject: str, body: str) -> str: ...

@mcp.tool()
def create_calendar_event(title: str, date: str, description: str) -> str: ...

@mcp.tool()
def append_google_sheet_row(spreadsheet_id: str, row: str) -> str: ...
```

### MCP Setup

To enable real Gmail, Calendar, and Sheets actions you need a Google OAuth token:

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Desktop app)
3. Enable the following APIs: Gmail API, Google Calendar API, Google Sheets API
4. Add these to your `.env`:

```
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_REFRESH_TOKEN=your-refresh-token
```

### Why MCP?

MCP (Model Context Protocol) is an open standard for connecting AI agents to external tools and services. Using MCP here means:

- **Composable** — swap Gmail for Slack, or Sheets for Notion, without touching agent code
- **Standardized** — any MCP-compatible client can discover and call these tools
- **Auditable** — every tool call is logged with inputs and outputs
- **Extensible** — add new tools (SMS alerts, ERP updates, Slack notifications) in minutes

---

## Security & Guardrails

**Vision Agent:**
- Image size capped at 10MB; unsupported MIME types rejected before any model call
- Prompt injection detection — 11 known injection patterns blocked (ignore previous, act as, jailbreak, etc.)
- Queries sanitized and truncated to 500 characters before reaching Gemini

**Supplier Agent:**
- Query length capped at 300 characters
- Character allowlist enforced (alphanumeric + common punctuation only)
- Disallowed characters stripped rather than rejected; empty result raises explicit error
- Internal stack traces never returned to caller — generic error message surfaced instead
- Confidence scores computed from validated ScaNN cosine distance, not hardcoded

**Infrastructure:**
- IAM-based AlloyDB access — no credentials in code or Docker images
- All secrets loaded from `.env` / Cloud Run environment, excluded from Git
- Each agent runs as an isolated service on a separate port; Control Tower is the only user-facing entry point
- CORS restricted to configured allowed origins only

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Vision | Gemini 3 Flash + Code Execution | Deterministic counting — model writes and runs Python, not guesses |
| Query Gen | Gemini 2.5 Flash Lite | Fast structured output with Pydantic models |
| Vector DB | AlloyDB AI + ScaNN | 10× faster filtered search vs HNSW, 8× faster index builds |
| Embeddings | Vertex AI text-embedding-005 | Real semantic similarity across part descriptions |
| DB Connection | AlloyDB Python Connector | IAM auth + managed SSL, no Auth Proxy needed |
| Backend | FastAPI + WebSocket | Async-native, real-time event streaming to UI |
| Agent Protocol | A2A | Plug-and-play agent discovery and composability |
| MCP | FastMCP | Standardized tool protocol for Gmail, Calendar, Sheets |
| Integrations | Gmail, Google Calendar, Google Sheets APIs | Real-world order confirmation and logging |

---

## Repository Structure

```
MultiAgentSupplyChainSystem/
├── setup.sh                          # Environment setup (APIs, .env generation)
├── run.sh                            # Launches all four services
├── requirements-test.txt             # Test dependencies
├── deploy/
│   ├── deploy.sh                     # Cloud Run deployment
│   └── cleanup.sh                    # Tears down resources
├── .env.example                      # Config template
│
├── agents/
│   ├── vision-agent/
│   │   ├── agent.py                  # Gemini 3 Flash vision + bounding box logic
│   │   ├── agent_executor.py         # A2A server executor
│   │   └── main.py                   # FastAPI entrypoint
│   ├── supplier-agent/
│   │   ├── inventory.py              # AlloyDB ScaNN vector search
│   │   ├── agent_executor.py         # A2A executor + input guardrails
│   │   └── main.py                   # FastAPI entrypoint
│   └── logistics-agent/
│       ├── shipping.py               # Zone-based shipping cost + ETA calculator
│       ├── agent_executor.py         # A2A executor
│       └── main.py                   # FastAPI entrypoint
│
├── frontend/
│   ├── app.py                        # Control Tower: orchestration + WebSocket + MCP integrations
│   ├── mcp_server.py                 # FastMCP server — Gmail, Calendar, Sheets tools
│   └── static/                       # UI (index.html, app.js, styles.css)
│
├── database/
│   ├── seed.py                       # AlloyDB seeding via Connector
│   └── seed_data.sql                 # Schema + 20 inventory items
│
├── tests/
│   ├── conftest.py                   # pytest package marker
│   └── test_supply_chain.py          # 97 tests — vision, supplier, logistics, MCP
│
└── test-images/                      # Sample warehouse images
```

---

## Getting Started

### Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI configured
- Python 3.9+

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | Vertex AI region (default: global) |
| `ALLOYDB_REGION` | Yes | GCP region of AlloyDB instance |
| `ALLOYDB_CLUSTER` | Yes | AlloyDB cluster name |
| `ALLOYDB_INSTANCE` | Yes | AlloyDB instance name |
| `DB_PASS` | Yes | AlloyDB postgres password |
| `OAUTH_CLIENT_ID` | Yes (MCP) | Google OAuth client ID for Gmail/Calendar/Sheets |
| `OAUTH_CLIENT_SECRET` | Yes (MCP) | Google OAuth client secret |
| `OAUTH_REFRESH_TOKEN` | Yes (MCP) | OAuth refresh token |
| `VISION_AGENT_URL` | No | Default: http://localhost:8081 |
| `SUPPLIER_AGENT_URL` | No | Default: http://localhost:8082 |
| `LOGISTICS_AGENT_URL` | No | Default: http://localhost:8083 |

### Run Locally

```bash
# Clone
git clone https://github.com/shabbeersyed/MultiAgentSupplyChainSystem.git
cd MultiAgentSupplyChainSystem

# Set up environment (validates gcloud, enables APIs, creates .env)
sh setup.sh

# Provision AlloyDB and load schema (see database/seed_data.sql)

# Launch all services
sh run.sh
```

Open http://localhost:8080 for the Control Tower.

### Deploy to Cloud Run

```bash
sh deploy/deploy.sh
```

---

## Running Tests

No API keys or GCP credentials needed — all 97 tests run completely offline.

```bash
pip install pytest
pytest tests/test_supply_chain.py -v
```

| Test Class | Count | What it covers |
|---|---|---|
| `TestValidateImageInput` | 11 | Valid types, empty bytes, 10MB size limit, bad MIME types |
| `TestSanitizeVisionQuery` | 13 | All 11 injection patterns, truncation, None/empty inputs |
| `TestExtractBoundingBoxes` | 6 | Valid JSON, missing block, malformed JSON, empty array |
| `TestSanitizeSupplierQuery` | 10 | SQL injection, XSS attempts, truncation, allowlist chars |
| `TestComputeConfidence` | 9 | Distance 0→100%, distance 2→0%, None handling, clamping |
| `TestEstimateWeight` | 8 | All item types, default fallback, case insensitivity |
| `TestGetSupplierLocation` | 6 | Exact match, fuzzy match, unknown supplier default |
| `TestCalculateShipping` | 15 | All zones, handling fees, breakdown totals, ETA labels |
| `TestMcpTools` | 6 | Gmail, Calendar, Sheets confirmation contracts |
| `TestEndToEndLogic` | 5 | Full pipeline: vision → sanitize → logistics |
| **Total** | **97** | |

---

## Design Decisions

**Why code execution for vision?** Asking an LLM to count items and return a number is unreliable. Giving it a Python interpreter and asking it to write counting logic, then run it, produces deterministic, auditable results with exact bounding boxes per detected object.

**Why ScaNN over pgvector HNSW?** ScaNN delivers 10× faster filtered search vs HNSW with a 3–4× smaller memory footprint and 8× faster index builds — material for searching millions of supplier parts with attribute filters.

**Why A2A Protocol?** Hard-coding agent interactions couples the system too tightly. A2A lets each agent advertise its capabilities via a standard card, making the system composable — swap the supplier agent, add a pricing agent, or integrate a logistics agent without touching orchestration code.

**Why a separate Logistics Agent?** Shipping calculation is deterministic and domain-specific (zone maps, carrier rules, weight tables). Keeping it as a dedicated A2A agent rather than inline logic in the Control Tower keeps the system modular and the shipping logic independently testable and replaceable.

**Why MCP for integrations?** MCP provides a standardized, composable interface for connecting AI agents to external tools. It means integrations are swappable, auditable, and discoverable — adding a new tool like Slack or an ERP system requires no changes to agent orchestration code.

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

## References

- [Gemini 3 Flash Code Execution](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/code-execution-api)
- [AlloyDB ScaNN vs HNSW Benchmarks](https://cloud.google.com/blog/products/databases/how-scann-for-alloydb-vector-search-compares-to-pgvector-hnsw)
- [AlloyDB Python Connector](https://github.com/GoogleCloudPlatform/alloydb-python-connector)
- [A2A Protocol](https://google.github.io/A2A/)
- [AlloyDB AI Docs](https://cloud.google.com/alloydb/docs/ai)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://modelcontextprotocol.io/)
