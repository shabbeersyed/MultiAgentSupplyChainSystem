# Autonomous Supply Chain: Vision × Vector × Agents

An end-to-end **enterprise-grade agentic supply chain system** — combining computer vision, semantic vector search, governance, observability, and agent-to-agent orchestration to automate physical inventory management.

## What It Does

Upload a photo of a warehouse shelf. The system:
1. **Validates** the request through a governance layer
2. **Counts** inventory items deterministically via vision AI
3. **Searches** millions of supplier parts semantically
4. **Traces** every agent decision with full audit logging
5. **Surfaces** the best supplier match — autonomously

## Enterprise Architecture
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
## Enterprise Features

### 🔒 Governance Layer
Every request is validated before any agent runs:
- Input validation (image type, size limits)
- Prompt injection detection and blocking
- High-risk order flagging with human approval requirement
- Full audit logging with unique request IDs

### 🔍 Observability & Audit Trail
Every agent execution is fully traceable:
- Per-agent execution tracing (start time, duration, status)
- Workflow-level tracking across all agents via workflow ID
- Structured audit logs for compliance
- Complete decision history retrievable by workflow ID

### 🤖 Multi-Agent Collaboration
Three specialized agents via A2A Protocol:
- **Vision Agent** — sees and counts inventory
- **Supplier Agent** — finds best matching parts semantically
- **Control Tower** — orchestrates, streams results in real-time

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Governance | Custom Python layer | Enterprise policy enforcement |
| Observability | Structured logging + tracing | Full audit trail |
| Vision | Gemini 3 Flash + Code Execution | Deterministic counting |
| Query Gen | Gemini 2.5 Flash Lite | Fast structured output |
| Vector DB | AlloyDB AI + ScaNN | 10× faster than HNSW |
| Embeddings | Vertex AI text-embedding-005 | Real semantic similarity |
| Backend | FastAPI | WebSocket, async-native |
| Agent Protocol | A2A | Plug-and-play agent discovery |

## Repository Structure
MultiAgentSupplyChainSystem/
├── agents/
│   ├── governance.py         # Input validation, prompt injection protection
│   ├── observability.py      # Per-agent tracing, audit logging
│   ├── vision-agent/         # Gemini vision + query generation
│   └── supplier-agent/       # AlloyDB ScaNN search
│
├── tests/
│   ├── test_governance.py    # 4 passing tests
│   └── test_observability.py # 3 passing tests
│
├── frontend/
│   ├── app.py                # FastAPI + WebSocket server
│   └── static/               # Control Tower UI
│
├── database/
│   ├── seed.py               # DB seeding via AlloyDB Connector
│   └── seed_data.sql         # Schema + 20 inventory items
│
└── test-images/              # Sample warehouse images
## Getting Started

### Prerequisites
- Google Cloud Project with billing enabled
- `gcloud` CLI configured
- Python 3.9+

### Run Locally

```bash
git clone https://github.com/shabbeersyed/MultiAgentSupplyChainSystem
cd MultiAgentSupplyChainSystem
sh setup.sh
sh run.sh
```

Open **http://localhost:8080** for the Control Tower.

### Run Tests

```bash
python tests/test_governance.py
python tests/test_observability.py
```

## Security & Guardrails

| Threat | Mitigation |
|---|---|
| Prompt Injection | Pattern matching blocks known attack phrases |
| Oversized inputs | Image size capped at 5MB |
| Invalid file types | Allowlist: jpeg, png, webp only |
| Risky orders | Quantities >1000 require human approval |
| Untraced decisions | Every agent action logged with workflow ID |

## Design Decisions

**Why code execution for vision?**
Asking an LLM to count items is unreliable. Having it write and run Python counting logic produces deterministic, auditable results.

**Why a governance layer?**
Enterprises cannot allow agents to run unchecked. Every request must be validated, policy-enforced, and logged before execution.

**Why observability?**
Decisions without audit trails are liabilities. Every agent action is traceable by workflow ID for compliance and debugging.

**Why ScaNN over pgvector HNSW?**
10× faster filtered search, 3-4× smaller memory footprint, 8× faster index builds at scale.

**Why A2A Protocol?**
Hard-coding agent interactions couples the system too tightly. A2A lets agents advertise capabilities and remain composable.

## License
Apache-2.0

