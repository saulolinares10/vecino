"""
Vecino — persistent store (SQLite via SQLAlchemy).
All public functions return plain dicts so callers never touch ORM objects
after session close.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./vecino.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM models ─────────────────────────────────────────────────────────────

class InventoryItem(Base):
    __tablename__ = "inventory"
    product      = Column(String, primary_key=True, index=True)
    quantity     = Column(Float, default=0.0)
    unit         = Column(String, default="unidades")
    last_updated = Column(DateTime, default=datetime.utcnow)


class Sale(Base):
    __tablename__ = "sales"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    product   = Column(String, index=True)
    quantity  = Column(Float)
    unit      = Column(String, default="unidades")
    amount    = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    note      = Column(Text, default="")


class Order(Base):
    __tablename__ = "orders"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    supplier = Column(String)
    product  = Column(String)
    quantity = Column(Float)
    unit     = Column(String, default="unidades")
    expected = Column(String)
    logged   = Column(DateTime, default=datetime.utcnow)


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    action      = Column(String)
    input_text  = Column(Text)
    output_text = Column(Text)
    status      = Column(String, default="done")


class WhatsAppMessage(Base):
    __tablename__ = "messages"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    sender    = Column(String, index=True)
    direction = Column(String)  # "inbound" | "outbound"
    body      = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


class LearnedPattern(Base):
    __tablename__ = "patterns"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    timestamp     = Column(DateTime, default=datetime.utcnow)
    at_count      = Column(Integer)
    top_products  = Column(Text)   # JSON array of {"product": str, "count": int}
    peak_day      = Column(String)
    restock_notes = Column(Text)


Base.metadata.create_all(bind=engine)


# ── Inventory ───────────────────────────────────────────────────────────────

def add_inventory(product: str, quantity: float, unit: str) -> dict:
    db = SessionLocal()
    try:
        item = db.query(InventoryItem).filter_by(product=product).first()
        if item:
            item.quantity += quantity
            item.unit = unit
            item.last_updated = datetime.utcnow()
        else:
            item = InventoryItem(product=product, quantity=quantity, unit=unit)
            db.add(item)
        db.commit()
        return {
            "product": item.product,
            "quantity": item.quantity,
            "unit": item.unit,
            "last_updated": item.last_updated.isoformat(),
        }
    finally:
        db.close()


def get_inventory(product: str | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        q = db.query(InventoryItem)
        if product:
            q = q.filter_by(product=product)
        rows = q.order_by(InventoryItem.product).all()
        return [
            {
                "product": r.product,
                "quantity": r.quantity,
                "unit": r.unit,
                "last_updated": r.last_updated.isoformat(),
            }
            for r in rows
        ]
    finally:
        db.close()


def get_low_stock(threshold: float = 10.0) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(InventoryItem).filter(InventoryItem.quantity <= threshold).all()
        return [
            {"product": r.product, "quantity": r.quantity, "unit": r.unit}
            for r in rows
        ]
    finally:
        db.close()


# ── Sales ───────────────────────────────────────────────────────────────────

def log_sale(
    product: str,
    quantity: float,
    unit: str,
    amount: float | None = None,
    note: str = "",
) -> dict:
    db = SessionLocal()
    try:
        item = db.query(InventoryItem).filter_by(product=product).first()
        if item:
            item.quantity = max(0.0, item.quantity - quantity)
            item.last_updated = datetime.utcnow()
        sale = Sale(product=product, quantity=quantity, unit=unit, amount=amount, note=note)
        db.add(sale)
        db.commit()
        return {
            "id": sale.id,
            "product": sale.product,
            "quantity": sale.quantity,
            "unit": sale.unit,
            "amount": sale.amount,
            "timestamp": sale.timestamp.isoformat(),
        }
    finally:
        db.close()


def get_sales_since(hours: int = 24) -> list[dict]:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        rows = db.query(Sale).filter(Sale.timestamp >= cutoff).all()
        return [
            {
                "product": r.product,
                "quantity": r.quantity,
                "unit": r.unit,
                "amount": r.amount,
                "timestamp": r.timestamp.isoformat(),
                "note": r.note,
            }
            for r in rows
        ]
    finally:
        db.close()


# ── Orders ──────────────────────────────────────────────────────────────────

def log_order(
    supplier: str,
    product: str,
    quantity: float,
    unit: str,
    expected: str,
) -> dict:
    db = SessionLocal()
    try:
        order = Order(
            supplier=supplier,
            product=product,
            quantity=quantity,
            unit=unit,
            expected=expected,
        )
        db.add(order)
        db.commit()
        return {
            "id": order.id,
            "supplier": order.supplier,
            "product": order.product,
            "quantity": order.quantity,
            "unit": order.unit,
            "expected": order.expected,
            "logged": order.logged.isoformat(),
        }
    finally:
        db.close()


def get_orders() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Order).order_by(Order.logged.desc()).all()
        return [
            {
                "id": r.id,
                "supplier": r.supplier,
                "product": r.product,
                "quantity": r.quantity,
                "unit": r.unit,
                "expected": r.expected,
                "logged": r.logged.isoformat(),
            }
            for r in rows
        ]
    finally:
        db.close()


# ── Agent steps ─────────────────────────────────────────────────────────────

def log_step(
    action: str,
    input_text: str,
    output_text: str,
    status: str = "done",
) -> dict:
    db = SessionLocal()
    try:
        step = AgentStep(
            action=action,
            input_text=input_text,
            output_text=output_text,
            status=status,
        )
        db.add(step)
        db.commit()
        return {
            "id": step.id,
            "timestamp": step.timestamp.isoformat(),
            "action": step.action,
            "input_text": step.input_text,
            "output_text": step.output_text,
            "status": step.status,
        }
    finally:
        db.close()


def get_steps(limit: int = 100) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(AgentStep)
            .order_by(AgentStep.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "action": r.action,
                "input_text": r.input_text,
                "output_text": r.output_text,
                "status": r.status,
            }
            for r in rows
        ]
    finally:
        db.close()


# ── WhatsApp messages ────────────────────────────────────────────────────────

def log_message(sender: str, direction: str, body: str) -> dict:
    db = SessionLocal()
    try:
        msg = WhatsAppMessage(sender=sender, direction=direction, body=body)
        db.add(msg)
        db.commit()
        return {
            "id": msg.id,
            "sender": msg.sender,
            "direction": msg.direction,
            "body": msg.body,
            "timestamp": msg.timestamp.isoformat(),
        }
    finally:
        db.close()


def get_messages(limit: int = 10) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(WhatsAppMessage)
            .order_by(WhatsAppMessage.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "sender": r.sender,
                "direction": r.direction,
                "body": r.body,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ]
    finally:
        db.close()


# ── Learned patterns ─────────────────────────────────────────────────────────

def log_pattern(
    at_count: int,
    top_products: list[dict],
    peak_day: str,
    restock_notes: str,
) -> dict:
    import json as _json
    db = SessionLocal()
    try:
        pattern = LearnedPattern(
            at_count=at_count,
            top_products=_json.dumps(top_products, ensure_ascii=False),
            peak_day=peak_day,
            restock_notes=restock_notes,
        )
        db.add(pattern)
        db.commit()
        return {
            "id": pattern.id,
            "timestamp": pattern.timestamp.isoformat(),
            "at_count": pattern.at_count,
            "top_products": top_products,
            "peak_day": pattern.peak_day,
            "restock_notes": pattern.restock_notes,
        }
    finally:
        db.close()


def get_patterns(limit: int = 20) -> list[dict]:
    import json as _json
    db = SessionLocal()
    try:
        rows = (
            db.query(LearnedPattern)
            .order_by(LearnedPattern.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "at_count": r.at_count,
                "top_products": _json.loads(r.top_products or "[]"),
                "peak_day": r.peak_day,
                "restock_notes": r.restock_notes,
            }
            for r in rows
        ]
    finally:
        db.close()
