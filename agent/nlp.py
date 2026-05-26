"""
Vecino — intent parser.
Uses Claude to extract structured intent + entities from free-form Spanish WhatsApp messages.
All prompts in Spanish. Returns a plain dict every time — never raises on parse failure.
"""
from __future__ import annotations

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-6"

INTENT_SYSTEM = """\
Eres el cerebro de Vecino, un agente de inteligencia de negocios para pequeños comerciantes latinoamericanos.
Tu trabajo es analizar mensajes de WhatsApp en español e identificar la intención del negociante y las entidades relevantes.

Responde SIEMPRE con JSON válido. Sin explicaciones. Sin texto extra. Solo el JSON.

Formato de respuesta:
{
  "intent": "<INTENT>",
  "entities": { ... }
}

Intenciones y sus entidades:

STOCK_IN — ingreso de mercancía al inventario
  Ejemplos: "llegaron 50 cajas de harina", "entró un bulto de arroz", "recibí 200 unidades de aceite"
  Entidades: {"product": str, "quantity": float, "unit": str}

STOCK_QUERY — consulta de inventario
  Ejemplos: "cuánto tenemos de azúcar", "¿qué tengo de café?", "inventario de leche"
  Entidades: {"product": str}

SALE_LOG — registro de venta
  Ejemplos: "vendí 5 bolsas de café", "salieron 12 unidades de refresco hoy", "despachaé 3 kg de queso"
  Entidades: {"product": str, "quantity": float, "unit": str, "amount": float|null}
  Nota: "amount" es el valor total en dinero si el usuario lo menciona, si no es null.

ORDER_LOG — pedido a proveedor
  Ejemplos: "pedí 100 kg a Polar", "encargué 50 cajas de harina a La Favorita, llegan el viernes"
  Entidades: {"supplier": str, "product": str, "quantity": float, "unit": str, "expected_date": str}
  Nota: si no menciona fecha, usa "por confirmar".

SUMMARY_REQUEST — solicitud de resumen del día o semana
  Ejemplos: "resumen del día", "cómo voy hoy", "qué vendí esta semana", "dame el cierre"
  Entidades: {}

UNKNOWN — no se puede determinar la intención
  Entidades: {}

Reglas:
- Normaliza los productos a minúsculas y singular (ej: "Harinas" → "harina")
- Convierte cantidades a número flotante
- Si no se especifica unidad, usa "unidades"
- Si el mensaje es un saludo, pregunta general o no tiene relación con el negocio, usa UNKNOWN\
"""


def parse_intent(message: str) -> dict:
    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=INTENT_SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
        raw = response.content[0].text.strip()

        # Try direct JSON parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting from code block
        m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if m:
            return json.loads(m.group(1))

        return {"intent": "UNKNOWN", "entities": {}}
    except Exception:
        return {"intent": "UNKNOWN", "entities": {}}
