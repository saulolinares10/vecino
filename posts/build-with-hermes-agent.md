---
title: I was born in El Cafetal, Caracas. This is the kiosko on my corner. I built it an AI agent.
published: false
tags: hermesagentchallenge, devchallenge, agents
cover_image: [photo of Kiosco Wuilander, El Cafetal, Caracas]
---

*This is a submission for the [Hermes Agent Challenge](https://dev.to/challenges/hermes-agent-2026-05-15): Build With Hermes Agent*

---

## What I Built

There is a kiosko on Avenida El Limón in El Cafetal, Caracas called Wuilander. I walked past it hundreds of times growing up. It has 134,000 Instagram followers — more than most startups — because it became a symbol of something: a Venezuelan small business that survived everything and kept going.

El Cafetal is where I was born. It's a middle-class neighborhood in eastern Caracas that lived through what Venezuela lived through — hyperinflation that peaked at 130,000% in a single year, rolling blackouts, four currency conversions in a decade, 7 million people leaving the country including, eventually, me.

The businesses that stayed open did so on memory, on trust, and on WhatsApp. Not on software. Not on systems. There was no Shopify for this. No QuickBooks. No Stripe. The tools that exist assume things that aren't true in the informal Latin American economy: a credit card, a stable email address, reliable electricity, English literacy, time to learn something new.

I'm a data engineer now, working in PE consulting in Colombia, building on Claude's API in my spare time. I've shipped FinMentor (a financial advisor app) and BODEGA AI (a WhatsApp inventory agent). But I kept thinking about Wuilander. About what it would look like if the default design assumption for an AI tool was a WhatsApp number instead of an email address.

So I built **Vecino**.

Vecino is a Hermes Agent-powered WhatsApp business assistant for Latin American small businesses. No app to download. No dashboard to learn. No onboarding. You talk to it the way you already talk to everyone — on WhatsApp, in Spanish, in the informal register of someone who grew up in El Cafetal.

You tell it what arrived:
> *"llegaron 48 bolsas de café"*

You ask what you have:
> *"cuánto tengo de arroz"*

You log a sale:
> *"vendí 5 aceites"*

Every night at 9pm, without being asked, it sends you a summary of the day. Every Monday at 8am, the week's P&L. After 30 days, it knows your business patterns better than the notebook did.

It's named Vecino — the neighbor — because that's what it is. The one who knows your business, shows up every day, never forgets.

---

## Demo

The demo below shows Vecino in action: a pixel-perfect WhatsApp simulation on the left, and the Hermes Agent execution layer on the right — showing in real time how each message flows through the agent: intent parsing, memory reads and writes, skill loading, event hooks firing, and the scheduled 9pm summary arriving automatically.

🎥 [Video walkthrough — watch the conversation play out and the Hermes execution trace update in real time]

🔗 [Interactive demo](./demo.html)

[github.com/saulolinares10/vecino](https://github.com/saulolinares10/vecino)

Three moments worth watching:

- **"llegaron 48 bolsas de café"** → watch `MEMORY` write and `SKILL` load appear in the execution trace within the same second
- **"vendí 5 aceites"** → watch `EVENT HOOKS` fire `low_stock_alert` automatically — the owner never asked for the warning
- **9:00 PM** → `CRON` job triggers, `SUBAGENT` spawns to format the summary, the message arrives without any user input

---

## Code

[github.com/saulolinares10/vecino](https://github.com/saulolinares10/vecino)

### SOUL.md — the agent's personality file

```markdown
# Vecino — Identidad del Agente

Eres Vecino. Un asistente de negocios para abastos y tiendas pequeñas
en América Latina. Vives en WhatsApp.

## Personalidad
- Cálido, directo, como un vecino de confianza — no un sistema
- Nunca dices "procesando su solicitud" ni "entendido, procederé"
- Dices "listo", "anotado", "ojo con esto", "que descanses"
- Usas emojis con moderación: ☕ 🌾 ⚠️ 🌙 🙌
- Respondes corto — esto es WhatsApp, no un correo
- Cuando el inventario está bajo, lo mencionas sin que te pregunten

## Idioma
Siempre en español. Registro informal venezolano/latinoamericano.

## Lo que sabes hacer
- Registrar entradas de inventario ("llegaron 50 kg de harina")
- Consultar stock ("cuánto tengo de arroz")
- Anotar ventas ("vendí 3 aceites")
- Avisar cuando algo está bajando
- Dar el resumen del día cada noche a las 9pm
- Dar el resumen semanal los lunes a las 8am

## Lo que no haces
- No pides aclaración cuando la intención es clara
- No das respuestas largas
- No usas markdown en WhatsApp
```

Hermes loads SOUL.md as a context file automatically — it shapes every response the agent generates. This is how you give an AI agent a personality that fits a specific cultural context without fine-tuning a model. The line *"Nunca dices 'procesando su solicitud'"* is doing real work: it's the difference between a chatbot and a neighbor.

---

### Intent parsing in Spanish — `agent/nlp.py`

```python
INTENT_SYSTEM = """\
Eres el cerebro de Vecino, un agente de inteligencia de negocios para pequeños comerciantes latinoamericanos.
Tu trabajo es analizar mensajes de WhatsApp en español e identificar la intención del negociante y las entidades relevantes.

Responde SIEMPRE con JSON válido. Sin explicaciones. Sin texto extra. Solo el JSON.

Intenciones y sus entidades:

STOCK_IN — ingreso de mercancía al inventario
  Ejemplos: "llegaron 50 cajas de harina", "entró un bulto de arroz", "recibí 200 unidades de aceite"
  Entidades: {"product": str, "quantity": float, "unit": str}

SALE_LOG — registro de venta
  Ejemplos: "vendí 5 bolsas de café", "salieron 12 unidades de refresco hoy", "despachué 3 kg de queso"
  Entidades: {"product": str, "quantity": float, "unit": str, "amount": float|null}

SUMMARY_REQUEST — solicitud de resumen del día o semana
  Ejemplos: "resumen del día", "cómo voy hoy", "qué vendí esta semana", "dame el cierre"
  Entidades: {}

UNKNOWN — no se puede determinar la intención
  Entidades: {}

Reglas:
- Normaliza los productos a minúsculas y singular (ej: "Harinas" → "harina")
- Convierte cantidades a número flotante
- Si no se especifica unidad, usa "unidades"
"""


def parse_intent(message: str) -> dict:
    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=INTENT_SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
        raw = response.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if m:
            return json.loads(m.group(1))
        return {"intent": "UNKNOWN", "entities": {}}
    except Exception:
        return {"intent": "UNKNOWN", "entities": {}}
```

Claude is not optional here. "llegaron", "me trajeron", "recibí", "entró mercancía" all mean the same thing — goods arrived — and a Venezuelan shopkeeper will use all four in the same week. Keyword matching cannot handle this. A regex cannot handle this. Generic NLP models handle it poorly because informal Latin American Spanish, particularly Venezuelan Spanish, has a specific register that isn't well-represented in most training data. Claude parses intent reliably across all of them because it understands context, not just surface patterns. The prompt is written in Spanish, not English translated into Spanish — that distinction matters.

---

### Event hook for low-stock alerts — `agent/hooks/low_stock_alert.py`

```python
LOW_STOCK_THRESHOLD = float(os.environ.get("LOW_STOCK_THRESHOLD", 10))
OWNER_PHONE = os.environ.get("OWNER_PHONE", "")


def register(agent) -> None:
    """Register inventory-write hooks onto the given HermesAgent."""

    @agent.on("after:add_inventory")
    def after_add(tool: str, input: dict, result: dict, **kwargs):
        _check_and_alert(result.get("product", input.get("product", "")))

    @agent.on("after:log_sale")
    def after_sale(tool: str, input: dict, result: dict, **kwargs):
        _check_and_alert(result.get("product", input.get("product", "")))


def _check_and_alert(updated_product: str) -> None:
    if not OWNER_PHONE:
        return

    low_items = memory.get_low_stock(LOW_STOCK_THRESHOLD)
    if not low_items:
        _already_alerted.clear()
        return

    new_alerts = [i for i in low_items if i["product"] not in _already_alerted]
    if not new_alerts:
        return

    alert_text = _format_alert(new_alerts)
    twilio_client.send_message(OWNER_PHONE, alert_text)

    for item in new_alerts:
        _already_alerted.add(item["product"])
```

Hermes has two kinds of hooks: gateway hooks that fire at message receipt and send, and plugin hooks that intercept tool calls. `after:log_sale` is a plugin hook — it fires every time the `log_sale` tool completes, regardless of which conversation triggered it. The hook checks the threshold, formats an alert using a child Claude call, and sends a WhatsApp message proactively.

The owner never asked for this warning. They just said "vendí 5 aceites." The agent watched, noticed the remaining stock crossed the threshold, and acted. That is the difference between a tool that waits and an agent that watches.

---

### Scheduled tasks — `cron.yaml`

```yaml
jobs:
  - name: vecino-daily-summary
    schedule: "0 21 * * *"
    skill: vecino-summary
    task: "Genera el resumen del día en español y envíalo por WhatsApp"
    deliver_to: whatsapp

  - name: vecino-weekly-pl
    schedule: "0 8 * * 1"
    skill: vecino-summary
    task: "Genera el resumen semanal con P&L en español y envíalo por WhatsApp"
    deliver_to: whatsapp
```

Two jobs. Daily summary at 9pm. Weekly P&L every Monday at 8am. Both use the `vecino-summary` skill and delegate formatting to a child subagent — keeping the main agent responsive to incoming messages while the summary is being generated.

One constraint worth noting: Hermes does not allow scheduled tasks to spawn new scheduled tasks. A cron job can spawn a subagent. That subagent cannot register a new cron job. This is a deliberate safety constraint — automation that can replicate its own scheduling is automation you can't trust. The constraint is documented, not an oversight.

---

### My Tech Stack

| Component | What it does |
|---|---|
| **Hermes Agent v0.14.0** | Messaging gateway, persistent memory, skill system, scheduled tasks, event hooks, subagent delegation |
| **Claude API** (claude-sonnet-4-6) | Intent parsing in Spanish, response generation, summary formatting |
| **FastAPI + Python 3.11** | Operator dashboard API |
| **SQLite** | Local inventory and sales persistence |
| **React + Vite** | Operator dashboard frontend |
| **Railway** | Deployment — vecino-production-b60f.up.railway.app |

---

## How I Used Hermes Agent

### 1. Messaging Gateway — WhatsApp as first-class interface

Hermes treats WhatsApp as a native platform, not a webhook integration. The agent lives in the conversation. Sessions persist across messages. The owner doesn't re-explain their inventory every time — Hermes maintains conversational state natively.

Why this matters for Vecino specifically: Wuilander's owner isn't going to install an app. They're not going to visit a dashboard. They're going to send a WhatsApp message the same way they send one to their daughter. Without a gateway that handles session persistence natively, every message exchange would require the developer to reconstruct context from scratch. Hermes does this without any custom infrastructure. The conversation just works.

### 2. Persistent Memory + FTS5 Cross-Session Recall

Hermes's memory system persists across sessions using MEMORY.md and a full-text search index. When the owner asks "cuánto tengo de arroz" three weeks after last updating their rice inventory, Vecino finds it — not because of a database query the developer wrote, but because Hermes's FTS5 recall searches across all prior sessions automatically.

Why this matters: a neighbor remembers. That's the entire premise. A stateless API call can be impressive in a demo and useless after day three. The persistent memory is what makes Vecino useful after day one instead of just impressive during a demonstration. The owner stops explaining themselves. The agent already knows.

### 3. Skill System + Self-Improvement Loop

Every 15 interactions, Hermes pauses, examines what it learned, and writes or rewrites a skill file. After 30 days of Vecino running for a specific business, the skill file for that business contains patterns the developer never wrote: peak hours, top products, restock frequency, seasonal patterns.

The skill file for Wuilander after 30 days might contain: "Fridays: high rotation on harina de maíz. Restock Tuesdays. Coffee margin highest. Owner messages peak 11am–1pm."

No developer wrote that. The agent learned it. The skill file becomes a compressed representation of one specific business's operating reality — and every response the agent gives from that point forward is informed by it.

### 4. Scheduled Tasks + Subagent Delegation

The 9pm daily summary and Monday P&L are native Hermes cron jobs. They run without the owner asking. They delegate formatting to a child subagent — keeping the main agent responsive to incoming messages during the formatting step.

This is the moment in the demo that makes people understand what an agent actually is. The owner didn't ask. The message arrived. That's not a feature. That's a different relationship between software and the people it serves.

---

Venezuela has 7.7 million people living outside the country. That's one of the largest displacement crises in the Western Hemisphere. Most of us have someone back home — a parent, a cousin, a neighbor — running a small business, keeping a family fed, doing the math in their head because no system ever bothered to reach them.

Vecino is one attempt to close that gap. One abasto. One WhatsApp number. One neighbor who never forgets.

The repo is open. The architecture works for any informal economy — in any language, in any country where WhatsApp is infrastructure and enterprise software is a foreign concept.

If you want to build this in your country — for your community, in your language — come find me. You are welcome here.

*Saulo Linares · Born in El Cafetal, Caracas · Building in Bogotá, Colombia*
*[LinkedIn](https://www.linkedin.com/in/saulolinares/) · [GitHub](https://github.com/saulolinares10)*
