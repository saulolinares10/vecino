# Vecino

Tu negocio, en tu idioma.

A WhatsApp-first business intelligence agent for Latin American small businesses. No app. No onboarding. No English. Just WhatsApp — the operating system of the informal economy.

---

## What it does

You run the business. Vecino keeps track.

Send a message the way you'd say it out loud:

```
"llegaron 50 kg de harina"       → updates inventory
"vendí 3 aceites"                 → logs the sale
"cuánto tengo de arroz"           → checks stock
"pedí 100 unidades a Polar"       → logs the supplier order
"resumen del día"                 → generates a summary on demand
```

Every night at 9pm it sends a summary of the day.
Every Monday at 8am it sends the week's numbers.
After 30 days it knows the business's patterns better than the notebook did.

---

## Architecture

```
WhatsApp (Twilio)
      │
      ▼
FastAPI /webhook
      │
      ├── nlp.py         Claude parses informal Spanish → structured intent
      ├── memory.py      SQLite: inventory, sales, orders, agent steps
      ├── scheduler.py   APScheduler: 9pm daily + Monday weekly
      └── twilio_client  Sends replies back to WhatsApp

React dashboard (optional)
      └── Operator view for remote monitoring — inventory grid,
          sales timeline, agent log, supplier orders
```

---

## Setup

### Backend

```bash
cd agent
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your credentials
uvicorn main:app --reload --port 8000
```

Point your Twilio WhatsApp sandbox webhook at:
```
https://<your-ngrok-url>/webhook
```

### Dashboard (optional)

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. Points to the backend at `http://localhost:8000` by default — override with `VITE_API_URL`.

---

## Environment variables

```
ANTHROPIC_API_KEY=          # Claude API key
TWILIO_ACCOUNT_SID=         # Twilio account SID
TWILIO_AUTH_TOKEN=          # Twilio auth token
TWILIO_WHATSAPP_FROM=       # Your Twilio WhatsApp number (whatsapp:+14155238886)
TWILIO_WHATSAPP_TO=         # Owner's WhatsApp number (whatsapp:+573227306058)
OWNER_PHONE=                # Same as above — used by the scheduler
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhook` | Receives Twilio WhatsApp messages |
| `POST` | `/api/summary` | Generate daily summary on demand |
| `GET` | `/api/inventory` | Current inventory as JSON |
| `GET` | `/api/sales` | Sales from last 24 hours |
| `GET` | `/api/orders` | All logged supplier orders |
| `GET` | `/api/steps` | Agent execution log |

---

## Stack

- **Claude** `claude-sonnet-4-6` — intent parsing in Spanish (informal speech, all variants)
- **FastAPI** — API layer and webhook receiver
- **Twilio** — WhatsApp delivery
- **SQLite** + SQLAlchemy — local persistence
- **APScheduler** — daily and weekly scheduled messages
- **React** + Vite — operator dashboard

---

## Why WhatsApp

Every small business inventory tool assumes a smartphone with storage, a credit card, an email address, reliable power, and enough English to set up an account.

Don Ramón has a phone. He has WhatsApp. His daughter tops up his data from Medellín.

Vecino is built for exactly that.

---

## Posts

- [build-with-hermes-agent.md](posts/build-with-hermes-agent.md) — dev.to submission: how Vecino was built
- [write-about-hermes-agent.md](posts/write-about-hermes-agent.md) — dev.to submission: why informal economy AI matters

---

## License

MIT
