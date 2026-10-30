# Análisis: Cambios en los Endpoints de Recepción de Facturas Factus

**Fecha de análisis:** 29 de septiembre de 2026  
**Analista:** Kiro AI  
**Proyecto:** Salsamentaria Multiespecial - Integración Factus

---

## Resumen Ejecutivo

✅ **IMPACTO EN NUESTRA IMPLEMENTACIÓN: NINGUNO**

Los cambios documentados en "Cambios en los endpoints de recepción de facturas" se refieren a:

1. **Migración de V1 a V2** de la API de Factus (ya implementamos V2 desde el inicio)
2. **Módulo de Recepción de Documentos** (recibir facturas de proveedores) - **NO IMPLEMENTADO** en nuestro proyecto

**Conclusión:** No se requiere ningún cambio en el código actual.

---

## Detalles del Análisis

### 1. ¿Qué es el Módulo de Recepción de Documentos?

El módulo de recepción (`/v2/receptions/*`) de Factus sirve para **recibir y gestionar facturas electrónicas que otros te emiten a ti** (como proveedor comprador).

**Endpoints del módulo:**

```
GET  /v2/receptions/bills          → Listar facturas recibidas
POST /v2/receptions/upload         → Cargar factura de proveedor (CUFE)
POST /v2/receptions/bills/{id}/events/accept     → Aceptar factura
POST /v2/receptions/bills/{id}/events/reject     → Rechazar factura
POST /v2/receptions/bills/{id}/events/claim      → Reclamar factura
```

**Nuestra implementación actual:**

```python
# facturacion_electronica/utils/api_fe.py

# SOLO USAMOS ESTOS ENDPOINTS (EMISIÓN):
url = f"{self.base_url}/v2/bills/validate"           # Crear y validar facturas
url = f"{self.base_url}/v2/bills/{number}/download-pdf"  # Descargar PDF
url = f"{self.base_url}/v2/bills/destroy/reference/{reference_code}"  # Eliminar
url = f"{self.base_url}/v2/numbering-ranges"         # Consultar rangos

# NO USAMOS NINGÚN ENDPOINT DE RECEPTIONS
```

**Búsqueda en código:**

```bash
grep -r "receptions" facturacion_electronica/
# Resultado: No matches found
```

### 2. Cambios V1 → V2 (Migración General de Factus)

Los cambios documentados en la guía de migración V1→V2 son:

#### 2.1 Campo `payment_details` (Array en lugar de campos simples)

**V1 (deprecado):**
```json
{
  "payment_form": "1",
  "payment_method_code": "10"
}
```

**V2 (actual):**
```json
{
  "payment_details": [
    {
      "payment_form": "1",
      "payment_method_code": "10",
      "amount": "50000.00"
    }
  ]
}
```

**Estado en nuestra implementación:**
```python
# facturacion_electronica/utils/api_fe.py línea 302-315
def _get_payment_details(doc):
    details = []
    payments = doc.get("payments") or []
    for p in payments:
        amount = flt(p.amount, 2)
        if amount <= 0:
            continue
        details.append({
            "payment_form": "1",
            "payment_method_code": _get_metodo_pago(p.mode_of_payment),
            "amount": str(amount),
        })
    # ...
    return details
```

✅ **YA IMPLEMENTADO CORRECTAMENTE** - Usamos array `payment_details` con formato V2.

#### 2.2 Campo `cash_rounding_amount`

**Nuevo en V2:**
```json
{
  "cash_rounding_amount": "0.00"
}
```

**Estado en nuestra implementación:**
```python
# Presente en todos nuestros payloads
payload = {
    # ...
    "cash_rounding_amount": "0.00",
    # ...
}
```

✅ **YA IMPLEMENTADO** - Siempre enviamos `"0.00"` (sin redondeo).

#### 2.3 Campos del Customer

**Cambios V1 → V2:**

