"""
Vecino — Twilio WhatsApp wrapper.
Sends outbound messages via the Twilio API.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"],
)

WHATSAPP_FROM = os.environ["TWILIO_WHATSAPP_FROM"]


def send_message(to: str, body: str) -> str:
    """Send a WhatsApp message. Returns the Twilio message SID."""
    msg = _client.messages.create(
        from_=WHATSAPP_FROM,
        to=to,
        body=body,
    )
    return msg.sid
