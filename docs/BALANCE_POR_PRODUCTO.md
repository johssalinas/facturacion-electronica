# Balance por Producto

Reporte y panel para saber, producto por producto, cuánto se compró, cuánto se vendió,
si se ganó o se perdió dinero y cómo evolucionan precio e inventario.

## Dónde está

| Qué | Ruta |
|---|---|
| Reporte (filtros, gráficos, Excel, PDF) | `/app/query-report/Balance por Producto` |
| Panel con indicadores y gráficos | `/app/balance-de-productos` |
| Dashboard | `/app/dashboard-view/Balance por Producto` |
| Enlaces | Barra lateral de **Selling** y **Stock** (Balance por Producto, Panel de Balance), dashboards Selling y Stock, ícono "Balance de Productos" en el escritorio y accesos en el escritorio de Lorena y Andrea |

Acceso solo para: System Manager, Dueño Negocio, Accounts Manager, Stock Manager, Sales Manager,
Purchase Manager y Auditor. La cajera (Sales User, Stock User, Accounts User) **no** lo ve.

## Qué reporta

Todo en pesos **sin IVA** (`base_net_amount`). Los productos en gramos se muestran en kilos.

**Vista "Resumen por producto"** (una fila por producto): compras (cantidad, valor, costo promedio,
último costo), ventas (cantidad, valor, precio promedio, último precio), costo de lo vendido,
utilidad bruta, margen %, utilidad por unidad, ventas − compras, inventario inicial / ajustes / final,
valor del inventario, días de cobertura, clasificación ABC, participación en ventas y alertas.

**Vista "Evolución por producto"**: lo mismo por producto y período (diario, semanal, mensual,
trimestral, anual), con variación de precio y de costo contra el período anterior.

**Vista "Evolución total"**: un renglón por período con todos los productos juntos.

Filtros: empresa, fechas, vista, período, grupo de producto, producto, almacén, base de costo,
resultado (ganancia / pérdida / sin costo confiable), columnas (completo o compacto para PDF),
incluir productos sin ventas e incluir costos sospechosos (ambos apagados por defecto). Exportar a Excel o PDF con el menú del reporte;
el formato "Compacto" deja 16 columnas para que el PDF sea legible.

## Cómo se calcula el costo (importante)

El filtro **Base de costo** tiene dos opciones:

1. **Costo de compra (promedio)**, por defecto. Costo de lo vendido = cantidad vendida × promedio
   ponderado de todas las compras del producto hasta la fecha de cada venta.
2. **Kardex del sistema (FIFO)**. Es el valor contable que calcula ERPNext.

Un producto **sin ninguna compra registrada** no tiene costo conocido. No se inventa utilidad:
queda como "Sin costo" y sus ventas se muestran aparte en "Ventas sin costo confiable".

Un producto cuyo margen cae fuera de −100 % a 99 % se marca "Costo sospechoso" (casi siempre es
una unidad de medida o un precio de compra mal digitado). Por defecto no entra en utilidad,
margen ni valor del inventario; marque **Incluir costos sospechosos** para verlo sumado.

## Datos que conviene corregir en ERPNext

Estado al 7-nov-2026, medido con este reporte:

- 644 productos vendidos ($55,8 M en ventas) no tienen ninguna compra registrada. Entraron como
  "Inventario Inicial" a costo $0. Mientras no se les cargue costo, no hay utilidad calculable.
- 18 productos con costo sospechoso. Ejemplos: `PROD-00323` queso en bloque (inventario inicial
  a $10.000 por gramo), `PROD-01277` queso cheddar (compra a $55,3 M por kilo) y `PROD-01126`
  almendras. Filtre Resultado = "Sin costo confiable" para verlos todos.
- 570 productos con stock negativo (se vendió más de lo registrado).
- Ventas de enero a junio ($122 M) están migradas de SIIGO sin detalle de producto y no entran
  al análisis por producto.

Con la base "Kardex" la utilidad total sale mucho más alta (≈69 %) porque muchos productos
tienen costo $0 en el kardex. No la use para decidir hasta corregir el inventario inicial.

## Qué incluye el código

| Archivo | Función |
|---|---|
| `facturacion_electronica/facturacion_electronica/report/balance_por_producto/` | Reporte (Python, JS y JSON) |
| `facturacion_electronica/utils/setup_balance_producto.py` | Crea tarjetas, gráficos, dashboard, workspace, barra lateral, ícono y los enlaces en Selling y Stock. Idempotente, corre en cada `bench migrate` (hook `after_migrate`) |

Cada paso de la configuración corre aislado: si uno falla se registra en Error Log y el
`migrate` continúa. No modifica facturas, inventario ni contabilidad.

## Supuestos

- Ventas = Sales Invoice (docstatus 1). Compras = Purchase Invoice. No se leen Purchase Receipt,
  Delivery Note ni POS Invoice porque hoy no tienen movimientos (0 documentos). Si algún día se
  usan, hay que incluirlos para no subcontar ni duplicar.
- Solo productos inventariables (`is_stock_item = 1`).
- Las tarjetas numéricas guardan su resultado 5 minutos en caché.

## Despliegue

Igual que el resto de la app (ver `DOCUMENTACION_COMPLETA.md`, sección 5.5): push a GitHub,
reconstruir la imagen `erpnext-fe`, redeploy en Coolify y `bench migrate`. El `migrate` sincroniza el
reporte y ejecuta `setup_balance_producto.run`. No ejecutar `bench build`.
