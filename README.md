# Autonomous Supply Chain: Vision × Vector × Agents

An end-to-end **agentic supply chain system** — combining computer vision, semantic vector search, agent-to-agent orchestration, and real-world integrations to automate physical inventory management.

**Live Demo:** https://visual-commerce-demo-693699778723.us-central1.run.app/

---

## Problem Statement

Most warehouse inventory systems rely on humans to physically count stock, identify shortages, and place reorders. This is slow, error-prone, and doesn't scale. This system replaces that entire workflow: upload a photo of a shelf, and the system autonomously counts what's there, finds the best-matched supplier, calculates shipping cost and ETA, and confirms the order via email, calendar, and a live spreadsheet — no human required.

---

## What It Does

Upload a photo of a warehouse shelf. Four specialized agents collaborate to:

1. **Count** what's on the shelf using deterministic computer vision
2. **Find** the best-matched supplier part via semantic vector search
3. **Calculate** shipping cost, carrier, and ETA
4. **Confirm** the order via Gmail, Google Calendar, and Google Sheets

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

All agents expose `/.well-known/agent-card.json` following the **A2A Protocol** — discoverable and composable without hard-coded wiring.

---

## Agents

| Agent | Port | Technology | Responsibility |
|-------|------|-----------|----------------|
| Vision Agent | 8081 | Gemini 3 Flash + Code Execution | Counts items deterministically from image, returns bounding boxes and semantic query |
| Supplier Agent | 8082 | AlloyDB ScaNN + Vertex AI Embeddings | Finds best-matched part and supplier via vector similarity search |
| Logistics Agent | 8083 | Zone-based shipping calculator | Calculates shipping cost, carrier, and ETA from supplier location to destination |
| Control Tower | 8080 | FastAPI + WebSocket | Orchestrates all agents via A2A, streams results live to UI |

### MCP Integrations (post-order)

After an order is placed, the Control Tower triggers three real-world integrations via Google APIs:

- **Gmail** — sends an HTML order confirmation email
- **Google Calendar** — creates a delivery date event on the primary calendar
- **Google Sheets** — appends an order log row (order ID, part, supplier, cost, carrier, ETA, origin)

---

## Security & Guardrails

**Vision Agent:**
- Image size capped at 10MB; unsupported MIME types rejected before any model call
- Prompt injection detection — 11 known injection patterns blocked (`ignore previous`, `act as`, `jailbreak`, etc.)
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
|-------|-----------|-----|
| Vision | Gemini 3 Flash + Code Execution | Deterministic counting — model writes and runs Python, not guesses |
| Query Gen | Gemini 2.5 Flash Lite | Fast structured output with Pydantic models |
| Vector DB | AlloyDB AI + ScaNN | 10× faster filtered search vs HNSW, 8× faster index builds |
| Embeddings | Vertex AI text-embedding-005 | Real semantic similarity across part descriptions |
| DB Connection | AlloyDB Python Connector | IAM auth + managed SSL, no Auth Proxy needed |
| Backend | FastAPI + WebSocket | Async-native, real-time event streaming to UI |
| Agent Protocol | A2A | Plug-and-play agent discovery and composability |
| Integrations | Gmail, Google Calendar, Google Sheets APIs | Real-world order confirmation and logging |

---

## Repository Structure

```
MultiAgentSupplyChainSystem/
├── setup.sh                          # Environment setup (APIs, .env generation)
├── run.sh                            # Launches all four services
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
│   └── static/                       # UI (index.html, app.js, styles.css)
│
├── database/
│   ├── seed.py                       # AlloyDB seeding via Connector
│   └── seed_data.sql                 # Schema + 20 inventory items
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
|----------|----------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | Vertex AI region (default: `global`) |
| `ALLOYDB_REGION` | Yes | GCP region of AlloyDB instance |
| `ALLOYDB_CLUSTER` | Yes | AlloyDB cluster name |
| `ALLOYDB_INSTANCE` | Yes | AlloyDB instance name |
| `DB_PASS` | Yes | AlloyDB postgres password |
| `OAUTH_CLIENT_ID` | Yes (MCP) | Google OAuth client ID for Gmail/Calendar/Sheets |
| `OAUTH_CLIENT_SECRET` | Yes (MCP) | Google OAuth client secret |
| `OAUTH_REFRESH_TOKEN` | Yes (MCP) | OAuth refresh token |
| `VISION_AGENT_URL` | No | Default: `http://localhost:8081` |
| `SUPPLIER_AGENT_URL` | No | Default: `http://localhost:8082` |
| `LOGISTICS_AGENT_URL` | No | Default: `http://localhost:8083` |

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

Open **http://localhost:8080** for the Control Tower.

### Deploy to Cloud Run

```bash
sh deploy/deploy.sh
```

---

## Design Decisions

**Why code execution for vision?**
Asking an LLM to count items and return a number is unreliable. Giving it a Python interpreter and asking it to write counting logic, then run it, produces deterministic, auditable results with exact bounding boxes per detected object.

**Why ScaNN over pgvector HNSW?**
ScaNN delivers 10× faster filtered search vs HNSW with a 3–4× smaller memory footprint and 8× faster index builds — material for searching millions of supplier parts with attribute filters.

**Why A2A Protocol?**
Hard-coding agent interactions couples the system too tightly. A2A lets each agent advertise its capabilities via a standard card, making the system composable — swap the supplier agent, add a pricing agent, or integrate a logistics agent without touching orchestration code.

**Why a separate Logistics Agent?**
Shipping calculation is deterministic and domain-specific (zone maps, carrier rules, weight tables). Keeping it as a dedicated A2A agent rather than inline logic in the Control Tower keeps the system modular and the shipping logic independently testable and replaceable.

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