| Campo V1 | Campo V2 | Nuestra Implementación |
|----------|----------|------------------------|
| `identification_document_id` | `identification_document_code` | ✅ Usamos `identification_document_code` |
| `legal_organization_id` | `legal_organization_code` | ✅ Usamos `legal_organization_code` |
| `tribute_id` | `tribute_code` | ✅ Usamos `tribute_code` |
| `municipality_id` | `municipality_code` | ✅ Usamos `municipality_code` |

**Código actual:**
```python
# facturacion_electronica/utils/api_fe.py línea 245-258
obj = {
    "identification_document_code": id_doc,  # ✅ V2
    "identification": identification,
    "legal_organization_code": "1" if is_company else "2",  # ✅ V2
    "tribute_code": _fe_codigo("Tributo FE", cust.get("fe_tribute_code"), fallback="ZZ"),  # ✅ V2
}
# ...
if muni_codigo:
    obj["municipality_code"] = muni_codigo  # ✅ V2
```

✅ **YA IMPLEMENTADO CORRECTAMENTE** - Todos los campos usan nomenclatura V2.

#### 2.4 Campos de Items

**Cambios V1 → V2:**

| Campo V1 | Campo V2 | Nuestra Implementación |
|----------|----------|------------------------|
| `price` (bruto con IVA) | `price` (neto sin IVA) | ✅ Usamos `net_unit_value` (neto) |
| `unit_measure_id` | `unit_measure_code` | ✅ Usamos `unit_measure_code` |
| `standard_id` | `standard_code` | ✅ Usamos `product_key` (código estándar) |
| `tax_rate` (número) | `taxes` (array) | ✅ Usamos array `taxes` |

**Código actual:**
```python
# facturacion_electronica/utils/api_fe.py línea 370-398
item_obj = {
    "name": item_name,
    "product_key": item.get("item_code") or item.get("item_name"),  # standard_code
    "unit_measure_code": uom_code,  # ✅ V2
    "quantity": str(qty),
    "net_unit_value": str(net_rate),  # ✅ Precio NETO (sin IVA)
    "discount_percent": str(discount),
    "taxes": taxes_list,  # ✅ Array de taxes
}
```

✅ **YA IMPLEMENTADO CORRECTAMENTE** - Items en formato V2, precio neto.

#### 2.5 Array `taxes` con múltiples impuestos

**V1 (deprecado):**
```json
{
  "tax_rate": 19,
  "tribute_id": 1
}
```

**V2 (actual):**
```json
{
  "taxes": [
    {
      "tax_code": "01",
      "tax_name": "IVA",
      "tax_percent": "19.00",
      "tax_amount": "1900.00"
    }
  ]
}
```

**Código actual:**
```python
# facturacion_electronica/utils/api_fe.py línea 380-390
for tax in item.get("taxes") or []:
    # ...
    taxes_list.append({
        "tax_code": tax_code,  # ✅ V2
        "tax_name": tax_name,
        "tax_percent": str(rate),
        "tax_amount": str(tax_amount),
    })
```

✅ **YA IMPLEMENTADO CORRECTAMENTE** - Array de taxes con formato V2.

#### 2.6 Items excluidos de impuesto

**V2:**
```json
{
  "taxes": [
    {
      "is_excluded": true
    }
  ]
}
```

**Código actual:**
```python
# facturacion_electronica/utils/api_fe.py línea 384-385
if account.get("fe_is_excluded"):
    taxes_list.append({"is_excluded": True})
```

✅ **YA IMPLEMENTADO CORRECTAMENTE** - Soportamos items excluidos.

---

## 3. Cambios NO Aplicables a Nuestro Proyecto

### 3.1 Campo `prepayment_details`

**Descripción:** Manejo de anticipos (prepagos) en facturas.

**Estado:** No implementado.

**Razón:** No es requerido para el negocio actual. Las facturas se cobran completas, no se manejan anticipos estructurados.

**¿Necesitamos implementarlo?** ❌ No, a menos que el negocio requiera facturar con anticipos formales.

