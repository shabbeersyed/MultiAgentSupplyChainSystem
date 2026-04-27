"""
Logistics Agent: A2A Server exposing calculate_shipping skill.
Challenge 3 — Multi-Agent Composition.
Cloud Run compatible: listens on PORT env variable.
"""
import json
import os
from pathlib import Path

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import LogisticsAgentExecutor
from starlette.responses import JSONResponse
from starlette.routing import Route

LOGISTICS_AGENT_URL = os.environ.get(
    "LOGISTICS_AGENT_URL", "http://localhost:8083"
).rstrip("/")


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
            name=data.get("name", "Logistics Agent"),
            description=data.get("description", ""),
            url=LOGISTICS_AGENT_URL,
            version=data.get("version", "1.0.0"),
            default_input_modes=["text", "application/json"],
            default_output_modes=["text", "application/json"],
            capabilities=AgentCapabilities(streaming=False),
            skills=skills,
        )

    # Fallback
    skill = AgentSkill(
        id="calculate_shipping",
        name="Calculate Shipping",
        description="Calculates shipping cost and ETA for a given supplier, item, and destination.",
        tags=["logistics", "shipping", "cost", "eta"],
        examples=["Calculate shipping for 10 boxes from Acme Corp to New York"],
    )
    return AgentCard(
        name="Logistics Agent",
        description="Shipping cost and ETA calculator for autonomous supply chain.",
        url=LOGISTICS_AGENT_URL,
        version="1.0.0",
        default_input_modes=["text", "application/json"],
        default_output_modes=["text", "application/json"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


agent_card = _load_agent_card()

request_handler = DefaultRequestHandler(
    agent_executor=LogisticsAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

a2a_app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=request_handler,
)

app = a2a_app.build()


async def health(request):
    return JSONResponse({
        "status": "healthy",
        "agent": "logistics",
        "agent_url": LOGISTICS_AGENT_URL,
    })


app.routes.append(Route("/health", health, methods=["GET"]))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8083))
    uvicorn.run(app, host="0.0.0.0", port=port)
