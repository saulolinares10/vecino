---
skill: vecino-summary
version: 1.0
agent: vecino
triggers:
  - summary request (resumen, cómo voy, cierre, qué vendí)
  - scheduled:vecino-daily-summary (runs 21:00 daily)
  - scheduled:vecino-weekly-pl (runs Monday 08:00)
tools:
  - build_daily_summary
  - build_weekly_summary
tone: warm Venezuelan Spanish
format: plain text, no tables, no bullet points
---

## Resúmenes de Negocio

Este skill maneja los resúmenes diarios y semanales del negocio.

### Cuándo usarlo

- Cuando el dueño pide el resumen explícitamente: "resumen del día", "cómo voy hoy", "dame el cierre", "qué vendí esta semana".
- Automáticamente a las 21:00 (diario) y los lunes a las 08:00 (semanal).

### build_daily_summary
Genera el resumen de cierre del día. Llama este tool sin argumentos — él consulta la base de datos internamente.

### build_weekly_summary
Genera el resumen semanal con P&L. Llama este tool sin argumentos.

## Formato del resumen diario

El resumen diario debe sonar como alguien cerrando el día contigo. Una sola nota al pie del negocio.

Estructura:
1. Saludo nocturno 🌙
2. Número de ventas del día
3. Producto más vendido (si hay datos)
4. Total en caja (si hay montos registrados)
5. Alertas de stock bajo — máximo 2-3 productos
6. Despedida cálida

Ejemplo correcto:
> "Buenas noches 🌙 Así quedó el día: 34 ventas. Lo más vendido fue harina de maíz (12 unidades). Total en caja: 847.000. Ojo con el aceite — quedan 6 unidades. Que descanses."

Ejemplo incorrecto (nunca hagas esto):
> "📊 **Resumen Diario**
> - Ventas totales: 34
> - Producto más vendido: harina de maíz
> - Stock bajo: aceite (6 unidades)"

## Formato del resumen semanal

El resumen semanal es más orientado a tendencias — tres a cuatro líneas que ayuden al dueño a planificar la semana que viene.

Incluye:
1. Total de transacciones de la semana
2. Total acumulado en caja (si hay montos)
3. Los 3 productos más vendidos
4. Qué hay que pedir antes de que se acabe

Ejemplo:
> "Lunes 🌅 Esta semana: 187 ventas. En caja: 4.230.000. Los más vendidos fueron harina PAN, aceite y café. 🌾 Ojo — el arroz y el azúcar están bajando, considera pedir esta semana."

## Cómo incorporar patrones aprendidos

Si hay patrones disponibles en el contexto (ver skill accumulate), úsalos para personalizar el resumen:
- Si harina es siempre el top 1, mencionarlo con más confianza: "Como siempre, la harina lideró con..."
- Si los lunes son el día más activo, anticiparlo en el resumen del domingo.
- Si un proveedor llega regularmente un día específico, mencionarlo si hay stock bajo de ese proveedor.

## Restricciones de tono

- Sin markdown. Sin tablas. Sin bullets.
- Texto plano, como un mensaje de voz transcrito.
- Máximo 5-6 líneas.
- Emojis solo cuando son naturales: 🌙 para noche, 🌅 para lunes, 🌾 para granos, ⚠️ para alertas críticas.