### 3.2 Campo `withholding_taxes` (Autoretenciones)

**Descripción:** Retenciones en la fuente aplicadas en la factura.

**Estado:** No implementado.

**Razón:** No aplica para el modelo de negocio (ventas a consumidor final y B2B sin autorretención).

**¿Necesitamos implementarlo?** ❌ No, a menos que se requiera facturar con retenciones.

### 3.3 Módulo de Recepción de Documentos

**Descripción:** Recibir, aceptar, rechazar facturas de proveedores.

**Estado:** No implementado.

**Razón:** El proyecto solo cubre **emisión** de facturas de venta, no **recepción** de facturas de compra.

**¿Necesitamos implementarlo?** ⚠️ **Potencialmente útil** si se quiere automatizar:
- Recepción de facturas de proveedores
- Eventos de acuse (aceptación/rechazo)
- Integración automática con Purchase Invoice

**Beneficio:** Cumplimiento automático de eventos DIAN, evitar multas por no responder facturas recibidas.

---

## 4. Verificación de Endpoints Usados

**Análisis del código actual:**

```python
# Grep en todo el código Python
grep -r "self.base_url" facturacion_electronica/

# Resultados:
/v2/bills/validate                          # ✅ Emisión facturas
/v2/bills/{number}/download-pdf             # ✅ Descargar PDF
/v2/bills/destroy/reference/{code}          # ✅ Eliminar factura pendiente
/v2/numbering-ranges                        # ✅ Consultar rangos (usado en tests)
/oauth/token                                # ✅ Autenticación OAuth2
```

**Endpoints de Recepción (NO USADOS):**
```
/v2/receptions/*                            # ❌ No implementado
```

---

## 5. Recomendaciones

### 5.1 Acciones Requeridas

✅ **NINGUNA** - La implementación actual ya usa V2 correctamente.

### 5.2 Acciones Opcionales (Mejoras Futuras)

#### Opción A: Implementar Recepción de Facturas de Proveedores

**Beneficios:**
- Cumplimiento automático DIAN (eventos de acuse)
- Integración automática Purchase Invoice ↔ Factura DIAN
- Evitar multas por no responder facturas recibidas en 3 días
- Trazabilidad completa de documentos recibidos

**Complejidad:** Media (3-5 días desarrollo)

**Endpoints a implementar:**
```python
def cargar_factura_proveedor(self, cufe):
    """Carga una factura recibida de proveedor usando su CUFE"""
    url = f"{self.base_url}/v2/receptions/upload"
    return requests.post(url, headers=self._headers(), json={"track_id": cufe})

def listar_facturas_recibidas(self, filters=None):
    """Lista facturas electrónicas recibidas"""
    url = f"{self.base_url}/v2/receptions/bills"
    # Filtros: id, number, issue_date, cufe, company_nit, completed_events
    return requests.get(url, headers=self._headers(), params=filters)

def aceptar_factura(self, reception_id):
    """Emite evento de aceptación de factura"""
    url = f"{self.base_url}/v2/receptions/bills/{reception_id}/events/accept"
    return requests.post(url, headers=self._headers())

def rechazar_factura(self, reception_id, reason_code, description):
    """Emite evento de rechazo de factura"""
    url = f"{self.base_url}/v2/receptions/bills/{reception_id}/events/reject"
    payload = {"reason_code": reason_code, "description": description}
    return requests.post(url, headers=self._headers(), json=payload)
```

**Integración con Purchase Invoice:**
```python
# Hook: on_submit Purchase Invoice
def on_submit_purchase_invoice(doc, method=None):
    # Si tiene CUFE del proveedor
    if doc.custom_cufe_proveedor:
        # Cargar factura en Factus
        api = FacturacionElectronicaAPI(dueno_fiscal)
        api.cargar_factura_proveedor(doc.custom_cufe_proveedor)
        # Emitir evento de aceptación automáticamente
        api.aceptar_factura(reception_id)
```

