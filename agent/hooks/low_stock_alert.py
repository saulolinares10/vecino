"""
Hermes hook: low_stock_alert

Fires after every inventory write (add_inventory, log_sale).
If any product is at or below the threshold, a formatting subagent
generates a natural-language WhatsApp alert and sends it to the owner.
"""
from __future__ import annotations

import os

import anthropic
from dotenv import load_dotenv

from agent import memory
from agent import twilio_client

load_dotenv()

LOW_STOCK_THRESHOLD = float(os.environ.get("LOW_STOCK_THRESHOLD", 10))
OWNER_PHONE = os.environ.get("OWNER_PHONE", os.environ.get("TWILIO_WHATSAPP_TO", ""))

_ALERT_SYSTEM = """\
Eres Vecino, asistente de abasto. Redacta un aviso corto de stock bajo en español casual venezolano.
Una o dos líneas máximo. Sin markdown. Sin bullets. Con el emoji ⚠️ al principio.\
"""

_already_alerted: set[str] = set()


def register(agent) -> None:
    """Register inventory-write hooks onto the given HermesAgent."""

    @agent.on("after:add_inventory")
    def after_add(tool: str, input: dict, result: dict, **kwargs):
        _check_and_alert(result.get("product", input.get("product", "")))

    @agent.on("after:log_sale")
    def after_sale(tool: str, input: dict, result: dict, **kwargs):
        _check_and_alert(result.get("product", input.get("product", "")))


def _check_and_alert(updated_product: str) -> None:
    """
    Check all low-stock items. If any product is below threshold and hasn't
    been alerted recently, delegate formatting to a subagent and send via Twilio.
    """
    if not OWNER_PHONE:
        return

    low_items = memory.get_low_stock(LOW_STOCK_THRESHOLD)
    if not low_items:
        _already_alerted.clear()
        return

    # Only alert on items we haven't already flagged this session
    new_alerts = [i for i in low_items if i["product"] not in _already_alerted]
    if not new_alerts:
        return

    alert_text = _format_alert(new_alerts)
    if not alert_text:
        return

    try:
        twilio_client.send_message(OWNER_PHONE, alert_text)
        for item in new_alerts:
            _already_alerted.add(item["product"])
        memory.log_step(
            "hook:low_stock_alert",
            str([i["product"] for i in new_alerts]),
            alert_text,
            "done",
        )
    except Exception as exc:
        memory.log_step("hook:low_stock_alert", "send_failed", str(exc), "error")


def _format_alert(items: list[dict]) -> str:
    """
    Subagent: call Claude to produce a single natural-language low-stock alert.
    Separate Claude context from the main conversation.
    """
    if not items:
        return ""

    product_list = ", ".join(
        f"{i['product']} ({i['quantity']} {i['unit']})" for i in items
    )

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=80,
            system=_ALERT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Productos con stock bajo: {product_list}",
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception:
        # Fallback to a plain message if the subagent call fails
        names = ", ".join(i["product"] for i in items)
        return f"⚠️ Stock bajo: {names}."
