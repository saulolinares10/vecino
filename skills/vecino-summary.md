---
skill: vecino-summary
version: 1.0
agent: vecino
triggers:
  - SUMMARY
  - scheduled:vecino-daily-summary
  - scheduled:vecino-weekly-pl
tools:
  - memory.get_sales_since
  - memory.get_low_stock
  - memory.get_inventory
language: es
format: plain text, no markdown, WhatsApp-safe, max 10 lines
---

## Propósito

Genera resúmenes del negocio en español casual. Formato WhatsApp: texto plano,
sin asteriscos, sin listas con guiones, emojis solo cuando son naturales.
Máximo 10 líneas. Siempre termina con una nota cálida.

## Resumen diario (vecino-daily-summary)

Corre a las 9pm. Usa `memory.get_sales_since(hours=24)` y `memory.get_low_stock()`.

Incluye en orden:
1. Saludo nocturno con 🌙
2. Total de ventas del día (número de transacciones)
3. Producto más vendido y cuántas unidades
4. Total en caja si hay montos registrados
5. Alertas de stock bajo (máximo 2 productos)
6. Cierre cálido

Ejemplo correcto:
```
Buenas noches 🌙 Así quedó el día: 34 ventas. Lo más vendido fue harina de maíz (12 unidades). En caja: 847.000. Ojo con el aceite — quedan 6 unidades. Que descanses.
```

Ejemplo incorrecto (nunca hacer esto):
```
📊 Resumen Diario:
- Ventas: 34
- Top producto: harina
```

Si no hubo ventas: "Buenas noches 🌙 Hoy sin ventas registradas. Mañana será mejor. Que descanses."

## Resumen semanal con P&L (vecino-weekly-pl)

Corre los lunes a las 8am. Usa `memory.get_sales_since(hours=168)`.

Incluye en orden:
1. Saludo de lunes con 🌅
2. Total de transacciones de la semana
3. Total acumulado en caja (si hay montos)
4. Los 3 productos más vendidos
5. Mejor día de la semana (más ventas)
6. Peor día de la semana (menos ventas)
7. Total de unidades movidas
8. Una nota hacia adelante basada en los datos
9. Saludo motivador de lunes

Nota hacia adelante — ejemplos según datos:
- Si un día fue consistentemente bajo: "El martes suele ser lento — buen día para pedir a proveedores."
- Si hay stock bajo de los productos más vendidos: "Considera reponer [producto] antes del fin de semana."
- Si las ventas subieron vs semana anterior: "Buen ritmo — sigue así 🙌"

Ejemplo correcto:
```
Lunes 🌅 Esta semana: 187 ventas. En caja: 4.230.000. Los más vendidos: harina PAN, aceite, café. Mejor día: viernes. El martes suele ser lento — buen día para pedir. Buena semana.
```

Si no hubo ventas en la semana: "Lunes 🌅 Esta semana sin ventas registradas. Buen momento para revisar el inventario y arrancar con fuerza."
