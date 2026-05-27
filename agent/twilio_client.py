"""
Vecino — Twilio WhatsApp wrapper.
Sends outbound messages via the Twilio API.

Credentials are read lazily so the module can be imported without
TWILIO_* environment variables being set (e.g. during boot on Railway
before secrets are injected, or in test environments).
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

_client: Client | None = None
_whatsapp_from: str = ""


def _get_twilio() -> tuple[Client, str]:
    """Lazily initialise and return the Twilio client + sender number."""
    global _client, _whatsapp_from
    if _client is None:
        sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if not sid or not token:
            raise RuntimeError(
                "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set to send WhatsApp messages"
            )
        _client = Client(sid, token)
        _whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
        if not _whatsapp_from:
            logging.warning("TWILIO_WHATSAPP_FROM is not set — outbound messages will fail")
    return _client, _whatsapp_from


def send_message(to: str, body: str) -> str:
    """Send a WhatsApp message. Returns the Twilio message SID."""
    client, from_ = _get_twilio()
    msg = client.messages.create(from_=from_, to=to, body=body)
    return msg.sid
