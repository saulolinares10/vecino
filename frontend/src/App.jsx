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

// ── Section 4: Agent log ───────────────────────────────────────────────────

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
  const [inventory, setInventory] = useState([])
  const [sales, setSales]         = useState([])
  const [orders, setOrders]       = useState([])
  const [steps, setSteps]         = useState([])
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
    fetchSteps()
  }, [fetchInventory, fetchSales, fetchOrders, fetchSteps])

  // Agent log auto-refreshes every 5 seconds
  useEffect(() => {
    const timer = setInterval(fetchSteps, 5_000)
    return () => clearInterval(timer)
  }, [fetchSteps])

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
        <StepsSection steps={steps} />
        <QuickReference />
      </div>
    </div>
  )
}
