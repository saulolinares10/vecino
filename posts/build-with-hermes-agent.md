---
title: My neighbor in El Cafetal never had a system. I built him one.
published: false
tags: hermesagentchallenge, devchallenge, agents
---

*This is a submission for the [Hermes Agent Challenge](https://dev.to/challenges/hermes-agent-2026-05-15): Build With Hermes Agent*

## What I Built

Don Ramón runs an abasto on Calle Los Samanes in El Cafetal, east Caracas. He has run it since 1987. He survived the Caracazo, four currency conversions, hyperinflation that peaked at 130,000%, and two years of rolling blackouts. His inventory system for thirty-five years was a worn notebook and his own memory. When his daughter left for Colombia in 2019 — like 7 million other Venezuelans — she took the notebook habit with her. Now it's just the memory. He's 67.

I'm Venezuelan. I've been based in Colombia for the past few years, working as a data lead at a PE firm, building on Claude's API in my own time. FinMentor. BODEGA AI. I know what software looks like when it's built for people who already have everything. And I know what it looks like when it never reaches the people who actually need it.

Every small business inventory solution on the market assumes the same stack: a smartphone with storage, a credit card, an email address, reliable enough internet to download an app, and enough English to get through the setup flow. Don Ramón has a phone. He has WhatsApp. His daughter tops up his data from Medellín. That's the whole stack.

Vecino is built for exactly that.

It's a Hermes Agent-powered business intelligence assistant that lives entirely inside WhatsApp. No app to download. No dashboard to log into. No onboarding. No English. Just WhatsApp — the actual operating system of the informal Latin American economy.

You tell it what arrived: *"llegaron 50 kg de harina"*
You ask what you have: *"cuánto tengo de arroz"*
You log a sale: *"vendí 3 aceites"*
Every night at 9pm it sends a summary of the day.
Every Monday it sends the week's P&L.
After 30 days it knows the business's patterns better than the notebook did.

---

## Demo

**Screenshot 1 — Inventory update via WhatsApp**

![WhatsApp chat screenshot showing Don Ramón typing "llegaron 48 bolsas de café" and Vecino responding: "Listo, anoté 48 bolsas de café ☕ Ahora tienes 61 bolsas en total. Ese café se mueve rápido — la semana pasada entraron 30 y ya se acabaron." The response is in the chat bubble style of a message from a contact named "Vecino 🏪", warm and conversational, not a system notification.](./screenshots/01-stock-update.png)

That response is not templated. The tail — *"ese café se mueve rápido"* — is the Hermes skill memory reading four weeks of stock-in history for this specific business and surfacing a pattern the developer never wrote a rule for.

---

**Screenshot 2 — The 9pm daily summary**

![WhatsApp message from Vecino at 21:00 reading: "Buenas noches 🌙 Así quedó el día: 34 transacciones. Lo más vendido fue harina de maíz (12 unidades). Ojo con el aceite — solo quedan 6 unidades. Mañana sería bueno llamar a Polar. Hasta mañana, Don Ramón." The message arrives as a single block of plain text, no markdown, formatted for mobile reading. The timestamp shows 9:00 PM.](./screenshots/02-daily-summary.png)

No markdown. No bullet points. Plain text, warm tone. Because WhatsApp is not a dashboard and Don Ramón is not a product manager. *"Hasta mañana, Don Ramón."* That last line is not hardcoded. It arrives because the agent knows the owner's name from the phone number registration.

---

**Screenshot 3 — Agent execution log in the operator dashboard**

![The Vecino operator dashboard showing the agent execution log section — a dark terminal panel with IBM Plex Mono font. Five rows visible: 001 — 14:23:08 — webhook:receive — green dot — From: whatsapp:+573227306058. 002 — 14:23:09 — nlp:STOCK_QUERY — green dot — product: arroz. 003 — 14:23:09 — memory:read — green dot — get_inventory(arroz). 004 — 14:23:10 — format:response — green dot — "Tienes 23 kg de arroz". 005 — 14:23:10 — webhook:reply — green dot — STOCK_QUERY. The panel has a warm amber color scheme with a dark #0f0e0d background.](./screenshots/03-agent-log.png)

The operator dashboard exists for the daughter in Medellín. She can open a browser, see the inventory grid, check today's sales, and know the business is running — without calling. The dashboard is in Spanish, the low-stock alerts have amber borders, and the design looks like something you'd build for your father on a weekend: functional, warm, no unnecessary complexity.

---

## Code

**GitHub:** [github.com/saulolinares10/vecino](https://github.com/saulolinares10/vecino)

---

### My Tech Stack

- **Hermes Agent** — memory, scheduler, messaging gateway
- **Claude API** / `claude-sonnet-4-6` — intent parsing in Spanish
- **FastAPI** + Python — backend API layer
- **Twilio WhatsApp API** — message routing
- **SQLite** + SQLAlchemy — local persistence
- **APScheduler** — cron jobs for daily and weekly summaries
- **React + Vite** — operator dashboard

---

### Snippet 1 — The intent parser

```python
INTENT_SYSTEM = """\
Eres el cerebro de Vecino, un agente de inteligencia de negocios
para pequeños comerciantes latinoamericanos.

Responde SIEMPRE con JSON válido. Sin explicaciones. Solo el JSON.

Intenciones y sus entidades:

STOCK_IN — ingreso de mercancía
  "llegaron 50 cajas de harina" / "recibí 200 unidades" / "me trajeron un bulto"
  entities: {product, quantity, unit}

SALE_LOG — registro de venta
  "vendí 5 bolsas de café" / "salieron 12 refrescos" / "despachéé 3 kg de queso"
  entities: {product, quantity, unit, amount}
...
"""
```

Why Claude and not regex? Because the same action — adding stock — arrives in forty different forms. *"Llegaron"* (they arrived). *"Recibí"* (I received). *"Me trajeron"* (they brought me). *"Entró un bulto de"* (a bundle of came in). *"Acaba de llegar"* (just arrived). Informal Venezuelan Spanish has enormous surface area for a single intent. A regex that catches *"llegaron"* misses *"me cayó"*. Claude catches all of them because it understands the sentence, not the pattern.

This isn't a nice-to-have. It's the product. If the agent can't parse how Don Ramón actually talks, Don Ramón won't use it. There's no onboarding that teaches someone how to phrase inventory updates into a format a machine can accept.

---

### Snippet 2 — The Hermes skill write

```python
async def _write_weekly_skill(business_id: str, summary: dict) -> None:
    record = {
        "business_id": business_id,
        "week": datetime.utcnow().strftime("%Y-W%U"),
        "top_products": summary["top_3"],
        "peak_day": summary["peak_day"],
        "restock_pattern": summary["restock_gaps"],
        "total_transactions": summary["total_txns"],
    }
    await hermes.memory.write(
        key=f"weekly_skill:{business_id}:{record['week']}",
        value=record,
        tags=["business_pattern", business_id, record["week"]],
    )
```

After 30 days, this business has 4 weekly skill records. When the agent generates the next daily summary, the retrieve step pulls those records first and looks for patterns: which products restock most often, which days are busiest, which inventory gaps tend to recur. The summary stops being a report of what happened and starts being a prediction of what needs to happen next.

*"Es viernes — suele entrar más harina los viernes."* That line in a response is not a rule the developer wrote. It's the agent reading four weeks of skill records and noticing that harina consistently arrives on Fridays for this business. A stateless API call gives you the same generic response every time. The Hermes memory loop gives you a response that knows this specific business.

---

### Snippet 3 — The 9pm scheduler

```yaml
schedule:
  - name: daily-summary
    cron: "0 21 * * *"
    timezone: "America/Caracas"
    task: send_daily_summary
    params:
      owner_phone: "${OWNER_PHONE}"
      language: es
```

The daily summary runs at 9pm Venezuela time without the owner asking for it. That's the difference between a tool and an assistant. Tools wait. Assistants show up.

One design constraint I noticed and appreciated: Hermes enforces that a scheduled task cannot spawn new scheduled tasks. My first instinct was to work around this — I had an idea for a low-stock alert that would schedule a follow-up restock reminder if the owner didn't respond within 48 hours. The constraint blocked it. But the constraint is correct. Automation that can create new automation is automation you can no longer reason about. I built the follow-up as a manual trigger instead, and it's better for it.

---

## How I Used Hermes Agent

### 1. Persistent memory across sessions

**What:** The agent maintains inventory state, sales history, and business patterns across every conversation without being told anything twice.

**Why:** A neighbor remembers. That's the whole product. Don Ramón doesn't want to re-tell the agent that he sells harina de maíz every time he opens WhatsApp. A stateless API call requires the user to carry the state themselves. The Hermes memory loop carries it for them.

**Code:**
```python
async def _get_inventory_context(product: str) -> dict | None:
    records = await hermes.memory.search(
        tags=["inventory", product],
        limit=1,
        order="recency",
    )
    return records[0]["value"] if records else None
```

### 2. Messaging gateway

**What:** WhatsApp is a first-class Hermes integration. The agent doesn't bolt onto the Twilio webhook as an afterthought — it lives in the conversation natively.

**Why:** The choice of delivery channel is not incidental. Every Latin American with a phone has WhatsApp. Fewer than 20% of small Venezuelan businesses have a formal email address. Any system that requires email for setup has already excluded the user this product is for. Hermes's messaging gateway is how the agent reaches Don Ramón where he already is, not where we'd like him to be.

### 3. Scheduler

**What:** The 9pm daily summary and Monday 8am P&L run on schedule, without a request. The owner never has to remember to ask.

**Why:** Most "smart" business tools shift cognitive load from the machine to the human. You have to remember to open the app, to run the report, to check the dashboard. The Hermes scheduler inverts that: the system takes on the obligation of showing up. For a 67-year-old running a shop alone, that inversion is the product.

**Code:**
```python
sched.add_job(
    send_daily_summary,
    "cron",
    hour=21,
    minute=0,
    timezone="America/Caracas",
    id="daily_summary",
)
```

### 4. Skill accumulation

**What:** After enough sessions, Vecino starts anticipating the business rather than just recording it. It surfaces patterns the owner already knows but has never seen made explicit — peak days, restock rhythms, which products move together.

**Why:** The abasto notebook was not just a ledger. It was a compressed record of thirty-five years of business intelligence, legible only to the person who wrote it. Vecino doesn't replace that — nothing does. But it makes the patterns accessible to someone who wasn't there. To the daughter in Medellín who wants to understand how the business is doing without having to call every day and ask. The skill loop is what makes Vecino useful across distance.

---

Venezuela has 7 million people living outside the country. Most of them have someone back home running a small business, keeping a family fed, doing the math in their head because no system ever reached them. Vecino is one attempt to change that — one abasto, one WhatsApp number at a time.

If you want to build this in your country — in your language, for your informal economy — the repo is open. Come find me. You're welcome here.
