"""
Logistics Agent Executor: Bridges A2A protocol to shipping calculator.
Challenge 3 — Multi-Agent Composition.

Accepts JSON: {
    "supplier": "Acme Corp",
    "item_type": "cardboard boxes",
    "item_count": 14,
    "destination": "New York, NY"  # optional
}
"""
import json
import logging
import os

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from shipping import calculate_shipping

logger = logging.getLogger(__name__)


class LogisticsAgentExecutor(AgentExecutor):
    """A2A executor that calculates shipping cost and ETA."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = getattr(context, "message", None) or getattr(context, "request_message", None)
        parts = message.parts if message and hasattr(message, "parts") else []

        supplier = None
        item_type = None
        item_count = 1
        destination = "New York, NY"

        for p in parts:
            text = getattr(p, "text", None)
            if not text and hasattr(p, "root"):
                text = getattr(p.root, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    supplier = data.get("supplier", supplier)
                    item_type = data.get("item_type", data.get("part", item_type))
                    item_count = int(data.get("item_count", data.get("count", item_count)))
                    destination = data.get("destination", destination)
                except (json.JSONDecodeError, ValueError):
                    pass

        if not supplier or not item_type:
            await event_queue.enqueue_event(
                new_agent_text_message(
                    'Error: Provide JSON with "supplier", "item_type", and "item_count".'
                )
            )
            return

        try:
            result = calculate_shipping(
                supplier_name=supplier,
                item_type=item_type,
                item_count=item_count,
                destination=destination,
            )
            await event_queue.enqueue_event(
                new_agent_text_message(json.dumps(result, indent=2))
            )
        except Exception as e:
            logger.error(f"Shipping calculation failed: {e}", exc_info=True)
            await event_queue.enqueue_event(
                new_agent_text_message("Error: Shipping calculation failed. Please try again.")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.warning("Cancel requested for LogisticsAgentExecutor — not supported.")
