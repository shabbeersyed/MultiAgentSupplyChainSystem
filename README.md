# Multi-Agent Supply Chain System

An end-to-end autonomous supply chain system that combines computer vision, semantic vector search, and agent-to-agent orchestration to automate physical inventory management — no human counting, classifying, or reordering required.

## What It Does

Upload a photo of a warehouse shelf. The system counts what's there, identifies what's running low, searches a supplier parts database semantically, and surfaces the best matches — entirely on its own.

## How It Works

The system is made up of four services that communicate in real time:

**Vision Agent** (port 8081) — receives an image, uses Gemini 3 Flash with Code Execution to count inventory items deterministically, then generates structured semantic search queries from what it sees.

**Supplier Agent** (port 8082) — takes those queries and searches the parts database using AlloyDB's ScaNN vector index, returning the most semantically similar supplier matches.

**Logistics Agent** (port 8083) — handles order routing and fulfillment decisions once a supplier match is identified.

**Control Tower** (port 8080) — the browser-based UI that orchestrates all three agents over WebSocket, compresses uploaded images, and streams results live.

Each agent exposes a `/.well-known/agent-card.json` following the A2A Protocol, making them independently discoverable and swappable.

## Architecture

```
Control Tower (port 8080)
  FastAPI + WebSocket + PIL image compression
       │
       ├──▶ Vision Agent (port 8081)
       │       Gemini 3 Flash + Code Execution
       │       → Gemini 2.5 Flash Lite for query generation
       │
       ├──▶ Supplier Agent (port 8082)
       │       AlloyDB ScaNN vector search
       │       Vertex AI text-embedding-005
       │
       └──▶ Logistics Agent (port 8083)
               Order routing and fulfillment logic
```

## Tech Stack

| Layer | Technology |
|---|---|
| Vision & counting | Gemini 3 Flash with Code Execution |
| Query generation | Gemini 2.5 Flash Lite |
| Vector database | AlloyDB AI with ScaNN index |
| Embeddings | Vertex AI text-embedding-005 |
| DB connection | AlloyDB Python Connector (no Auth Proxy needed) |
| Backend | FastAPI (async, WebSocket-native) |
| Agent discovery | A2A Protocol |
| Containerization | Docker (Python 3.12 slim) |

## Repository Structure

```
MultiAgentSupplyChainSystem/
├── setup.sh                      # Environment setup: validates gcloud, enables APIs, generates .env
├── run.sh                        # Starts all four services with health checks
├── Dockerfile                    # Single-container build exposing port 8080
├── .env.example                  # Configuration template
├── tutorial.md                   # Step-by-step codelab guide
│
├── agents/
│   ├── vision-agent/             # Gemini vision + structured query generation
│   ├── supplier-agent/           # AlloyDB ScaNN semantic search
│   └── logistics-agent/          # Order routing and fulfillment
│
├── frontend/
│   ├── app.py                    # FastAPI + WebSocket server (Control Tower)
│   └── static/                   # Browser UI assets
│
├── database/
│   ├── seed.py                   # Seeds inventory via AlloyDB Connector
│   └── seed_data.sql             # Schema + 20 sample parts with vector embeddings
│
├── deploy/
│   └── deploy.sh                 # Cloud Run deployment script
│
├── assets/                       # Architecture diagrams and screenshots
└── test-images/                  # Sample warehouse shelf images for testing
```

## Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Python 3.9 or higher
- AlloyDB instance provisioned (see setup steps below)

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/shabbeersyed/MultiAgentSupplyChainSystem.git
cd MultiAgentSupplyChainSystem
```

### 2. Run setup

The setup script validates your environment, enables required GCP APIs, and generates a `.env` configuration file.

```bash
sh setup.sh
```

It will prompt you for:
- Your Gemini API key (get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))
- Your AlloyDB region, cluster, and instance details
- Your database password

You can re-run `sh setup.sh` safely at any time — it loads existing `.env` values.

### 3. Set up the database

Connect to AlloyDB Studio in the GCP Console and run the following SQL blocks in order.

Enable extensions:
```sql
CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;
```

Create the inventory table:
```sql
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    part_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    description TEXT,
    stock_level INT DEFAULT 0,
    part_embedding vector(768)
);
```

Seed sample data, generate embeddings, and create the ScaNN index (see `database/seed_data.sql` for the full SQL).

### 4. Enable Public IP on AlloyDB

In the AlloyDB Console → your instance → Edit → enable Public IP. The Python Connector handles authentication automatically — no authorized networks needed.

### 5. Start all services

```bash
sh run.sh
```

Open **http://localhost:8080** for the Control Tower UI.

### 6. Test the workflow

1. Upload a warehouse shelf image (or select one from `test-images/`)
2. Watch the Vision Agent count items and generate search queries
3. Watch the Supplier Agent return semantically matched parts
4. The system places an autonomous reorder

Toggle **DEMO mode** in the UI to pause at each stage and inspect what each agent is doing.

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```
GOOGLE_CLOUD_PROJECT=your-project-id
GEMINI_API_KEY=your-gemini-api-key
ALLOYDB_REGION=us-central1
ALLOYDB_CLUSTER=your-cluster-name
ALLOYDB_INSTANCE=your-instance-name
DB_USER=postgres
DB_PASS=your-db-password
DB_NAME=postgres
```

`ALLOYDB_PROJECT` and `ALLOYDB_SA_KEY_PATH` are only needed when connecting to a shared/workshop AlloyDB instance in a different GCP project.

## Health Checks

Verify each service is running:

```bash
curl http://localhost:8081/health   # Vision Agent
curl http://localhost:8082/health   # Supplier Agent
curl http://localhost:8083/health   # Logistics Agent
curl http://localhost:8080/api/health  # Control Tower
```

## Logs

All service logs are written to the `logs/` directory:

```
logs/vision-agent.log
logs/supplier-agent.log
logs/logistics-agent.log
logs/frontend.log
```

## Troubleshooting

**Port already in use:**
```bash
lsof -ti:8080 | xargs kill -9
lsof -ti:8081 | xargs kill -9
lsof -ti:8082 | xargs kill -9
lsof -ti:8083 | xargs kill -9
```

**AlloyDB connection refused:**
- Confirm your `.env` has the correct `ALLOYDB_REGION`, `ALLOYDB_CLUSTER`, and `ALLOYDB_INSTANCE`
- Enable Public IP on the instance (AlloyDB Console → Instance → Edit → Connectivity)
- Wait 1–2 minutes after provisioning before connecting

**Missing GCP APIs:**
- `setup.sh` will detect and offer to enable any missing APIs automatically
- Required: `aiplatform.googleapis.com`, `alloydb.googleapis.com`, `compute.googleapis.com`, `servicenetworking.googleapis.com`

## Deploying to Cloud Run

```bash
sh deploy/deploy.sh
```

The script reads your `.env`, builds containers, and deploys all services to Cloud Run with a public URL.

## Design Decisions

**Why Code Execution for vision?** Asking an LLM to count items and return a number is unreliable. Giving it a Python interpreter and asking it to write counting logic — then run it — produces deterministic, auditable results. The model explains its reasoning in code rather than prose.

**Why ScaNN over pgvector HNSW?** ScaNN is 10× faster for filtered search when indices exceed memory, with a 3–4× smaller memory footprint and 8× faster index builds. For searching millions of parts with attribute filters, that difference is significant.

**Why A2A Protocol?** Hard-coding agent interactions couples the system too tightly. A2A lets each agent advertise capabilities via a standard card, making the system composable — swap the supplier agent, add a pricing agent, integrate a different logistics provider — without touching orchestration code.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
