"""
Vision Agent: A2A Server exposing audit_inventory skill.
Cloud Run compatible: listens on PORT env variable.
"""
import os
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import VisionAgentExecutor
from starlette.responses import JSONResponse
from starlette.routing import Route


VISION_AGENT_URL = os.environ.get(
    "VISION_AGENT_URL",
    "http://localhost:8081"
).rstrip("/")


skill = AgentSkill(
    id="audit_inventory",
    name="Audit Inventory via Image",
    description="Analyzes an image to count and identify inventory items using Gemini 3 Flash code execution.",
    tags=["vision", "counting", "audit", "supply-chain"],
    examples=[
        "Count the boxes in this warehouse image.",
        "Analyze this shelf and report item count.",
    ],
)

agent_card = AgentCard(
    name="Vision Inspection Agent",
    description="Autonomous computer vision agent that audits physical inventory from image payloads using Gemini 3 Flash.",
    url=VISION_AGENT_URL,
    version="1.0.0",
    default_input_modes=["text", "image"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(streaming=False),
    skills=[skill],
)

request_handler = DefaultRequestHandler(
    agent_executor=VisionAgentExecutor(),
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
            "agent": "vision",
            "agent_url": VISION_AGENT_URL,
        }
    )


app.routes.append(Route("/health", health, methods=["GET"]))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)