"""
Vecino — background scheduler.
Sends automatic WhatsApp summaries to the business owner.

Scheduled jobs:
  - Daily 9pm (Bogotá): cash / sales summary
  - Monday 8am (Bogotá): weekly P&L summary

APScheduler runs in a background thread. All DB calls go through memory.py (sync).
Claude is used to turn raw data into natural Spanish prose.
"""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime

import anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

import memory
import twilio_client

load_dotenv()

_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
OWNER_PHONE = os.environ.get("OWNER_PHONE", os.environ.get("TWILIO_WHATSAPP_TO", ""))

SUMMARY_SYSTEM = """\
Eres Vecino, un asistente de negocios amigable para pequeños comerciantes.
Redacta resúmenes en español casual y cálido — como un vecino de confianza, no como un sistema.
Sé breve (máx. 5 líneas). Usa emojis con naturalidad, no en exceso.
No uses markdown. Solo texto plano.\
"""


# ── Summary builders ────────────────────────────────────────────────────────

def build_daily_summary() -> str:
    sales = memory.get_sales_since(hours=24)
    low   = memory.get_low_stock(threshold=10)

    if not sales:
        data_text = "No se registraron ventas en las últimas 24 horas."
    else:
        total_txns = len(sales)
        total_amount = sum(s["amount"] for s in sales if s["amount"])
        counter = Counter(s["product"] for s in sales)
        top_product, top_count = counter.most_common(1)[0]

        parts = [f"{total_txns} transacciones de venta registradas hoy."]
        if total_amount:
            parts.append(f"Total en caja: {total_amount:,.0f}.")
        parts.append(f"Lo más vendido: {top_product} ({top_count} veces).")
        data_text = " ".join(parts)

    if low:
        alerts = ", ".join(f"{i['product']} ({i['quantity']} {i['unit']})" for i in low)
        data_text += f" Stock bajo: {alerts}."

    response = _claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=SUMMARY_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Genera el resumen de cierre del día para el dueño del negocio.\n\n"
                    f"Datos del día:\n{data_text}"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def build_weekly_summary() -> str:
    sales = memory.get_sales_since(hours=168)  # 7 days

    if not sales:
        data_text = "Sin ventas registradas esta semana."
    else:
        total_txns = len(sales)
        total_amount = sum(s["amount"] for s in sales if s["amount"])
        counter = Counter(s["product"] for s in sales)
        top_3 = counter.most_common(3)

        parts = [f"Semana con {total_txns} transacciones."]
        if total_amount:
            parts.append(f"Total acumulado: {total_amount:,.0f}.")
        if top_3:
            top_str = ", ".join(f"{p} ({c})" for p, c in top_3)
            parts.append(f"Más vendidos: {top_str}.")
        data_text = " ".join(parts)

    response = _claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=SUMMARY_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Genera el resumen semanal de P&L para el dueño del negocio.\n\n"
                    f"Datos de la semana:\n{data_text}"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


# ── Scheduled senders ───────────────────────────────────────────────────────

def send_daily_summary() -> None:
    if not OWNER_PHONE:
        return
    try:
        text = build_daily_summary()
        twilio_client.send_message(OWNER_PHONE, text)
        memory.log_step("scheduler:daily_summary", "scheduled_job", text, "done")
    except Exception as exc:
        memory.log_step("scheduler:daily_summary", "scheduled_job", str(exc), "error")


def send_weekly_summary() -> None:
    if not OWNER_PHONE:
        return
    try:
        text = build_weekly_summary()
        twilio_client.send_message(OWNER_PHONE, text)
        memory.log_step("scheduler:weekly_summary", "scheduled_job", text, "done")
    except Exception as exc:
        memory.log_step("scheduler:weekly_summary", "scheduled_job", str(exc), "error")


# ── Scheduler factory ───────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="America/Bogota")

    # Daily 9pm — sales summary
    sched.add_job(
        send_daily_summary,
        "cron",
        hour=21,
        minute=0,
        id="daily_summary",
        replace_existing=True,
    )

    # Monday 8am — weekly P&L
    sched.add_job(
        send_weekly_summary,
        "cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly_summary",
        replace_existing=True,
    )

    return sched
