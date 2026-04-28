![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Tests](https://img.shields.io/badge/Tests-7%20passing-brightgreen)
![Agents](https://img.shields.io/badge/Agents-3-orange)
![Cloud](https://img.shields.io/badge/Cloud-GCP-blue)

# Autonomous Supply Chain: Vision × Vector × Agents

An end-to-end **enterprise-grade agentic supply chain system** — combining computer vision, semantic vector search, governance, observability, and agent-to-agent orchestration to automate physical inventory management.

---

## The Problem

Traditional warehouse inventory systems depend on humans to:
- Physically count items on shelves
- Manually look up supplier catalogs by SKU
- Decide when and what to reorder
- Track what decisions were made and why

This is slow, error-prone, and unscalable. This system eliminates all of it.

---

## The Solution

Upload a photo of a warehouse shelf. The system autonomously:
1. **Validates** the request through a governance layer
2. **Counts** inventory items deterministically via vision AI
3. **Searches** millions of supplier parts semantically
4. **Traces** every agent decision with full audit logging
5. **Surfaces** the best supplier match and places the order

No human in the loop. No manual SKU lookup. No guessing.

---

## Business Impact

| Problem | Without This System | With This System |
|---|---|---|
| Inventory counting | Manual, hours of labor, error-prone | Automated in seconds via vision AI |
| Stockout detection | Discovered after the fact | Detected proactively from shelf image |
| Supplier matching | Manual SKU lookup, catalog search | Semantic search across millions of parts |
| Audit compliance | No trace of decisions | Full audit log per request and agent |
| Large order risk | No controls or approval gates | Human approval enforced automatically |

**KPIs this system improves:**
- Reduces inventory counting time from hours to seconds
- Eliminates manual supplier lookup entirely
- Enforces compliance automatically with zero human overhead
- Provides full decision audit trail for enterprise governance
- Flags high-risk orders before they execute

---

## Enterprise Architecture

```
Request
   │
   ▼
Governance Layer (agents/governance.py)
   Validates input, blocks prompt injection,
   enforces policies, logs every request
   │
   ▼
Control Tower (8080)
   WebSocket + FastAPI + Observability
   Assigns workflow ID, traces all agents
   │
   ├──▶ Vision Agent (8081)
   │       Gemini 3 Flash + Code Execution
   │       Deterministic item counting
   │       Gemini 2.5 Flash Lite → query generation
   │
   └──▶ Supplier Agent (8082)
           AlloyDB ScaNN vector search
           Vertex AI text-embedding-005
           Returns best matching supplier part
```

Agents expose `/.well-known/agent-card.json` following the **A2A Protocol** — so they are discoverable and composable with other agents.

---

## Enterprise Features

### Governance Layer
Every request is validated before any agent runs:
- Image type and size validation (jpeg, png, webp only, max 5MB)
- Prompt injection detection and blocking
- High-risk order flagging — quantities over 1000 require human approval
- Full audit logging with unique request IDs and timestamps

### Observability and Audit Trail
Every agent execution is fully traceable:
- Per-agent execution tracing (start time, duration, status)
- Workflow-level tracking across all agents via workflow ID
- Structured audit logs written to file for compliance
- Complete decision history retrievable by workflow ID
- Success and failure capture with full error context

### Multi-Agent Collaboration via A2A Protocol
Three specialized agents working together:
- **Vision Agent** — sees and counts inventory from images
- **Supplier Agent** — finds best matching parts semantically
- **Control Tower** — orchestrates agents, streams results in real-time

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Governance | Custom Python layer | Enterprise policy enforcement before agent execution |
| Observability | Structured logging + tracing | Full audit trail across every workflow |
| Vision | Gemini 3 Flash + Code Execution | Deterministic counting, not hallucination |
| Query Gen | Gemini 2.5 Flash Lite | Fast structured output with Pydantic models |
| Vector DB | AlloyDB AI + ScaNN | 10x faster filtered search vs HNSW |
| Embeddings | Vertex AI text-embedding-005 | Real semantic similarity across part descriptions |
| DB Connection | AlloyDB Python Connector | IAM auth + managed SSL, no Auth Proxy needed |
| Backend | FastAPI | WebSocket support, async-native |
| Agent Protocol | A2A | Plug-and-play agent discovery and composability |

---

## Repository Structure

```
MultiAgentSupplyChainSystem/
├── agents/
│   ├── governance.py         # Input validation, prompt injection protection
│   ├── observability.py      # Per-agent tracing, audit logging
│   ├── vision-agent/         # Gemini vision + query generation
│   └── supplier-agent/       # AlloyDB ScaNN search
├── tests/
│   ├── test_governance.py    # 4 passing tests
│   └── test_observability.py # 3 passing tests
├── frontend/
│   ├── app.py                # FastAPI + WebSocket server
│   └── static/               # Control Tower UI
├── database/
│   ├── seed.py               # DB seeding via AlloyDB Connector
│   └── seed_data.sql         # Schema + 20 inventory items
├── deploy/
│   └── deploy.sh             # Cloud Run deployment script
├── test-images/              # Sample warehouse shelf images
├── Dockerfile                # Container configuration
├── setup.sh                  # Environment setup script
├── run.sh                    # Launches all three services
└── .env.example              # Config template
```

---

## Getting Started

### Prerequisites
- Google Cloud Project with billing enabled
- gcloud CLI configured
- Python 3.9+

### Run Locally

```bash
git clone https://github.com/shabbeersyed/MultiAgentSupplyChainSystem
cd MultiAgentSupplyChainSystem
sh setup.sh
sh run.sh
```

Open http://localhost:8080 for the Control Tower.

### Deploy to Cloud Run

```bash
sh deploy/deploy.sh
```

Reads your .env, builds containers, deploys with a public URL.

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

## Security and Guardrails

| Threat | Mitigation |
|---|---|
| Prompt Injection | Pattern matching blocks known attack phrases before agent execution |
| Oversized inputs | Image size capped at 5MB |
| Invalid file types | Allowlist enforced: jpeg, png, webp only |
| Risky orders | Quantities over 1000 require human approval |
| Untraced decisions | Every agent action logged with workflow ID |
| Data handling | No PII stored, audit logs contain only request metadata |

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

## Design Decisions

**Why code execution for vision?**
Asking an LLM to count items and return a number is unreliable. Giving it a Python interpreter and asking it to write counting logic, then run it, produces deterministic auditable results.

**Why a governance layer?**
Enterprises cannot allow agents to run unchecked. Every request must be validated, policy-enforced, and logged before any agent executes.

**Why observability?**
Decisions without audit trails are liabilities. Every agent action is traceable by workflow ID for compliance, debugging, and enterprise reporting.

**Why ScaNN over pgvector HNSW?**
ScaNN delivers 10x faster filtered search, 3-4x smaller memory footprint, and 8x faster index builds at scale — material differences when searching millions of parts with attribute filters.

**Why A2A Protocol?**
Hard-coding agent interactions couples the system too tightly. A2A lets each agent advertise its capabilities via a standard card, making the system composable — swap the supplier agent, add a pricing agent, integrate a logistics agent — without touching orchestration code.

---

## License
Apache-2.0

