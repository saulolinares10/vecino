"""
Vecino — FastAPI backend for WhatsApp business intelligence.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import pathlib
import re
import subprocess
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
_PHONE = os.environ.get("WHATSAPP_ALLOWED_USERS", "573227306058")


def _collect_pair_data() -> dict:
    """
    Sync helper (run via asyncio.to_thread) — three-tier fallback:
      1. hermes Python SDK  → qr bytes/str + pairing_code
      2. subprocess --json  → parse JSON for qr and pairing_code
      3. subprocess --phone → regex for 8-digit code
    Returns {"img_src": str|None, "pairing_code": str|None}
    """
    img_src: str | None = None
    pairing_code: str | None = None

    # ── Tier 1: hermes Python SDK ──────────────────────────────────────────
    try:
        import hermes as _hermes  # type: ignore
        client = _hermes.WhatsApp()
        qr = client.get_qr()
        if qr:
            if isinstance(qr, bytes):
                img_src = "data:image/png;base64," + base64.b64encode(qr).decode()
            elif str(qr).startswith("data:"):
                img_src = str(qr)
        get_code = getattr(client, "get_pairing_code", None)
        if callable(get_code):
            code = get_code()
            if code:
                pairing_code = str(code).strip()
    except Exception:
        pass

    # ── Tier 2: subprocess --json ──────────────────────────────────────────
    if not img_src and not pairing_code:
        try:
            result = subprocess.run(
                ["hermes", "whatsapp", "--json"],
                capture_output=True, timeout=10,
            )
            data = json.loads(result.stdout.decode("utf-8", errors="ignore"))
            raw_qr = data.get("qr") or data.get("qrCode") or data.get("qr_code")
            if raw_qr:
                s = str(raw_qr)
                if s.startswith("data:"):
                    img_src = s
                else:
                    img_src = "data:image/png;base64," + base64.b64encode(
                        raw_qr if isinstance(raw_qr, bytes) else s.encode()
                    ).decode()
            raw_code = (
                data.get("pairingCode")
                or data.get("pairing_code")
                or data.get("code")
            )
            if raw_code:
                pairing_code = str(raw_code).strip()
        except Exception:
            pass

    # ── Tier 3: subprocess --phone (8-digit code) ──────────────────────────
    if not pairing_code:
        try:
            result = subprocess.run(
                ["hermes", "whatsapp", "--phone", _PHONE],
                capture_output=True, timeout=15,
            )
            output = (
                result.stdout.decode("utf-8", errors="ignore")
                + result.stderr.decode("utf-8", errors="ignore")
            )
            match = re.search(r"\b(\d{4}[-\s]?\d{4}|\d{8})\b", output)
            if match:
                digits = re.sub(r"\D", "", match.group(1))
                pairing_code = digits[:4] + "-" + digits[4:]
        except Exception:
            pass

    return {"img_src": img_src, "pairing_code": pairing_code}


@app.get("/pair", response_class=HTMLResponse)
async def pair():
    """WhatsApp pairing page — QR code (Option A) and phone number code (Option B)."""
    data = await asyncio.to_thread(_collect_pair_data)

    img_src = data["img_src"]
    pairing_code = data["pairing_code"]

    # File fallback for QR
    if not img_src and _QR_FILE.exists():
        img_src = "data:image/png;base64," + base64.b64encode(_QR_FILE.read_bytes()).decode()

    # Build HTML fragments
    if img_src:
        option_a = f'<img src="{img_src}" alt="WhatsApp QR code">'
    else:
        option_a = "<p class='unavailable'>Código QR no disponible</p>"

    if pairing_code:
        option_b = f'<div class="pairing-code">{pairing_code}</div>'
    else:
        option_b = (
            f"<p class='unavailable'>Ejecuta en el servidor:<br>"
            f"<code>hermes whatsapp --phone {_PHONE}</code></p>"
        )

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
      min-height: 100vh; gap: 28px; padding: 24px;
    }}
    h1   {{ color: #E8A838; font-size: 22px; letter-spacing: -.02em; }}
    h2   {{ color: #a89880; font-size: 12px; text-transform: uppercase;
            letter-spacing: .08em; margin-bottom: 4px; }}
    p    {{ color: #8a8070; font-size: 14px; text-align: center; line-height: 1.5; }}
    code {{ background: #1e1c1a; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
    .options   {{ display: flex; gap: 28px; flex-wrap: wrap; justify-content: center; }}
    .option    {{
      background: #1a1815; border: 1px solid #2a2520; border-radius: 12px;
      padding: 24px; text-align: center;
      display: flex; flex-direction: column; align-items: center; gap: 14px;
      max-width: 280px; width: 100%;
    }}
    img  {{ width: 240px; height: 240px; background: #fff; padding: 12px; border-radius: 8px; }}
    .pairing-code {{
      font-size: 38px; font-weight: 700; letter-spacing: .15em;
      color: #E8A838; font-variant-numeric: tabular-nums;
      background: #1e1c1a; padding: 16px 28px; border-radius: 8px;
    }}
    .badge       {{ background: #2a4a2a; color: #6ecc6e;
                   font-size: 10px; padding: 2px 8px; border-radius: 20px; }}
    .unavailable {{ color: #605858; font-size: 13px; }}
    #status      {{ font-size: 13px; color: #4a4540; }}
  </style>
</head>
<body>
  <h1>Vecino — Conectar WhatsApp</h1>
  <div class="options">

    <div class="option">
      <h2>Opción A &mdash; Código QR</h2>
      <p>WhatsApp → Dispositivos vinculados → Vincular dispositivo → Escanear</p>
      {option_a}
    </div>

    <div class="option">
      <h2>Opción B &mdash; Número de teléfono <span class="badge">Recomendado</span></h2>
      <p>WhatsApp → Dispositivos vinculados → Vincular dispositivo → Vincular con número</p>
      {option_b}
      <p style="color:#605858;font-size:12px;">Ingresa este código cuando WhatsApp lo solicite</p>
    </div>

  </div>
  <p id="status">Verificando conexión…</p>
  <script>
    const statusEl = document.getElementById('status');
    let secs = 10;
    const tick = setInterval(() => {{
      secs -= 1;
      statusEl.textContent = secs > 0 ? `Verificando en ${{secs}} s…` : 'Verificando…';
    }}, 1000);

    const poll = setInterval(async () => {{
      try {{
        const r = await fetch('/pair/status');
        const d = await r.json();
        if (d.paired) {{
          clearInterval(poll); clearInterval(tick);
          statusEl.textContent = '✅ ¡Conectado! Puedes cerrar esta página.';
          document.querySelector('h1').textContent = 'Vecino — ¡Conectado! 🙌';
        }} else {{
          secs = 10;
        }}
      }} catch (_) {{ secs = 10; }}
    }}, 10000);
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
