"""
Vecino — FastAPI backend for WhatsApp business intelligence.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import re
import subprocess
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

load_dotenv()

from agent import memory
from agent import scheduler as sched_module


# ── WhatsApp phone-pairing helper (runs once at startup) ───────────────────

_PAIR_LOG = pathlib.Path("/tmp/pair_code.txt")
_PHONE = os.environ.get("WHATSAPP_ALLOWED_USERS", "573227306058")


def _run_hermes_pairing() -> None:
    """Blocking call — run in a daemon thread at startup.
    Tries each command in order; writes all output to _PAIR_LOG."""
    _commands = [
        ["hermes", "pairing", "--phone", _PHONE],
        ["hermes", "whatsapp", "pair", "--phone", _PHONE],
        ["hermes", "pairing"],
        ["hermes", "whatsapp"],
    ]

    log_lines: list[str] = []

    for cmd in _commands:
        label = " ".join(cmd)
        log_lines.append(f"--- trying: {label} ---\n")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            log_lines.append(result.stdout)
            if result.stderr:
                log_lines.append(result.stderr)
            _PAIR_LOG.write_text("".join(log_lines), encoding="utf-8")
            # Stop at first command that exits cleanly
            if result.returncode == 0:
                return
        except FileNotFoundError:
            log_lines.append(f"hermes not found in PATH\n")
            break
        except subprocess.TimeoutExpired:
            log_lines.append(f"timed out after 60 s\n")
        except Exception as exc:
            log_lines.append(f"error: {exc}\n")

    _PAIR_LOG.write_text("".join(log_lines), encoding="utf-8")


# ── Lifespan: APScheduler + pairing thread ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    # Start hermes phone-pairing in the background (captures output to _PAIR_LOG)
    threading.Thread(target=_run_hermes_pairing, daemon=True).start()
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


@app.get("/pair", response_class=HTMLResponse)
async def pair():
    """Read pairing output written by the startup thread; display 8-digit code large."""
    content = ""
    if _PAIR_LOG.exists():
        content = _PAIR_LOG.read_text(encoding="utf-8", errors="replace")

    match = re.search(r"\b\d{4}-\d{4}\b|\b\d{8}\b", content)
    if match:
        raw = match.group(0).replace("-", "")
        code = raw[:4] + "-" + raw[4:]
        code_html = (
            f'<div class="code">{code}</div>'
            f'<p class="hint">WhatsApp → Dispositivos vinculados → '
            f'Vincular dispositivo → Vincular con número de teléfono</p>'
        )
        status_init = "Ingresa el código en WhatsApp cuando lo solicite."
        has_code = "true"
    else:
        code_html = '<div class="waiting">⏳ Esperando código…</div>'
        status_init = "Generando código, reintentando en 5 s…"
        has_code = "false"

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
      min-height: 100vh; gap: 20px; padding: 24px; text-align: center;
    }}
    h1       {{ color: #E8A838; font-size: 22px; letter-spacing: -.02em; }}
    p        {{ color: #8a8070; font-size: 14px; line-height: 1.6; }}
    .code    {{
      font-size: 52px; font-weight: 700; letter-spacing: .18em;
      color: #E8A838; font-variant-numeric: tabular-nums;
      background: #1a1815; border: 1px solid #2a2520;
      padding: 20px 36px; border-radius: 12px;
    }}
    .hint    {{ color: #6a6060; font-size: 13px; max-width: 340px; }}
    .waiting {{ color: #6a6060; font-size: 24px; }}
    .logs-link {{ color: #4a4540; font-size: 12px; text-decoration: none; margin-top: 8px; }}
    .logs-link:hover {{ color: #8a8070; }}
    #status  {{ font-size: 13px; color: #4a4540; }}
  </style>
</head>
<body>
  <h1>Vecino — Vincular WhatsApp</h1>
  {code_html}
  <p id="status">{status_init}</p>
  <a class="logs-link" href="/pair/logs">ver logs →</a>
  <script>
    const statusEl = document.getElementById('status');
    // Poll /pair/status every 5 s; celebrate when paired
    const pollPaired = setInterval(async () => {{
      try {{
        const r = await fetch('/pair/status');
        const d = await r.json();
        if (d.paired) {{
          clearInterval(pollPaired);
          if (typeof pollCode !== 'undefined') clearInterval(pollCode);
          statusEl.textContent = '✅ ¡Conectado! Puedes cerrar esta página.';
          document.querySelector('h1').textContent = 'Vecino — ¡Conectado! 🙌';
        }}
      }} catch (_) {{}}
    }}, 5000);
    // While waiting for a code, reload the page every 5 s
    const hasCode = {has_code};
    const pollCode = hasCode ? null : setInterval(() => location.reload(), 5000);
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/pair/logs")
async def pair_logs():
    """Return raw hermes pairing output for debugging."""
    if not _PAIR_LOG.exists():
        return {"log": "", "note": "No output yet — hermes pairing thread may still be running."}
    content = _PAIR_LOG.read_text(encoding="utf-8", errors="replace")
    return {"log": content}


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
