"""
Vecino — WhatsApp-first business intelligence agent for Latin American small businesses.
Powered by Hermes Agent + Claude + Twilio.

Owner WhatsApp: +57 3227306058
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from collections import Counter

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse

import memory
import nlp
import scheduler as sched_module
import twilio_client

load_dotenv()

LOW_STOCK_THRESHOLD = 10.0


# ── Lifespan: start/stop APScheduler ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _scheduler = sched_module.create_scheduler()
    _scheduler.start()
    app.state.scheduler = _scheduler
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="Vecino", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Response helpers ───────────────────────────────────────────────────────

def twiml(text: str) -> Response:
    resp = MessagingResponse()
    resp.message(text)
    return Response(content=str(resp), media_type="application/xml")


# ── Intent handlers ────────────────────────────────────────────────────────

def _handle_stock_in(entities: dict) -> str:
    product  = entities.get("product", "").strip().lower()
    quantity = float(entities.get("quantity", 0))
    unit     = entities.get("unit", "unidades")

    if not product or quantity <= 0:
        return "No entendí bien. ¿Qué producto llegó y en qué cantidad? 📦"

    updated = memory.add_inventory(product, quantity, unit)
    total   = updated["quantity"]

    low = memory.get_low_stock(LOW_STOCK_THRESHOLD)
    alert = ""
    low_products = [i["product"] for i in low]
    if product not in low_products:
        pass  # just updated stock is fine
    elif total <= LOW_STOCK_THRESHOLD:
        alert = f"\n⚠️ Ojo — todavía quedan pocas unidades de {product} ({total} {unit})."

    return f"Listo, anoté {quantity} {unit} de {product}. Ahora tienes {total} {unit} en total. 📦{alert}"


def _handle_stock_query(entities: dict) -> str:
    product = entities.get("product", "").strip().lower()

    if not product:
        items = memory.get_inventory()
        if not items:
            return "El inventario está vacío. Empieza anotando lo que tienes. 📋"
        lines = [f"• {i['product']}: {i['quantity']} {i['unit']}" for i in items[:10]]
        header = f"Inventario actual ({len(items)} productos):\n"
        return header + "\n".join(lines)

    items = memory.get_inventory(product=product)
    if not items:
        return f"No tengo registro de {product} en el inventario. ¿Lo ingresamos? 🤔"

    item = items[0]
    qty  = item["quantity"]
    unit = item["unit"]

    if qty <= LOW_STOCK_THRESHOLD:
        return f"Tienes {qty} {unit} de {item['product']} 🌾 — ⚠️ stock bajo, considera pedir más pronto."
    return f"Tienes {qty} {unit} de {item['product']} 🌾"


def _handle_sale_log(entities: dict) -> str:
    product  = entities.get("product", "").strip().lower()
    quantity = float(entities.get("quantity", 0))
    unit     = entities.get("unit", "unidades")
    amount   = entities.get("amount")
    if amount:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = None

    if not product or quantity <= 0:
        return "No entendí bien la venta. ¿Qué vendiste y cuánto? 🧾"

    memory.log_sale(product, quantity, unit, amount=amount)

    # Running today's total
    today_sales = memory.get_sales_since(hours=24)
    today_total = sum(s["amount"] for s in today_sales if s["amount"])

    reply = f"Listo, anoté {quantity} {unit} de {product} ✅"
    if today_total:
        reply += f" Hoy llevas {today_total:,.0f} en ventas 💵"
    if amount:
        reply += f" (esta venta: {amount:,.0f})"
    reply += "."

    # Low stock alert after deducting
    inv = memory.get_inventory(product=product)
    if inv and inv[0]["quantity"] <= LOW_STOCK_THRESHOLD:
        reply += f"\n⚠️ El {product} está bajando — solo quedan {inv[0]['quantity']} {inv[0]['unit']}."

    return reply


def _handle_order_log(entities: dict) -> str:
    supplier = entities.get("supplier", "proveedor").strip()
    product  = entities.get("product", "").strip().lower()
    quantity = float(entities.get("quantity", 0))
    unit     = entities.get("unit", "unidades")
    expected = entities.get("expected_date", "por confirmar")

    if not product or quantity <= 0:
        return "No entendí bien el pedido. ¿A quién le pediste, qué producto y cuánto? 📋"

    memory.log_order(supplier, product, quantity, unit, expected)
    return (
        f"Pedido anotado ✅\n"
        f"Proveedor: {supplier}\n"
        f"Producto: {quantity} {unit} de {product}\n"
        f"Llegada esperada: {expected}"
    )


async def _handle_summary_request() -> str:
    return await asyncio.to_thread(sched_module.build_daily_summary)


def _handle_unknown() -> str:
    return (
        "No entendí bien 😅 Puedo ayudarte con:\n"
        "• Anotar lo que llegó: \"llegaron 50 cajas de harina\"\n"
        "• Ver inventario: \"cuánto tengo de arroz\"\n"
        "• Registrar una venta: \"vendí 5 bolsas de café\"\n"
        "• Pedir a proveedor: \"pedí 100 kg a Polar\"\n"
        "• Resumen del día: \"resumen del día\""
    )


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/webhook")
async def webhook(
    Body: str = Form(default=""),
    From: str = Form(default=""),
):
    message = Body.strip()
    sender  = From.strip()

    memory.log_step("webhook:receive", sender, message, "running")

    # Parse intent in thread pool (sync Anthropic client)
    parsed  = await asyncio.to_thread(nlp.parse_intent, message)
    intent  = parsed.get("intent", "UNKNOWN")
    entities = parsed.get("entities", {})

    memory.log_step(f"nlp:{intent}", message, str(entities), "done")

    if intent == "STOCK_IN":
        reply = _handle_stock_in(entities)
    elif intent == "STOCK_QUERY":
        reply = _handle_stock_query(entities)
    elif intent == "SALE_LOG":
        reply = _handle_sale_log(entities)
    elif intent == "ORDER_LOG":
        reply = _handle_order_log(entities)
    elif intent == "SUMMARY_REQUEST":
        reply = await _handle_summary_request()
    else:
        reply = _handle_unknown()

    memory.log_step("webhook:reply", intent, reply, "done")

    return twiml(reply)


@app.post("/api/summary")
async def api_summary():
    """Generate a daily summary in plain Spanish and return as JSON."""
    text = await asyncio.to_thread(sched_module.build_daily_summary)
    return {"summary": text}


@app.get("/api/inventory")
async def api_inventory():
    """Return the full current inventory as JSON."""
    items = await asyncio.to_thread(memory.get_inventory)
    return {"inventory": items, "count": len(items)}


@app.get("/api/sales")
async def api_sales(hours: int = 24):
    """Return sales from the last N hours (default 24)."""
    sales = await asyncio.to_thread(memory.get_sales_since, hours)
    return {"sales": sales, "count": len(sales)}


@app.get("/api/orders")
async def api_orders():
    """Return all logged supplier orders."""
    orders = await asyncio.to_thread(memory.get_orders)
    return {"orders": orders, "count": len(orders)}


@app.get("/api/steps")
async def api_steps():
    """Return the last 100 agent execution steps."""
    steps = await asyncio.to_thread(memory.get_steps)
    return {"steps": steps, "count": len(steps)}
