"""
Vecino — FastAPI backend for WhatsApp business intelligence.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from agent import memory
from agent import scheduler as sched_module


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


# ── WhatsApp webhook ───────────────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    return {"status": "received", "body": body}


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
