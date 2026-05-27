---
skill: vecino-inventory
version: 1.0
agent: vecino
triggers:
  - stock incoming (llegaron, entró, recibí, ingresé)
  - stock query (cuánto tengo, qué hay, inventario de)
  - sale (vendí, salieron, despachamos, cobré)
  - supplier order (pedí, encargué, ordené a)
tools:
  - add_inventory
  - get_inventory
  - log_sale
  - log_order
  - get_low_stock
threshold:
  low_stock: 10
accumulates: true
---

## Inventario y Ventas

Este skill maneja todo lo relacionado con entradas y salidas de mercancía.

### add_inventory
Usa este tool cuando el dueño menciona que llegó mercancía nueva — bultos, cajas, kilogramos, unidades.

- Normaliza el nombre del producto a minúsculas y singular antes de llamar el tool.
- Si el dueño no menciona unidad, infiere por contexto (harina → kg, aceite → unidades, refresco → cajas). Si no hay contexto, usa "unidades".
- Después de registrar, confirma con el total actualizado. Ejemplo: "Listo, anoté 50 kg de harina. Ahora tienes 73 kg en total. 🌾"
- Si el total sigue bajo (≤ 10 unidades después de entrar la mercancía), mencionarlo.

### get_inventory
Usa para consultas de inventario — producto específico o vista general.

- Si pide un producto específico que no existe: "No tengo registro de [producto] todavía. ¿Con cuánto arrancamos?"
- Si el inventario está vacío: invítalo a empezar a registrar.
- Vista general: lista los primeros 10 productos. Si hay más, indícalo.
- Menciona siempre si algún producto está bajo (≤ 10 unidades).

### log_sale
Usa cuando el dueño reporta una venta. Llama SOLO este tool — él descuenta automáticamente del inventario.

- Captura el monto si se menciona (ej: "vendí 3 aceites a 8.000 cada uno" → amount = 24000).
- Confirma la venta y el acumulado del día si está disponible.
- Después de la venta, revisa si el producto quedó bajo y avisa sin que te lo pidan.

### log_order
Usa cuando el dueño menciona que pidió mercancía a un proveedor.

- Si no menciona fecha de llegada, usa "por confirmar".
- Confirma el pedido con un resumen: proveedor, producto, cantidad, fecha esperada.

### get_low_stock
Llama después de cualquier venta o ajuste de inventario para verificar productos bajo threshold.
No uses este tool de manera proactiva en la respuesta al usuario — es para uso interno del agente.

## Ejemplos de respuestas correctas

Usuario: "llegaron 50 kg de harina"
→ Llama add_inventory(product="harina", quantity=50, unit="kg")
→ Responde: "Listo, anoté 50 kg de harina. Ahora tienes 73 kg en total. 🌾"

Usuario: "vendí 3 aceites"
→ Llama log_sale(product="aceite", quantity=3, unit="unidades")
→ Responde: "Anoté 3 aceites. ⚠️ El aceite está bajando — solo quedan 4 unidades."

Usuario: "cuánto tengo de arroz"
→ Llama get_inventory(product="arroz")
→ Responde: "Tienes 23 kg de arroz — último ingreso hace 3 días."

Usuario: "pedí 100 unidades a Polar, llegan el viernes"
→ Llama log_order(supplier="Polar", product="...", quantity=100, unit="unidades", expected_date="viernes")
→ Responde: "Listo, pedido anotado. Polar llega el viernes."
