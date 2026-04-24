"""
Supplier Agent Executor: Bridges A2A protocol to AlloyDB ScaNN search.

Security guardrails added:
  - Query length cap to prevent oversized payloads
  - Query character allowlist (alphanumeric + common punctuation only)
  - Confidence score calculation validated against ScaNN distance range
  - Explicit error messages without leaking internal stack traces to caller
"""
import asyncio
import json
import logging
import os
import re

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from inventory import find_supplier, find_supplier_by_image, get_embedding

logger = logging.getLogger(__name__)

# ── Input guardrails ──────────────────────────────────────────────────────────
MAX_QUERY_LENGTH = 300  # characters
# Allowlist: letters, digits, spaces, hyphens, commas, periods, apostrophes
SAFE_QUERY_RE = re.compile(r"^[a-zA-Z0-9\s\-,\.\'\(\)\/]+$")


def sanitize_supplier_query(query: str) -> str:
    """
    Validates and sanitizes the supplier search query.
    - Truncates to MAX_QUERY_LENGTH
    - Strips characters outside the allowlist
    - Raises ValueError if nothing usable remains
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string.")

    query = query[:MAX_QUERY_LENGTH].strip()

    if not SAFE_QUERY_RE.match(query):
        # Strip disallowed characters rather than rejecting outright
        sanitized = re.sub(r"[^a-zA-Z0-9\s\-,\.\'\(\)\/]", "", query).strip()
        if not sanitized:
            raise ValueError(
                "Query contains no usable characters after sanitization. "
                "Use plain text (letters, numbers, hyphens, commas)."
            )
        logger.warning(
            f"Supplier query contained disallowed characters. "
            f"Original length: {len(query)}, sanitized: '{sanitized[:60]}'"
        )
        return sanitized

    return query


def compute_confidence(distance: float) -> str:
    """
    Converts a ScaNN cosine distance to a human-readable confidence percentage.
    ScaNN cosine distance range: 0 (identical) to 2 (opposite).
    Clamps to [0, 100] to handle edge cases.
    """
    if distance is None:
        return "N/A"
    # Cosine similarity = 1 - distance; scale to percentage
    similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
    return f"{similarity * 100:.1f}%"


class SupplierAgentExecutor(AgentExecutor):
    """A2A executor that searches inventory via AlloyDB ScaNN vector search."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = getattr(context, 'message', None) or getattr(context, 'request_message', None)
        parts = message.parts if message and hasattr(message, 'parts') else []

        query = None
        embedding = None
        image_base64 = None

        for p in parts:
            text = getattr(p, "text", None)
            if not text and hasattr(p, "root"):
                text = getattr(p.root, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    query = data.get("query")
                    embedding = data.get("embedding")
                    image_base64 = data.get("image_base64")  # Challenge 1
                except json.JSONDecodeError:
                    query = text

        if not query and not embedding and not image_base64:
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Error: Provide 'query' (text), 'embedding' (vector), or 'image_base64' in JSON."
                )
            )
            return

        # ── Challenge 1: Image-based search ──
        if image_base64 and not query and not embedding:
            try:
                import base64 as b64lib
                image_bytes = b64lib.b64decode(image_base64)
                logger.info(f"Image-based supplier search: {len(image_bytes)} bytes")
                result = await asyncio.to_thread(find_supplier_by_image, image_bytes)
                if result:
                    part_name = result[0]
                    supplier_name = result[1]
                    distance = result[2] if len(result) > 2 else None
                    confidence = compute_confidence(distance)
                    logger.info(f"Image search match: {part_name} from {supplier_name} ({confidence})")
                    out = {
                        "part": part_name,
                        "supplier": supplier_name,
                        "match_confidence": confidence,
                        "search_mode": "multimodal_image",
                    }
                    await event_queue.enqueue_event(new_agent_text_message(json.dumps(out, indent=2)))
                    return
                else:
                    logger.info("Image search returned no result, falling back to text query")
                    query = "warehouse inventory parts"
            except Exception as e:
                logger.error(f"Image-based search failed, falling back to text: {e}")
                query = "warehouse inventory parts"

        # ── Guardrail: sanitize text query ──
        if query and not embedding:
            try:
                query = sanitize_supplier_query(query)
            except ValueError as e:
                logger.warning(f"Supplier query rejected by sanitizer: {e}")
                await event_queue.enqueue_event(
                    new_agent_text_message(f"Input rejected: {e}")
                )
                return

        try:
            emb = embedding if embedding else get_embedding(query)
            result = find_supplier(emb)

            if not result:
                await event_queue.enqueue_event(
                    new_agent_text_message("No matching supplier found in inventory.")
                )
                return

        except Exception as e:
            # Log full trace internally; return generic message to caller (no stack trace leakage)
            logger.error(f"Supplier agent exception: {e}", exc_info=True)
            await event_queue.enqueue_event(
                new_agent_text_message("Database error: Unable to retrieve supplier data. Please try again.")
            )
            return

        part_name = result[0]
        supplier_name = result[1]
        distance = result[2] if len(result) > 2 else None

        # ── Confidence: validated calculation (not hardcoded fallback) ──
        confidence = compute_confidence(distance)

        logger.info(f"Supplier match: {part_name} from {supplier_name} (confidence: {confidence})")

        out = {
            "part": part_name,
            "supplier": supplier_name,
            "match_confidence": confidence,
        }
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(out, indent=2)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Gracefully signal cancellation (not supported — log and no-op)."""
        logger.warning("Cancel requested for SupplierAgentExecutor — cancel is not supported.")
