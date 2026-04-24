"""
Vision Agent Executor: Bridges A2A protocol to Gemini 3 Flash.
Uses Gemini 2.5 Flash Lite to dynamically extract item type and search query
from the vision result instead of hardcoding "cardboard boxes".
"""
import asyncio
import base64
import json
import logging
import os
import re

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from google import genai
from google.genai import types
from pydantic import BaseModel

from agent import analyze_image

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MAX_BASE64_LENGTH = 14 * 1024 * 1024


# ── Structured output schema for Flash Lite ──────────────────────────────────
class VisionStructuredOutput(BaseModel):
    count: int
    item_type: str          # e.g. "cardboard boxes", "ball bearings", "safety goggles"
    search_query: str       # e.g. "cardboard shipping boxes warehouse"
    summary: str


def extract_structured_output(raw_text: str, box_count: int) -> VisionStructuredOutput:
    """
    Uses Gemini 2.5 Flash Lite to parse the raw Gemini 3 Flash vision output
    into a structured object with dynamic item_type and search_query.
    Falls back to safe defaults if the call fails.
    """
    try:
        lite_client = genai.Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )
        prompt = f"""
You are a structured data extractor for a warehouse inventory system.

Given the following vision analysis output, extract:
1. item_type: the primary object type detected (plural if count > 1, singular if count == 1)
2. search_query: a concise 3-6 word supplier search query for this item type
3. count: the confirmed item count ({box_count} bounding boxes were detected)
4. summary: one sentence describing what was found

Vision output:
\"\"\"
{raw_text[:2000]}
\"\"\"

Respond ONLY with valid JSON matching this schema:
{{"count": int, "item_type": str, "search_query": str, "summary": str}}
"""
        response = lite_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        text = response.text.strip()
        data = json.loads(text)
        return VisionStructuredOutput(**data)
    except Exception as e:
        logger.warning(f"Flash Lite structured extraction failed, using defaults: {e}")
        # Safe fallback — still uses the real bounding box count
        item_word = "item" if box_count == 1 else "items"
        return VisionStructuredOutput(
            count=box_count,
            item_type=item_word,
            search_query="warehouse inventory items",
            summary=f"{box_count} {item_word} detected in image.",
        )


def extract_boxes_from_raw_text(raw_text: str) -> list:
    match = re.search(
        r"\[BOUNDING_BOXES\](.*?)\[/BOUNDING_BOXES\]",
        raw_text,
        re.DOTALL,
    )

    if not match:
        return []

    try:
        return json.loads(match.group(1).strip())
    except Exception as e:
        logger.warning(f"Could not parse bounding boxes from raw text: {e}")
        return []


class VisionAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info("=" * 80)
        logger.info("VISION AGENT EXECUTOR - EXECUTE CALLED")
        logger.info("=" * 80)

        message = getattr(context, "message", None) or getattr(context, "request_message", None)
        parts = message.parts if message and hasattr(message, "parts") else []

        image_base64 = None

        for p in parts:
            text = getattr(p, "text", None)
            if not text and hasattr(p, "root"):
                text = getattr(p.root, "text", None)

            if text:
                try:
                    data = json.loads(text)
                    image_base64 = data.get("image_base64")
                except json.JSONDecodeError:
                    pass

        if not image_base64:
            await event_queue.enqueue_event(
                new_agent_text_message("Error: No image. Send JSON: {\"image_base64\": \"<base64>\"}")
            )
            return

        if len(image_base64) > MAX_BASE64_LENGTH:
            await event_queue.enqueue_event(
                new_agent_text_message("Error: Image payload too large. Maximum image size is 10 MB.")
            )
            return

        try:
            image_bytes = base64.b64decode(image_base64)
            logger.info(f"Decoded image: {len(image_bytes)} bytes")
        except Exception as e:
            await event_queue.enqueue_event(
                new_agent_text_message(f"Error: Invalid image encoding — {e}")
            )
            return

        try:
            import asyncio

            result = await asyncio.to_thread(analyze_image, image_bytes)

            answer = result.get("answer", "")
            code_output = result.get("code_output", "")
            direct_boxes = result.get("boxes", [])

            raw_text = answer
            if code_output:
                raw_text = f"Code output: {code_output}\n\n{answer}"

            logger.info(f"Raw text length: {len(raw_text)} chars")
            logger.info(f"Direct boxes from agent.py: {len(direct_boxes)}")

        except ValueError as e:
            await event_queue.enqueue_event(new_agent_text_message(f"Input rejected: {e}"))
            return
        except Exception as e:
            logger.error(f"analyze_image failed unexpectedly: {e}", exc_info=True)
            await event_queue.enqueue_event(
                new_agent_text_message("Error: Image analysis failed. Please try again.")
            )
            return

        parsed_boxes = direct_boxes or extract_boxes_from_raw_text(raw_text)
        item_count = len(parsed_boxes)

        logger.info(f"Final bounding boxes passed to frontend: {item_count}")

        # ── Dynamically extract item type and search query via Flash Lite ──
        structured = await asyncio.to_thread(extract_structured_output, raw_text, item_count)

        item_type = structured.item_type
        confidence = "high" if item_count > 0 else "low"
        search_query = structured.search_query
        summary = structured.summary

        logger.info(f"Structured output: {item_count} {item_type}, query='{search_query}'")

        response_payload = {
            "count": item_count,
            "item_count": item_count,
            "type": item_type,
            "item_type": item_type,
            "confidence": confidence,
            "summary": summary,
            "search_query": search_query,
            "boxes": parsed_boxes,
            "bounding_boxes": parsed_boxes,
        }

        full_response = json.dumps(response_payload)
        full_response += f"\n\n[BOUNDING_BOXES]{json.dumps(parsed_boxes)}[/BOUNDING_BOXES]"

        logger.info("Vision analysis complete")
        await event_queue.enqueue_event(new_agent_text_message(full_response))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.warning("Cancel requested for VisionAgentExecutor — cancel is not supported.")