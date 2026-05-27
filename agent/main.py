"""
Vecino — Hermes Agent gateway for WhatsApp business intelligence.

The agent handles all message processing (tool use loop, NLP, memory
writes, low-stock alerting) through the Hermes framework. FastAPI is
kept only for the operator dashboard API.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

import memory
import scheduler as sched_module
from hermes import HermesAgent
from hooks import low_stock_alert

LOW_STOCK_THRESHOLD = float(os.environ.get("LOW_STOCK_THRESHOLD", 10))

# ── Hermes agent ───────────────────────────────────────────────────────────

agent = HermesAgent(
    name="vecino",
    model="claude-sonnet-4-6",
    skills_dir="skills",
    system_file="../SOUL.md",
)


# ── Tool registrations ─────────────────────────────────────────────────────

@agent.tool
def add_inventory(product: str, quantity: float, unit: str = "unidades") -> dict:
    """Add incoming stock for a product. Updates the running total and returns the new record."""
    return memory.add_inventory(product.lower().strip(), quantity, unit)


@agent.tool
def get_inventory(product: str = "") -> list:
    """Return current inventory. Pass a product name to filter, or empty string for all products."""
    return memory.get_inventory(product=product.lower().strip() if product else None)


@agent.tool
def log_sale(
    product: str,
    quantity: float,
    unit: str = "unidades",
    amount: float | None = None,
) -> dict:
    """Record a sale. Automatically deducts quantity from inventory. Returns the sale record."""
    return memory.log_sale(product.lower().strip(), quantity, unit, amount=amount)


@agent.tool
def log_order(
    supplier: str,
    product: str,
    quantity: float,
    unit: str = "unidades",
    expected_date: str = "por confirmar",
) -> dict:
    """Log a supplier order. Returns the logged order."""
    return memory.log_order(
        supplier, product.lower().strip(), quantity, unit, expected_date
    )


@agent.tool
def get_low_stock(threshold: float = 10.0) -> list:
    """Return all products with stock at or below threshold. Used for proactive alerts."""
    return memory.get_low_stock(threshold)


@agent.tool
def build_daily_summary() -> str:
    """Generate the end-of-day business summary in natural Venezuelan Spanish prose."""
    return sched_module.build_daily_summary()


@agent.tool
def build_weekly_summary() -> str:
    """Generate the weekly P&L summary in natural Venezuelan Spanish prose."""
    return sched_module.build_weekly_summary()


# ── Memory logging hooks ───────────────────────────────────────────────────

@agent.on("message:received")
def on_receive(sender: str, body: str, **kwargs):
    memory.log_message(sender, "inbound", body)
    memory.log_step("agent:receive", sender, body, "running")


@agent.on("message:sent")
def on_sent(sender: str, body: str, **kwargs):
    memory.log_message(sender, "outbound", body)
    memory.log_step("agent:reply", sender, body[:120], "done")


@agent.on("tool:called")
def on_tool_called(tool: str, input: dict, result: dict, **kwargs):
    memory.log_step(
        f"tool:{tool}",
        json.dumps(input, ensure_ascii=False),
        json.dumps(result, ensure_ascii=False),
        "done",
    )


# ── Low-stock alert hook ───────────────────────────────────────────────────

low_stock_alert.register(agent)


# ── Skill accumulation hook ────────────────────────────────────────────────

@agent.on("skill:accumulate")
def on_skill_accumulate(sender: str, count: int, **kwargs):
    """Every 15 interactions per business: compute and store observed patterns."""
    sales = memory.get_sales_since(hours=168)
    if not sales:
        return

    counter = Counter(s["product"] for s in sales)
    top_products = [
        {"product": p, "count": c} for p, c in counter.most_common(3)
    ]

    day_counter = Counter(
        datetime.fromisoformat(s["timestamp"]).strftime("%A") for s in sales
    )
    peak_day = day_counter.most_common(1)[0][0] if day_counter else "desconocido"

    memory.log_pattern(
        at_count=count,
        top_products=top_products,
        peak_day=peak_day,
        restock_notes=(
            f"Top productos: {', '.join(p['product'] for p in top_products)}. "
            f"Día pico: {peak_day}."
        ),
    )
    memory.log_step(
        "skill:accumulate",
        f"sender={sender} count={count}",
        f"top={top_products[0]['product'] if top_products else 'n/a'} peak={peak_day}",
        "done",
    )


# ── Lifespan: APScheduler ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    app.state.scheduler = None
    try:
        _scheduler = sched_module.create_scheduler()
        _scheduler.start()
        app.state.scheduler = _scheduler
    except Exception as exc:
        logging.warning("Scheduler failed to start (scheduled summaries disabled): %s", exc)
    yield
    if app.state.scheduler is not None:
        app.state.scheduler.shutdown(wait=False)


# ── FastAPI app ────────────────────────────────────────────────────────────

app = FastAPI(title="Vecino", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent.mount(app)  # registers POST /webhook with Hermes WhatsApp gateway


# ── Health ─────────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# ── Operator dashboard endpoints ───────────────────────────────────────────

@app.get("/api/inventory")
async def api_inventory():
    items = await asyncio.to_thread(memory.get_inventory)
    return {"inventory": items, "count": len(items)}


@app.get("/api/steps")
async def api_steps():
    steps = await asyncio.to_thread(memory.get_steps)
    return {"steps": steps, "count": len(steps)}


@app.get("/api/patterns")
async def api_patterns():
    patterns = await asyncio.to_thread(memory.get_patterns)
    return {"patterns": patterns, "count": len(patterns)}


@app.get("/api/messages")
async def api_messages():
    msgs = await asyncio.to_thread(memory.get_messages, 10)
    return {"messages": msgs, "count": len(msgs)}
