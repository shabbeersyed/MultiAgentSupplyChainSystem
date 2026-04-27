"""
Supplier Agent: A2A Server exposing search_inventory skill.
Cloud Run compatible: listens on PORT env variable.
Loads agent_card.json if present.
"""
import json
import os
from pathlib import Path

import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import SupplierAgentExecutor
from starlette.responses import JSONResponse
from starlette.routing import Route


SUPPLIER_AGENT_URL = os.environ.get(
    "SUPPLIER_AGENT_URL",
    "http://localhost:8082"
).rstrip("/")


skill = AgentSkill(
    id="search_inventory",
    name="Search Inventory",
    description="Searches the warehouse database for semantic matches using AlloyDB ScaNN vector search.",
    tags=["database", "inventory", "search", "alloydb"],
    examples=[
        "Find me the stock levels for industrial grade ball bearings.",
        "Who supplies Industrial Widget X-9?",
    ],
)


def _load_agent_card() -> AgentCard:
    card_path = Path(__file__).parent / "agent_card.json"

    if card_path.exists():
        with open(card_path) as f:
            data = json.load(f)

        skills = [
            AgentSkill(
                id=s["id"],
                name=s.get("name", s["id"]),
                description=s.get("description", ""),
                tags=s.get("tags", []),
                examples=s.get("examples", []),
            )
            for s in data.get("skills", [])
        ]

        return AgentCard(
            name=data.get("name", "Supplier Agent"),
            description=data.get("description", ""),
            url=SUPPLIER_AGENT_URL,
            version=data.get("version", "1.0.0"),
            default_input_modes=["text", "application/json"],
            default_output_modes=["text", "application/json"],
            capabilities=AgentCapabilities(streaming=False),
            skills=skills or [skill],
        )

    return AgentCard(
        name="Acme Supplier Agent",
        description="Autonomous fulfillment for industrial parts. Semantic search via AlloyDB.",
        url=SUPPLIER_AGENT_URL,
        version="1.0.0",
        default_input_modes=["text", "application/json"],
        default_output_modes=["text", "application/json"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


agent_card = _load_agent_card()

request_handler = DefaultRequestHandler(
    agent_executor=SupplierAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

a2a_app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=request_handler,
)

app = a2a_app.build()


async def health(request):
    return JSONResponse(
        {
            "status": "healthy",
            "agent": "supplier",
            "agent_url": SUPPLIER_AGENT_URL,
        }
    )


app.routes.append(Route("/health", health, methods=["GET"]))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)