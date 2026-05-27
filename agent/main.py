"""
Vecino — FastAPI backend for WhatsApp business intelligence.
"""
from __future__ import annotations

import asyncio
import base64
import os
import pathlib
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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


# ── WhatsApp pairing ───────────────────────────────────────────────────────

_CREDS = pathlib.Path.home() / ".hermes/platforms/whatsapp/session/creds.json"
_QR_FILE = pathlib.Path.home() / ".hermes/platforms/whatsapp/qr.png"


@app.get("/pair", response_class=HTMLResponse)
async def pair():
    """Serve a QR-code page for WhatsApp pairing.
    Runs 'hermes whatsapp --qr-web', captures the PNG from stdout,
    and embeds it as a data URI. Auto-refreshes via JS until paired."""
    img_src: str | None = None

    # 1. Try to get QR image from hermes subprocess (10-second timeout)
    try:
        proc = await asyncio.create_subprocess_exec(
            "hermes", "whatsapp", "--qr-web",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            stdout = b""

        raw = stdout.strip()
        if raw:
            # Accept both a ready data URI and raw base64 PNG bytes
            text = raw.decode("utf-8", errors="ignore")
            if text.startswith("data:"):
                img_src = text
            else:
                img_src = "data:image/png;base64," + base64.b64encode(raw).decode()
    except FileNotFoundError:
        pass  # hermes not installed — fall through to file fallback

    # 2. Fallback: QR image file written by the gateway
    if not img_src and _QR_FILE.exists():
        img_src = "data:image/png;base64," + base64.b64encode(_QR_FILE.read_bytes()).decode()

    if img_src:
        img_tag = f'<img src="{img_src}" alt="WhatsApp QR code">'
    else:
        img_tag = "<p class='error'>QR no disponible — reintentando en 5 segundos…</p>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vecino — Conectar WhatsApp</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f0e0d; color: #f0ede8;
      font-family: system-ui, sans-serif;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      min-height: 100vh; gap: 16px; padding: 24px;
    }}
    h1  {{ color: #E8A838; font-size: 22px; letter-spacing: -.02em; }}
    p   {{ color: #8a8070; font-size: 14px; text-align: center; }}
    img {{
      width: 280px; height: 280px;
      background: #fff; padding: 16px; border-radius: 12px;
    }}
    .error {{ color: #ef4444; }}
    #status {{ font-size: 13px; color: #4a4540; margin-top: 4px; }}
  </style>
</head>
<body>
  <h1>Vecino</h1>
  <p>Abre WhatsApp → Dispositivos vinculados → Vincular dispositivo<br>y escanea este código</p>
  {img_tag}
  <p id="status">Actualizando en 5 s…</p>
  <script>
    const statusEl = document.getElementById('status');
    let countdown = 5;
    const tick = setInterval(() => {{
      countdown -= 1;
      statusEl.textContent = countdown > 0
        ? `Actualizando en ${{countdown}} s…`
        : 'Verificando…';
    }}, 1000);

    const poll = setInterval(async () => {{
      try {{
        const r = await fetch('/pair/status');
        const d = await r.json();
        if (d.paired) {{
          clearInterval(poll);
          clearInterval(tick);
          statusEl.textContent = '✅ ¡Conectado! Puedes cerrar esta página.';
        }} else {{
          location.reload();
        }}
      }} catch (_) {{
        location.reload();
      }}
    }}, 5000);
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/pair/status")
async def pair_status():
    """Returns {"paired": true} once WhatsApp session credentials exist."""
    return {"paired": _CREDS.exists()}


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
