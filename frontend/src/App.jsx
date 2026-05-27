import { useState, useEffect, useCallback, useRef } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const LOW_STOCK = 10
const OWNER_PHONE = '+57 322 730 6058'

const EXAMPLES = [
  'llegaron 50 kg de harina',
  'vendí 3 aceites hoy',
  'cuánto tengo de arroz',
  'pedí 100 unidades a Polar',
  'resumen del día',
  'cómo voy esta semana',
]

const DAY_ES = {
  Monday: 'Lunes', Tuesday: 'Martes', Wednesday: 'Miércoles',
  Thursday: 'Jueves', Friday: 'Viernes', Saturday: 'Sábado', Sunday: 'Domingo',
}

// ── Time helpers ───────────────────────────────────────────────────────────

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
}

function fmtClock(iso) {
  const d = new Date(iso)
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map(n => String(n).padStart(2, '0'))
    .join(':')
}

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  const h = Math.floor(m / 60)
  const d = Math.floor(h / 24)
  if (m < 1) return 'ahora'
  if (m < 60) return `hace ${m}m`
  if (h < 24) return `hace ${h}h`
  return `hace ${d}d`
}

function nowClock() {
  return new Date().toLocaleTimeString('es-CO', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

// ── Data fetching ──────────────────────────────────────────────────────────

async function apiFetch(path) {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Pattern helpers ────────────────────────────────────────────────────────

function confidenceLevel(atCount) {
  if (atCount >= 60) return 3
  if (atCount >= 30) return 2
  return 1
}

function derivePatternCards(patterns) {
  if (!patterns.length) return []

  const latest = patterns[0]
  const conf = confidenceLevel(latest.at_count)
  const top = latest.top_products || []
  const cards = []

  if (top[0]) {
    cards.push({
      name: 'Producto más vendido',
      description: `${top[0].product} — ${top[0].count} ventas registradas`,
      confidence: conf,
    })
  }

  if (latest.peak_day) {
    const dayES = DAY_ES[latest.peak_day] || latest.peak_day
    cards.push({
      name: `${dayES}: día más activo`,
      description: 'Alta rotación de productos este día',
      confidence: conf,
    })
  }

  if (top[1]) {
    cards.push({
      name: 'Alto movimiento',
      description: `${top[1].product} — ${top[1].count} ventas`,
      confidence: conf,
    })
  }

  if (top[2]) {
    cards.push({
      name: 'Tercer más vendido',
      description: `${top[2].product} con ${top[2].count} ventas`,
      confidence: Math.max(1, conf - 1),
    })
  }

  // Pull distinct peak-day insights from older snapshots
  const seenDays = new Set([latest.peak_day])
  for (const p of patterns.slice(1)) {
    if (cards.length >= 6) break
    if (p.peak_day && !seenDays.has(p.peak_day)) {
      seenDays.add(p.peak_day)
      const dayES = DAY_ES[p.peak_day] || p.peak_day
      cards.push({
        name: `${dayES}: reabastecimiento frecuente`,
        description: 'Tendencia observada en períodos anteriores',
        confidence: 1,
      })
    }
  }

  return cards.slice(0, 6)
}

// ── Header ─────────────────────────────────────────────────────────────────

function Header({ lastRefresh }) {
  return (
    <header className="header">
      <div>
        <h1 className="header-wordmark">Vecino</h1>
        <p className="header-subtitle">tu negocio, en tu idioma</p>
      </div>
      <div className="header-meta">
        {lastRefresh && (
          <span className="header-refresh">actualizado {lastRefresh}</span>
        )}
        <span className="header-phone">📱 {OWNER_PHONE}</span>
      </div>
    </header>
  )
}

// ── Section 1: Inventario ──────────────────────────────────────────────────

function InventorySection({ items, loading, onRefresh }) {
  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Inventario Actual</h2>
        <button className="btn btn--ghost" onClick={onRefresh} disabled={loading}>
          {loading ? 'Cargando…' : '↻ Actualizar'}
        </button>
      </div>

      {loading ? (
        <div className="empty-state">Cargando inventario…</div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          Sin productos registrados.
          <br />
          Envía "llegaron 50 kg de harina" por WhatsApp para empezar.
        </div>
      ) : (
        <div className="inv-grid">
          {items.map(item => (
            <div
              key={item.product}
              className={`inv-card${item.quantity <= LOW_STOCK ? ' inv-card--low' : ''}`}
            >
              <div className="inv-product">{item.product}</div>
              <div className="inv-qty">{item.quantity}</div>
              <div className="inv-unit">{item.unit}</div>
              <div className="inv-updated">{timeAgo(item.last_updated)}</div>
              {item.quantity <= LOW_STOCK && (
                <div className="inv-alert">⚠ stock bajo</div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ── Section 2: Ventas ──────────────────────────────────────────────────────

function SalesSection({ sales }) {
  const totalAmount = sales.reduce((acc, s) => acc + (s.amount || 0), 0)
  const sorted = [...sales].sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp),
  )

  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Ventas de Hoy</h2>
        <span className="sales-total">
          <span className="sales-total-count">
            {sales.length} {sales.length === 1 ? 'venta' : 'ventas'}
          </span>
          {totalAmount > 0 && (
            <>
              {' · '}
              <span className="sales-total-amount">
                {totalAmount.toLocaleString('es-CO')}
              </span>
            </>
          )}
        </span>
      </div>

      {sales.length === 0 ? (
        <div className="empty-state">
          Sin ventas registradas hoy.
          <br />
          Envía "vendí 5 bolsas de café" para anotar.
        </div>
      ) : (
        <div className="sales-list">
          {sorted.map((sale, i) => (
            <div key={sale.id || i} className="sale-row">
              <span className="sale-time">{fmtTime(sale.timestamp)}</span>
              <span className="sale-dot" />
              <span className="sale-product">{sale.product}</span>
              <span className="sale-qty">
                × {sale.quantity} {sale.unit}
              </span>
              {sale.amount != null && (
                <span className="sale-amount">
                  {sale.amount.toLocaleString('es-CO')}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ── Section 3: Pedidos ─────────────────────────────────────────────────────

function OrdersSection({ orders }) {
  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Pedidos Pendientes</h2>
        <span className="section-meta">{orders.length} pedidos</span>
      </div>

      {orders.length === 0 ? (
        <div className="empty-state">
          Sin pedidos registrados.
          <br />
          Envía "pedí 100 kg a Polar, llegan el viernes" para anotar.
        </div>
      ) : (
        <div className="orders-list">
          {orders.map((order, i) => {
            const daysOld = Math.floor(
              (Date.now() - new Date(order.logged).getTime()) / 86_400_000,
            )
            const overdue = daysOld >= 7 && order.expected !== 'por confirmar'
            return (
              <div
                key={order.id || i}
                className={`order-row${overdue ? ' order-row--overdue' : ''}`}
              >
                <span className="order-supplier">{order.supplier}</span>
                <span className="order-product">
                  {order.quantity} {order.unit} de {order.product}
                </span>
                <span className="order-expected">llega: {order.expected}</span>
                <span className="order-logged">{timeAgo(order.logged)}</span>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

// ── Section 4: Patrones aprendidos ────────────────────────────────────────

function ConfidenceDots({ level }) {
  return (
    <div className="confidence-dots">
      {[1, 2, 3].map(n => (
        <span key={n} className={`confidence-dot${n <= level ? ' confidence-dot--on' : ''}`} />
      ))}
    </div>
  )
}

function PatternsSection({ patterns }) {
  const cards = derivePatternCards(patterns)

  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Lo que Vecino ha aprendido de tu negocio</h2>
        <span className="section-meta">
          {cards.length > 0 ? `${cards.length} patrones` : 'aprendiendo'}
        </span>
      </div>

      {cards.length === 0 ? (
        <div className="empty-state">
          Vecino aprende con el uso — los patrones aparecen después de unos días 📈
        </div>
      ) : (
        <div className="patterns-grid">
          {cards.map((card, i) => (
            <div key={i} className="pattern-card">
              <div className="pattern-header">
                <span className="pattern-name">{card.name}</span>
                <ConfidenceDots level={card.confidence} />
              </div>
              <p className="pattern-description">{card.description}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ── Section 5: Últimos mensajes ────────────────────────────────────────────

function MessagesSection({ messages }) {
  const feedRef = useRef(null)

  const sorted = [...messages]
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .slice(-8)

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages])

  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Conversación reciente</h2>
        <span className="section-meta">
          {sorted.length > 0 ? `${sorted.length} mensajes · cada 10s` : 'esperando…'}
        </span>
      </div>

      {sorted.length === 0 ? (
        <div className="empty-state">
          Sin mensajes todavía. Envía algo a Vecino por WhatsApp para empezar.
        </div>
      ) : (
        <div className="chat-feed" ref={feedRef}>
          {sorted.map((msg, i) => (
            <div
              key={msg.id || i}
              className={`bubble-row bubble-row--${msg.direction}`}
            >
              {msg.direction === 'outbound' && (
                <span className="bubble-sender">Vecino</span>
              )}
              <div className={`bubble bubble--${msg.direction}`}>
                <p className="bubble-text">{msg.body}</p>
                <span className="bubble-time">{fmtTime(msg.timestamp)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ── Section 6: Agent log ───────────────────────────────────────────────────

function StepsSection({ steps }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [steps])

  const sorted = [...steps].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
  )

  return (
    <section>
      <div className="section-header">
        <h2 className="section-title">Agente — Log de Ejecución</h2>
        <span className="section-meta">{steps.length} pasos · refresca cada 5s</span>
      </div>

      {steps.length === 0 ? (
        <div className="log-terminal log-empty">
          <span className="log-cursor">█</span>
          {' '}esperando mensajes de WhatsApp…
        </div>
      ) : (
        <div className="log-terminal">
          {sorted.map((step, i) => (
            <div key={step.id || i} className="log-entry">
              <span className="log-idx">{String(i + 1).padStart(3, '0')}</span>
              <span className="log-ts">{fmtClock(step.timestamp)}</span>
              <span className="log-action">{step.action}</span>
              <span className={`log-dot dot-${step.status ?? 'wait'}`} title={step.status} />
              <span className="log-msg">
                {(step.input_text || '').slice(0, 72)}
              </span>
            </div>
          ))}
          <div ref={bottomRef} />
          <div className="log-refresh-hint">↻ auto-refresh cada 5 segundos</div>
        </div>
      )}
    </section>
  )
}

// ── Quick reference ────────────────────────────────────────────────────────

function QuickReference() {
  return (
    <section className="quick-ref">
      <div className="section-header">
        <h2 className="section-title">Cómo hablarle a Vecino</h2>
        <span className="section-meta">vía WhatsApp</span>
      </div>
      <div className="examples-grid">
        {EXAMPLES.map((ex, i) => (
          <div key={i} className="example-card">
            <span className="example-wa-icon">💬</span>
            <span className="example-text">"{ex}"</span>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── App ────────────────────────────────────────────────────────────────────

export default function App() {
  const [inventory, setInventory]   = useState([])
  const [sales, setSales]           = useState([])
  const [orders, setOrders]         = useState([])
  const [patterns, setPatterns]     = useState([])
  const [messages, setMessages]     = useState([])
  const [steps, setSteps]           = useState([])
  const [loadingInv, setLoadingInv] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchInventory = useCallback(async () => {
    setLoadingInv(true)
    try {
      const data = await apiFetch('/api/inventory')
      setInventory(data.inventory || [])
    } catch (e) { console.error('inventory:', e) }
    finally { setLoadingInv(false) }
  }, [])

  const fetchSales = useCallback(async () => {
    try {
      const data = await apiFetch('/api/sales')
      setSales(data.sales || [])
    } catch (e) { console.error('sales:', e) }
  }, [])

  const fetchOrders = useCallback(async () => {
    try {
      const data = await apiFetch('/api/orders')
      setOrders(data.orders || [])
    } catch (e) { console.error('orders:', e) }
  }, [])

  const fetchPatterns = useCallback(async () => {
    try {
      const data = await apiFetch('/api/patterns')
      setPatterns(data.patterns || [])
    } catch (e) { console.error('patterns:', e) }
  }, [])

  const fetchMessages = useCallback(async () => {
    try {
      const data = await apiFetch('/api/messages')
      setMessages(data.messages || [])
    } catch (e) { console.error('messages:', e) }
  }, [])

  const fetchSteps = useCallback(async () => {
    try {
      const data = await apiFetch('/api/steps')
      setSteps(data.steps || [])
      setLastRefresh(nowClock())
    } catch (e) { console.error('steps:', e) }
  }, [])

  // Initial load — all at once
  useEffect(() => {
    fetchInventory()
    fetchSales()
    fetchOrders()
    fetchPatterns()
    fetchMessages()
    fetchSteps()
  }, [fetchInventory, fetchSales, fetchOrders, fetchPatterns, fetchMessages, fetchSteps])

  // Agent log: every 5 seconds
  useEffect(() => {
    const t = setInterval(fetchSteps, 5_000)
    return () => clearInterval(t)
  }, [fetchSteps])

  // WhatsApp feed: every 10 seconds
  useEffect(() => {
    const t = setInterval(fetchMessages, 10_000)
    return () => clearInterval(t)
  }, [fetchMessages])

  return (
    <div className="app">
      <Header lastRefresh={lastRefresh} />
      <div className="sections">
        <InventorySection
          items={inventory}
          loading={loadingInv}
          onRefresh={fetchInventory}
        />
        <SalesSection sales={sales} />
        <OrdersSection orders={orders} />
        <PatternsSection patterns={patterns} />
        <MessagesSection messages={messages} />
        <StepsSection steps={steps} />
        <QuickReference />
      </div>
    </div>
  )
}
