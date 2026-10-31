# Lecciones Aprendidas - Facturación Electrónica

## ❌ Error: Doble Aplicación de IVA

### Problema Identificado
**Fecha:** 2026-10-30  
**Facturas afectadas:** SM1 - SM22 (22 facturas)

### Descripción del Error
Al generar las facturas consolidadas en producción, usamos el campo `grand_total` de las Sales Invoices de ERPNext, el cual **ya incluye el IVA calculado**.

Luego, al enviar este monto a la API de Factus como base de los items, **Factus volvió a calcular y agregar el IVA**, resultando en una **doble aplicación del impuesto**.

### Impacto
- **Monto esperado:** ~$73.7 millones
- **Monto real facturado:** ~$85 millones
- **Sobrefacturación:** ~$12 millones (16% de exceso)

### Causa Raíz
```python
# ❌ INCORRECTO - Lo que hicimos
total_dia = sum(flt(i["qty"]) * flt(i["net_rate"]) for i in items)
# Donde net_rate venía de: sii.rate (que es el precio CON IVA en algunas facturas)

# El payload enviaba items con precios que ya incluían IVA
# Factus le agregaba IVA nuevamente al total
```

### Solución Correcta
```python
# ✅ CORRECTO - Lo que debimos hacer
# Opción 1: Usar base_net_rate (precio sin impuestos)
sql = """
    SELECT 
        sii.item_code,
        sii.item_name,
        SUM(sii.qty) as qty,
        sii.base_net_rate as net_rate,  -- Precio SIN impuestos
        sii.uom
    FROM `tabSales Invoice Item` sii
    ...
"""

# Opción 2: Calcular el neto desde grand_total
net_amount = grand_total / (1 + (tax_rate / 100))

# Opción 3: Usar net_total en lugar de grand_total
net_total = frappe.db.get_value("Sales Invoice", invoice_name, "net_total")
```

### Estructura Correcta del Payload

```python
# Para cada item en el payload de Factus:
item_payload = {
    "code": item_code,
    "description": item_name,
    "quantity": qty,
    "unit_measure_id": uom_id,
    "price_amount": net_price,  # ⚠️ Este debe ser SIN IVA
    "base_quantity": qty,
    "tax_totals": [{
        "tax_id": tax_code,  # IVA
        "tax_amount": price * qty * (tax_rate / 100),  # Factus calculará esto
        "taxable_amount": price * qty,  # Base gravable
        "percent": tax_rate  # 19% o 5%
    }]
}
```

### Acciones Tomadas
1. ✅ Error documentado en este archivo
2. ⏳ Nota crédito para SM16 ($5,760,048) para ajustar el total
3. ⏳ Actualizar scripts batch_*.py con la lógica correcta

### Acciones Futuras
- [ ] Modificar `get_ventas_por_dia_*()` para usar `base_net_rate` o `net_total`
- [ ] Agregar validación en `_get_item_obj()` para verificar que el precio no incluya IVA
- [ ] Crear tests unitarios que validen el cálculo correcto de totales
- [ ] Documentar claramente en el código que `price_amount` debe ser neto

### Campos Correctos en ERPNext

```python
# Sales Invoice Item (tabSales Invoice Item)
- rate: Precio unitario (puede incluir o no IVA según configuración)
- base_rate: Precio en moneda base
- net_rate: Precio después de descuentos
- base_net_rate: Precio neto en moneda base (⭐ USAR ESTE)

# Sales Invoice (tabSales Invoice)
- total: Subtotal de items (antes de impuestos)
- net_total: Total neto después de descuentos (antes de impuestos) (⭐ USAR ESTE)
- grand_total: Total final CON impuestos (❌ NO USAR como base)
- base_grand_total: Grand total en moneda base
```

### Ejemplo Correcto

```python
def get_ventas_por_dia_corregido(fecha_inicio, fecha_fin):
    """Versión corregida - usa net_rate que es sin IVA"""
    sql = """
        SELECT 
            si.posting_date,
            sii.item_code,
            sii.item_name,
            sii.uom,
            SUM(sii.qty) as qty,
            sii.net_rate as price_without_tax,  -- Precio sin impuestos
            AVG(stc.rate) as tax_rate  -- Tasa de IVA aplicable
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        INNER JOIN `tabSales Taxes and Charges` stc 
            ON stc.parent = si.name 
        WHERE si.posting_date >= %s 
        AND si.posting_date <= %s 
        AND si.docstatus = 1
        GROUP BY si.posting_date, sii.item_code
        ORDER BY si.posting_date, sii.item_code
    """
    
    rows = frappe.db.sql(sql, (fecha_inicio, fecha_fin), as_dict=True)
    
    # Verificar totales
    for row in rows:
        base = row["price_without_tax"] * row["qty"]
        tax = base * (row["tax_rate"] / 100)
        total_with_tax = base + tax
        # Este total_with_tax debería coincidir con el grand_total de la factura
```

### Verificación en Factus
Después de enviar una factura, verificar en la respuesta:
```json
{
  "legal_monetary_totals": {
    "line_extension_amount": "1000000.00",  // Base sin IVA
    "tax_exclusive_amount": "1000000.00",   // Total antes de impuestos
    "tax_inclusive_amount": "1190000.00",   // Total CON IVA (19%)
    "payable_amount": "1190000.00"          // Total a pagar
  }
}
```

Si `tax_inclusive_amount` es muy alto, es señal de doble IVA.

### Referencias
- ERPNext Sales Invoice DocType: https://frappeframework.com/docs/
- Factus API v2 Documentation: https://docs.factus.com.co/
- DIAN Resolución FAK08: Anexo técnico factura electrónica

---
**Última actualización:** 2026-10-30  
**Estado:** Documentado - Pendiente corrección en código