#### Opción B: Implementar Anticipos (`prepayment_details`)

Solo si el negocio lo requiere (actualmente no aplica).

#### Opción C: Implementar Retenciones (`withholding_taxes`)

Solo si se va a facturar con retenciones (actualmente no aplica).

### 5.3 Pruebas de Regresión

Aunque no hay cambios requeridos, se recomienda ejecutar el siguiente test de regresión:

```python
# Test: Verificar que el payload generado sea V2-compliant
from facturacion_electronica.utils.api_fe import _construir_payload

doc = frappe.get_doc("Sales Invoice", "ACC-SINV-2026-00001")
dueno = frappe.get_doc("Dueno Fiscal", "Lorena")
items = doc.get("items")
config = frappe.get_single("Configuracion API FE")

payload = _construir_payload(doc, dueno, items, "Inmediata B2B", config)

# Verificaciones V2:
assert "payment_details" in payload  # ✅ Array
assert isinstance(payload["payment_details"], list)
assert "cash_rounding_amount" in payload  # ✅ Presente
assert "identification_document_code" in payload["customer"]  # ✅ V2 field
assert "taxes" in payload["items"][0]  # ✅ Array de taxes
assert isinstance(payload["items"][0]["taxes"], list)

print("✅ Payload es V2-compliant")
```

---

## 6. Conclusiones

### ✅ Estado Actual: CONFORME

- Nuestra implementación usa **Factus API V2** desde el inicio
- Todos los campos usan nomenclatura V2 (`*_code` en lugar de `*_id`)
- Estructura de datos correcta (arrays de `payment_details` y `taxes`)
- Precios netos sin IVA incluido
- Formato de dirección cumple FAK08 (ya corregido)

### ❌ No Afectado por Cambios de Recepción

- Los cambios documentados en el PDF se refieren al módulo de **recepción** de facturas
- Nuestro proyecto solo implementa **emisión** de facturas
- No usamos ningún endpoint `/v2/receptions/*`

### 🔮 Oportunidades Futuras

Si se requiere en el futuro:

1. **Recepción de Facturas de Proveedores** → Implementar módulo nuevo (3-5 días)
2. **Anticipos** → Agregar campo `prepayment_details` (1 día)
3. **Retenciones** → Agregar campo `withholding_taxes` (1 día)

---

## 7. Acciones Inmediatas

**Ninguna acción requerida.**

El código actual está correcto y no necesita cambios por el documento analizado.

---

## Anexo A: Comparativa de Endpoints

| Módulo | Endpoint | Implementado | Usado |
|--------|----------|--------------|-------|
| **EMISIÓN** | | | |
| Crear factura | `POST /v2/bills/validate` | ✅ Sí | ✅ Sí |
| Descargar PDF | `GET /v2/bills/{id}/download-pdf` | ✅ Sí | ✅ Sí |
| Eliminar factura | `DELETE /v2/bills/destroy/reference/{code}` | ✅ Sí | ✅ Sí |
| Consultar rangos | `GET /v2/numbering-ranges` | ✅ Sí | ⚠️ Solo testing |
| **RECEPCIÓN** | | | |
| Cargar factura recibida | `POST /v2/receptions/upload` | ❌ No | ❌ No |
| Listar recibidas | `GET /v2/receptions/bills` | ❌ No | ❌ No |
| Aceptar factura | `POST /v2/receptions/bills/{id}/events/accept` | ❌ No | ❌ No |
| Rechazar factura | `POST /v2/receptions/bills/{id}/events/reject` | ❌ No | ❌ No |
| Reclamar factura | `POST /v2/receptions/bills/{id}/events/claim` | ❌ No | ❌ No |

---

**Fin del análisis.**

**Firma:** Kiro AI  
**Fecha:** 29 de septiembre de 2026  
**Archivo fuente:** Cambios en los endpoints de recepción de facturas.pdf
