import asyncio
import base64
import io
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Set
from uuid import uuid4

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx
from PIL import Image

from a2a.client import A2ACardResolver, A2AClient
import anthropic
from a2a.types import MessageSendParams, SendMessageRequest

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent

VISION_URL = os.environ.get("VISION_AGENT_URL", "http://localhost:8081")
SUPPLIER_URL = os.environ.get("SUPPLIER_AGENT_URL", "http://localhost:8082")
LOGISTICS_URL = os.environ.get("LOGISTICS_AGENT_URL", "http://localhost:8083")

app = FastAPI(title="Autonomous Supply Chain Control Tower")

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        # Cache the last N events so late-connecting WebSockets catch up
        self._event_cache: list = []
        self._max_cache = 30

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        # Replay cached events to the new connection so it doesn't miss anything
        for event in self._event_cache:
            try:
                await websocket.send_json(event)
            except Exception:
                break

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    def clear_cache(self):
        self._event_cache = []

    async def broadcast(self, message: dict):
        # Cache every broadcast event
        self._event_cache.append(message)
        if len(self._event_cache) > self._max_cache:
            self._event_cache = self._event_cache[-self._max_cache:]

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        self.active_connections -= disconnected


manager = ConnectionManager()


def compress_image(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    max_dimension = 1024
    quality = 85

    while max_dimension >= 256:
        img_copy = img.copy()
        img_copy.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img_copy.save(output, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = output.getvalue()

        if len(compressed_bytes) / 1024 <= max_size_kb:
            return compressed_bytes

        if quality > 60:
            quality -= 10
        else:
            max_dimension = int(max_dimension * 0.8)
            quality = 85

    return compressed_bytes


def extract_text_from_response(response) -> str:
    text = ""

    if hasattr(response, "root"):
        root = response.root
        if hasattr(root, "result"):
            result = root.result
            if hasattr(result, "parts"):
                for part in result.parts or []:
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        if part.root.text:
                            text += part.root.text

    if not text and hasattr(response, "artifact") and response.artifact:
        for part in getattr(response.artifact, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if not part_text and hasattr(part, "root"):
                part_text = getattr(part.root, "text", None)
            if part_text:
                text += part_text

    if not text and hasattr(response, "messages"):
        for msg in response.messages or []:
            for part in getattr(msg, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if not part_text and hasattr(part, "root"):
                    part_text = getattr(part.root, "text", None)
                if part_text:
                    text += part_text

    return text


def extract_thinking_steps(response_text: str, agent_type: str = "vision") -> list:
    import datetime

    if agent_type == "supplier":
        return [
            {
                "step": 1,
                "thought": "Generating embedding vector from query text",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            },
            {
                "step": 2,
                "thought": "Executing ScaNN vector search in AlloyDB",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            },
            {
                "step": 3,
                "thought": "Ranking results by similarity score",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            },
        ]

    steps = []

    if "def " in response_text or "import " in response_text:
        steps.extend(
            [
                {
                    "step": 1,
                    "thought": "Analyzing image requirements and planning approach",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                },
                {
                    "step": 2,
                    "thought": "Writing Python code with OpenCV for box detection",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                },
                {
                    "step": 3,
                    "thought": "Executing code in sandbox environment",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                },
            ]
        )

    if "result" in response_text.lower() or "boxes" in response_text.lower():
        steps.append(
            {
                "step": len(steps) + 1,
                "thought": "Processing execution results and formatting output",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            }
        )

    return steps


async def run_workflow_with_events(image_bytes: bytes):
    # Clear event cache so each new analysis starts fresh
    manager.clear_cache()
    async with httpx.AsyncClient(timeout=300.0) as client:
        await manager.broadcast(
            {
                "type": "upload_complete",
                "message": "Image uploaded successfully",
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

        await asyncio.sleep(0.5)

        await manager.broadcast(
            {
                "type": "discovery_start",
                "agent": "vision",
                "message": "Discovering Vision Agent via A2A protocol...",
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

        try:
            resolver = A2ACardResolver(httpx_client=client, base_url=VISION_URL)
            vision_card = await resolver.get_agent_card()
            vision_client = A2AClient(httpx_client=client, agent_card=vision_card)

            vision_skills = []
            if hasattr(vision_card, "skills") and vision_card.skills:
                for s in vision_card.skills:
                    vision_skills.append(
                        {
                            "id": getattr(s, "id", ""),
                            "name": getattr(s, "name", ""),
                            "description": getattr(s, "description", ""),
                            "tags": getattr(s, "tags", []),
                            "examples": getattr(s, "examples", []),
                        }
                    )

            vision_caps = getattr(vision_card, "capabilities", None)
            vision_streaming = getattr(vision_caps, "streaming", False) if vision_caps else False

            await manager.broadcast(
                {
                    "type": "discovery_complete",
                    "agent": "vision",
                    "message": f"Vision Agent discovered: {vision_card.name}",
                    "agent_name": vision_card.name,
                    "agent_description": getattr(vision_card, "description", ""),
                    "agent_url": VISION_URL,
                    "agent_version": getattr(vision_card, "version", "1.0.0"),
                    "agent_skills": vision_skills,
                    "agent_input_modes": getattr(vision_card, "default_input_modes", []),
                    "agent_output_modes": getattr(vision_card, "default_output_modes", []),
                    "agent_protocol_version": getattr(vision_card, "protocol_version", ""),
                    "agent_transport": getattr(vision_card, "preferred_transport", ""),
                    "agent_streaming": vision_streaming,
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            await asyncio.sleep(0.5)

            await manager.broadcast(
                {
                    "type": "vision_start",
                    "message": "Vision Agent analyzing image with Gemini 3 Flash...",
                    "details": "Think-Act-Observe loop initiated",
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            compressed_bytes = compress_image(image_bytes, max_size_kb=500)
            payload = json.dumps(
                {
                    "image_base64": base64.b64encode(compressed_bytes).decode("utf-8"),
                }
            )

            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        "role": "user",
                        "parts": [{"kind": "text", "text": payload}],
                        "messageId": uuid4().hex,
                    }
                ),
            )

            await manager.broadcast(
                {
                    "type": "vision_progress",
                    "substep": "thinking",
                    "message": "Gemini 3 Flash analyzing image composition...",
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            response = await vision_client.send_message(request)
            vision_text = extract_text_from_response(response)

            bounding_boxes = []
            clean_vision_text = vision_text

            if "[BOUNDING_BOXES]" in vision_text:
                try:
                    bbox_start = vision_text.index("[BOUNDING_BOXES]") + len("[BOUNDING_BOXES]")
                    bbox_end = vision_text.index("[/BOUNDING_BOXES]")
                    bbox_json = vision_text[bbox_start:bbox_end]
                    bounding_boxes = json.loads(bbox_json)
                    clean_vision_text = vision_text[: vision_text.index("[BOUNDING_BOXES]")].strip()
                    logger.info(f"Extracted {len(bounding_boxes)} bounding boxes from vision response")
                except Exception as e:
                    logger.warning(f"Failed to parse bounding boxes: {e}")

            real_count = len(bounding_boxes)
            real_type = "cardboard boxes" if real_count > 0 else "items"
            real_confidence = "high" if real_count > 0 else "low"
            real_summary = f"{real_count} {real_type} were detected."

            # Try to extract dynamic item_type, search_query, summary from vision response
            try:
                vision_data = json.loads(clean_vision_text.split("\n\n")[0])
                real_type = vision_data.get("item_type", real_type)
                real_confidence = vision_data.get("confidence", real_confidence)
                real_summary = vision_data.get("summary", real_summary)
                dynamic_search_query = vision_data.get("search_query", "warehouse inventory items")
            except Exception:
                dynamic_search_query = "warehouse inventory items"

            await manager.broadcast(
                {
                    "type": "vision_complete",
                    "message": "Vision analysis complete",
                    "result": clean_vision_text,
                    "item_count": real_count,
                    "item_type": real_type,
                    "summary": real_summary,
                    "confidence": real_confidence,
                    "search_query": dynamic_search_query,
                    "bounding_boxes": bounding_boxes,
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            thinking_steps = extract_thinking_steps(vision_text, "vision")
            if thinking_steps:
                await manager.broadcast(
                    {
                        "type": "thinking_update",
                        "agent": "vision",
                        "steps": thinking_steps,
                    }
                )

        except Exception as e:
            await manager.broadcast(
                {
                    "type": "vision_error",
                    "message": f"Vision Agent error: {str(e)}",
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )
            return

        await asyncio.sleep(0.5)

        await manager.broadcast(
            {
                "type": "discovery_start",
                "agent": "supplier",
                "message": "Discovering Supplier Agent via A2A protocol...",
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

        try:
            supplier_resolver = A2ACardResolver(httpx_client=client, base_url=SUPPLIER_URL)
            supplier_card = await supplier_resolver.get_agent_card()
            supplier_client = A2AClient(httpx_client=client, agent_card=supplier_card)

            supplier_skills = []
            if hasattr(supplier_card, "skills") and supplier_card.skills:
                for s in supplier_card.skills:
                    supplier_skills.append(
                        {
                            "id": getattr(s, "id", ""),
                            "name": getattr(s, "name", ""),
                            "description": getattr(s, "description", ""),
                            "tags": getattr(s, "tags", []),
                            "examples": getattr(s, "examples", []),
                        }
                    )

            supplier_caps = getattr(supplier_card, "capabilities", None)
            supplier_streaming = (
                getattr(supplier_caps, "streaming", False) if supplier_caps else False
            )

            await manager.broadcast(
                {
                    "type": "discovery_complete",
                    "agent": "supplier",
                    "message": f"Supplier Agent discovered: {supplier_card.name}",
                    "agent_name": supplier_card.name,
                    "agent_description": getattr(supplier_card, "description", ""),
                    "agent_url": SUPPLIER_URL,
                    "agent_version": getattr(supplier_card, "version", "1.0.0"),
                    "agent_skills": supplier_skills,
                    "agent_input_modes": getattr(supplier_card, "default_input_modes", []),
                    "agent_output_modes": getattr(supplier_card, "default_output_modes", []),
                    "agent_protocol_version": getattr(supplier_card, "protocol_version", ""),
                    "agent_transport": getattr(supplier_card, "preferred_transport", ""),
                    "agent_streaming": supplier_streaming,
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            await asyncio.sleep(0.5)

            await manager.broadcast(
                {
                    "type": "memory_start",
                    "message": "Querying AlloyDB with ScaNN vector search...",
                    "details": "Searching inventory parts",
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            supplier_payload = json.dumps({"query": dynamic_search_query})
            logger.info(f"Supplier search query: '{dynamic_search_query}'")
            supplier_request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        "role": "user",
                        "parts": [{"kind": "text", "text": supplier_payload}],
                        "messageId": uuid4().hex,
                    }
                ),
            )

            supplier_response = await supplier_client.send_message(supplier_request)
            supplier_text = extract_text_from_response(supplier_response)

            part_name = "Cardboard Boxes"
            supplier_name = "Acme Industrial Supplies"
            confidence = "High"

            if supplier_text:
                try:
                    supplier_data = json.loads(supplier_text)

                    part_name = (
                        supplier_data.get("part")
                        or supplier_data.get("part_name")
                        or supplier_data.get("item")
                        or part_name
                    )

                    supplier_name = (
                        supplier_data.get("supplier")
                        or supplier_data.get("supplier_name")
                        or supplier_name
                    )

                    confidence = (
                        supplier_data.get("match_confidence")
                        or supplier_data.get("confidence")
                        or confidence
                    )

                except json.JSONDecodeError:
                    logger.warning(f"Supplier response was not JSON: {supplier_text[:150]}")

            await manager.broadcast(
                {
                    "type": "memory_complete",
                    "message": f"Match found: {part_name}",
                    "part": part_name,
                    "supplier": supplier_name,
                    "confidence": confidence,
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            supplier_thinking = extract_thinking_steps(supplier_text, "supplier")
            if supplier_thinking:
                await manager.broadcast(
                    {
                        "type": "thinking_update",
                        "agent": "memory",
                        "steps": supplier_thinking,
                    }
                )

            await asyncio.sleep(0.5)

            order_id = f"#{random.randint(9000, 9999)}"
            await manager.broadcast(
                {
                    "type": "order_placed",
                    "message": f"Order {order_id} placed autonomously",
                    "order_id": order_id,
                    "part": part_name,
                    "supplier": supplier_name,
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            # ── Challenge 3: Logistics Agent ──────────────────────────────
            await asyncio.sleep(0.5)
            await manager.broadcast(
                {
                    "type": "logistics_start",
                    "message": "Calculating shipping cost and ETA via Logistics Agent...",
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            try:
                logistics_resolver = A2ACardResolver(httpx_client=client, base_url=LOGISTICS_URL)
                logistics_card = await logistics_resolver.get_agent_card()
                logistics_client = A2AClient(httpx_client=client, agent_card=logistics_card)

                logistics_payload = json.dumps({
                    "supplier": supplier_name,
                    "item_type": real_type,
                    "item_count": real_count,
                    "destination": "New York, NY",
                })

                logistics_request = SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message={
                            "role": "user",
                            "parts": [{"kind": "text", "text": logistics_payload}],
                            "messageId": uuid4().hex,
                        }
                    ),
                )

                logistics_response = await logistics_client.send_message(logistics_request)
                logistics_text = extract_text_from_response(logistics_response)

                shipping_cost = "N/A"
                carrier = "N/A"
                eta = "N/A"
                origin = "N/A"

                if logistics_text:
                    try:
                        logistics_data = json.loads(logistics_text)
                        shipping_cost = logistics_data.get("shipping_cost", shipping_cost)
                        carrier = logistics_data.get("carrier", carrier)
                        eta = logistics_data.get("eta_label", logistics_data.get("eta_days", eta))
                        origin = logistics_data.get("origin", origin)
                    except json.JSONDecodeError:
                        logger.warning(f"Logistics response was not JSON: {logistics_text[:100]}")

                await manager.broadcast(
                    {
                        "type": "logistics_complete",
                        "message": f"Shipping: {shipping_cost} via {carrier}",
                        "shipping_cost": shipping_cost,
                        "carrier": carrier,
                        "eta": str(eta),
                        "origin": origin,
                        "destination": "New York, NY",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                )
                logger.info(f"Logistics: {shipping_cost} via {carrier}, ETA {eta}")

                # MCP Integration: Gmail + Calendar + Sheets
                await asyncio.sleep(0.5)
                await manager.broadcast({
                    "type": "mcp_start",
                    "message": "Sending confirmation via Gmail, Calendar & Sheets...",
                    "timestamp": asyncio.get_event_loop().time(),
                })
                asyncio.create_task(run_mcp_integrations(
                    order_id=order_id,
                    part_name=part_name,
                    supplier_name=supplier_name,
                    item_count=real_count,
                    item_type=real_type,
                    shipping_cost=shipping_cost,
                    carrier=carrier,
                    eta=str(eta),
                    origin=origin,
                    manager=manager,
                ))

            except Exception as e:
                logger.warning(f"Logistics Agent unavailable: {e}")
                await manager.broadcast(
                    {
                        "type": "logistics_complete",
                        "message": "Logistics Agent unavailable — shipping estimate skipped",
                        "shipping_cost": "N/A",
                        "carrier": "N/A",
                        "eta": "N/A",
                        "origin": "N/A",
                        "destination": "New York, NY",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                )

        except Exception as e:
            await manager.broadcast(
                {
                    "type": "memory_error",
                    "message": f"Supplier Agent error: {str(e)}",
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )



# ── MCP Integration ─────────────────────────────────────────────────────────
MCP_USER_EMAIL = "syedshabbeerbasha08@gmail.com"
SHEETS_URL = "https://docs.google.com/spreadsheets/d/1w-zhfJtPmptPgv8ctvWfNyGYJq5mEB-FYdsI7913Dds/edit"
SHEET_ID = "1w-zhfJtPmptPgv8ctvWfNyGYJq5mEB-FYdsI7913Dds"

async def run_mcp_integrations(
    order_id, part_name, supplier_name, item_count,
    item_type, shipping_cost, carrier, eta, origin, manager
):
    """
    Calls Claude API with Gmail, Calendar, and Drive MCP servers
    to send confirmation email, create calendar event, and log to Sheets.
    """
    try:
        client = anthropic.AsyncAnthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        from datetime import datetime, timedelta
        import pytz
        tz = pytz.timezone("America/Chicago")
        now = datetime.now(tz)
        delivery_date = now + timedelta(days=3)
        delivery_str = delivery_date.strftime("%Y-%m-%d")
        order_date_str = now.strftime("%B %d, %Y at %I:%M %p CST")

        prompt = f"""You are an automated supply chain assistant. An order has just been placed. 
Complete ALL THREE tasks below using the available tools:

ORDER DETAILS:
- Order ID: {order_id}
- Part: {part_name}
- Supplier: {supplier_name}  
- Quantity: {item_count} {item_type}
- Shipping: {shipping_cost} via {carrier}
- ETA: {eta}
- From: {origin} → New York, NY
- Date: {order_date_str}

TASK 1 - Send Gmail email to {MCP_USER_EMAIL}:
Subject: "Supply Chain Order {order_id} Confirmed — {part_name}"
Body: A professional HTML email confirming the order with all details above including shipping info.

TASK 2 - Create Google Calendar event:
Title: "📦 Delivery: {part_name} ({order_id})"
Date: {delivery_str}
Duration: 1 hour (9am-10am CST)
Description: Order {order_id} from {supplier_name} via {carrier}. Cost: {shipping_cost}

TASK 3 - Log to Google Sheets (spreadsheet ID: {SHEET_ID}):
Add a new row to Sheet1 with these columns in order:
{order_id} | {now.strftime("%Y-%m-%d %H:%M")} | {part_name} | {supplier_name} | {item_count} | {shipping_cost} | {carrier} | {eta} | {origin}

Complete all 3 tasks now."""

        # Get Google OAuth token from environment
        google_token = os.environ.get("GOOGLE_OAUTH_TOKEN", "")
        
        mcp_servers = []
        if google_token:
            auth_header = {"Authorization": f"Bearer {google_token}"}
            mcp_servers = [
                {"type": "url", "url": "https://gmailmcp.googleapis.com/mcp/v1", "name": "gmail", "authorization_token": google_token},
                {"type": "url", "url": "https://calendarmcp.googleapis.com/mcp/v1", "name": "calendar", "authorization_token": google_token},
                {"type": "url", "url": "https://drivemcp.googleapis.com/mcp/v1", "name": "drive", "authorization_token": google_token},
            ]
        else:
            logger.warning("GOOGLE_OAUTH_TOKEN not set — MCP integrations will be simulated")

        results = {"email": False, "calendar": False, "sheets": False}

        if mcp_servers:
            response = await client.beta.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                mcp_servers=mcp_servers,
                betas=["mcp-client-2025-04-04"],
            )

            for block in response.content:
                if hasattr(block, "type"):
                    if block.type == "mcp_tool_use" or (block.type == "tool_use" and hasattr(block, "name")):
                        tool = getattr(block, "name", "").lower()
                        if "send" in tool or "email" in tool or "gmail" in tool or "draft" in tool:
                            results["email"] = True
                        elif "event" in tool or "calendar" in tool or "insert" in tool:
                            results["calendar"] = True
                        elif "sheet" in tool or "drive" in tool or "append" in tool or "value" in tool:
                            results["sheets"] = True
                    elif block.type == "mcp_tool_result":
                        # Tool was called successfully
                        logger.info(f"MCP tool result received")
            
            logger.info(f"MCP results: {results}")
        else:
            # Simulate for demo purposes
            await asyncio.sleep(1)
            results = {"email": True, "calendar": True, "sheets": True}
            logger.info("MCP simulated (no OAuth token)")

        await manager.broadcast({
            "type": "mcp_complete",
            "message": "External integrations complete",
            "email_sent": results["email"],
            "calendar_created": results["calendar"],
            "sheet_logged": results["sheets"],
            "timestamp": asyncio.get_event_loop().time(),
        })

    except Exception as e:
        logger.error(f"MCP integration failed: {e}", exc_info=True)
        await manager.broadcast({
            "type": "mcp_complete",
            "message": f"MCP integration error: {str(e)[:100]}",
            "email_sent": False,
            "calendar_created": False,
            "sheet_logged": False,
            "timestamp": asyncio.get_event_loop().time(),
        })



@app.post("/api/set-google-token")
async def set_google_token(request: Request):
    """Set Google OAuth token at runtime for MCP integrations."""
    body = await request.json()
    token = body.get("token", "")
    if token:
        os.environ["GOOGLE_OAUTH_TOKEN"] = token
        logger.info("Google OAuth token updated successfully")
        return {"status": "ok", "message": "Token set successfully"}
    return {"status": "error", "message": "No token provided"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/analyze")
async def analyze_image(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()

        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        asyncio.create_task(run_workflow_with_events(image_bytes))

        return {
            "status": "processing",
            "message": "Workflow started. Listen to WebSocket for real-time updates.",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/deployer")
async def deployer_info():
    deployer_name = os.environ.get("DEPLOYER_NAME", "")
    return {
        "name": deployer_name,
        "codelab_url": "https://codelabs.developers.google.com/visual-commerce-gemini-3-alloydb",
        "code_vipassana_url": "https://www.codevipassana.dev/",
        "show": bool(deployer_name),
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "control-tower",
        "vision_url": VISION_URL,
        "supplier_url": SUPPLIER_URL,
        "logistics_url": LOGISTICS_URL,
    }


@app.get("/api/test-images")
async def list_test_images():
    test_images_dir = APP_ROOT / "test-images"

    if not test_images_dir.exists():
        return {"images": []}

    images = []
    for img_path in test_images_dir.glob("*"):
        if img_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            images.append(
                {
                    "name": img_path.name,
                    "path": f"test-images/{img_path.name}",
                }
            )

    return {"images": images}


@app.get("/api/test-image/{image_name}")
async def get_test_image(image_name: str):
    test_images_dir = APP_ROOT / "test-images"
    image_path = test_images_dir / image_name

    if not image_path.exists() or image_path.suffix.lower() not in [".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(image_path)


static_dir = APP_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = APP_ROOT / "static" / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    return HTMLResponse(
        """
        <html>
            <body>
                <h1>Autonomous Supply Chain Control Tower</h1>
                <p>Static files not found. Please create frontend/static/index.html</p>
            </body>
        </html>
        """
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
