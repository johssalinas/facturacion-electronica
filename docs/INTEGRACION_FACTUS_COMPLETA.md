# Integración Completa con Factus API — Facturación Electrónica DIAN Colombia

**Fecha de creación:** 29 de septiembre de 2026  
**Proyecto:** Salsamentaria Multiespecial  
**Versión ERPNext:** v16.25.0  
**Versión Frappe:** v16.24.0

---

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Requisitos Previos](#requisitos-previos)
3. [Arquitectura de la Integración](#arquitectura-de-la-integración)
4. [Configuración Inicial](#configuración-inicial)
5. [Estructura de Datos](#estructura-de-datos)
6. [Flujos de Facturación](#flujos-de-facturación)
7. [Formato de Payload a Factus](#formato-de-payload-a-factus)
8. [Ambientes: Sandbox vs Producción](#ambientes-sandbox-vs-producción)
9. [Rangos de Numeración](#rangos-de-numeración)
10. [Resolución de Problemas Comunes](#resolución-de-problemas-comunes)
11. [Compliance DIAN (FAK08)](#compliance-dian-fak08)
12. [Testing y Validación](#testing-y-validación)
13. [Despliegue de Cambios](#despliegue-de-cambios)
14. [Mantenimiento](#mantenimiento)

---

## Introducción

Esta documentación describe la integración completa entre ERPNext y Factus API para cumplir con la normativa de Facturación Electrónica de la DIAN en Colombia.

### ¿Qué es Factus?

Factus es un proveedor autorizado de facturación electrónica que actúa como intermediario entre tu sistema y la DIAN. Su API permite:

- Emitir facturas electrónicas de venta
- Generar notas crédito y débito
- Administrar rangos de numeración
- Obtener CUFE (Código Único de Factura Electrónica)
- Descargar PDF y XML certificados por DIAN

### Modalidades Soportadas

1. **B2B Inmediata:** Facturas a empresas enviadas inmediatamente a DIAN al momento de crear la factura
2. **CCF (Consumidor Final):** Facturas agrupadas en un resumen diario que se envía al cierre de caja

---

## Requisitos Previos

### 1. Cuentas y Credenciales

#### Sandbox (Pruebas)
- **URL Base:** `https://api-sandbox.factus.com.co`
- **Dashboard:** `https://app-sandbox.factus.com.co`
- Factus proporciona credenciales de prueba pre-configuradas
- Los rangos de numeración vienen pre-creados (prefijos genéricos: SETP, NA, NC, ND, SEDS)

#### Producción
- **URL Base:** `https://api.factus.com.co`
- **Dashboard:** `https://app.factus.com.co`
- Requiere contrato con Factus
- Requiere certificado digital emitido por la DIAN
- Requiere resolución de numeración DIAN vigente

**Credenciales necesarias (ambos ambientes):**
```
- client_id: UUID proporcionado por Factus
- client_secret: Clave secreta del cliente OAuth2
- username: Email de la cuenta Factus
- password: Contraseña de la cuenta Factus
```

### 2. Información Legal de la Empresa

Para facturar electrónicamente necesitas:

- **NIT** con dígito de verificación (DV)
- **Resolución de numeración DIAN** (número, prefijo, rango desde-hasta, vigencia)
- **Certificado digital DIAN** (para producción)
- **Datos del representante legal** (nombres, apellidos, documento)
- **Dirección fiscal** con código DIVIPOLA del municipio

### 3. Infraestructura ERPNext

- ERPNext v15+ (probado en v16.25.0)
- Python 3.11+
- Acceso al servidor para instalar la app custom
- Permisos de System Manager para configuración

---

## Arquitectura de la Integración

### Componentes Principales

```
ERPNext
  └── App: facturacion_electronica
       ├── DocTypes Custom
       │    ├── Configuracion API FE (Single)
       │    ├── Dueno Fiscal (Normal)
       │    ├── Log Factura Electronica (Document)
       │    └── Catálogos DIAN (Municipio, Tributo, etc.)
       │
       ├── Custom Fields en DocTypes Estándar
       │    ├── Customer (identificación FE, municipio, tributo)
       │    ├── Item (dueno_fiscal)
       │    ├── Sales Invoice / POS Invoice (estado_fe, cufe)
       │    ├── Account (fe_tax_code)
       │    └── Mode of Payment (fe_tipo_medio_pago)
       │
       ├── Hooks y Eventos
       │    ├── on_submit → envío inmediato (B2B)
       │    ├── before_submit POS Closing → bloqueo si hay pendientes
       │    └── scheduler hourly → reintentos automáticos
       │
       └── API Client
            ├── Autenticación OAuth2
            ├── Construcción de payload
            ├── Emisión y validación
            └── Descarga de PDF/XML
```

### Flujo de Datos

```
Sales Invoice/POS Invoice
         ↓
   Validación de datos
         ↓
   Construcción payload JSON
         ↓
   POST a Factus API /v2/bills/validate
         ↓
   Factus → DIAN (validación)
         ↓
   Respuesta con CUFE y estado
         ↓
   Log Factura Electronica (registro)
         ↓
   Actualización estado_fe en factura
```

---

## Configuración Inicial

### Paso 1: Instalar la App Custom

**En el servidor:**

```bash
# SSH al servidor
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129

# Obtener container ID del backend
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Clonar e instalar la app
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench get-app https://github.com/johssalinas/facturacion-electronica && \
  bench --site salsamentariamultiespecial.duckdns.org install-app facturacion_electronica'
```

**Nota:** En ambiente con Coolify, se usa imagen Docker custom que incluye la app horneada. Ver `DOCUMENTACION_COMPLETA.md` sección 2.5.

### Paso 2: Migrar la Base de Datos

```bash
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site salsamentariamultiespecial.duckdns.org migrate'
```

Esto crea:
- Todos los DocTypes custom
- Los Custom Fields en doctypes estándar
- Las tablas de catálogos DIAN

### Paso 3: Cargar Catálogos DIAN

Los catálogos se deben poblar manualmente o via fixtures. Principales catálogos:

#### Municipio FE (código DIVIPOLA)
```python
# Ejemplos Santander
[
  {"nombre": "Bucaramanga", "codigo": "68001"},
  {"nombre": "Floridablanca", "codigo": "68276"},
  {"nombre": "Girón", "codigo": "68406"},
  {"nombre": "Piedecuesta", "codigo": "68547"}
]
```

**Nota:** Los primeros 2 dígitos del código DIVIPOLA son el departamento (68 = Santander).

#### Tipo Documento Identidad FE
```python
[
  {"codigo": "11", "nombre": "Registro civil"},
  {"codigo": "12", "nombre": "Tarjeta de identidad"},
  {"codigo": "13", "nombre": "Cédula de ciudadanía"},
  {"codigo": "21", "nombre": "Tarjeta de extranjería"},
  {"codigo": "22", "nombre": "Cédula de extranjería"},
  {"codigo": "31", "nombre": "NIT"},
  {"codigo": "41", "nombre": "Pasaporte"},
  {"codigo": "42", "nombre": "Documento de identificación extranjero"},
  {"codigo": "91", "nombre": "NUIP"}
]
```

#### Tributo FE
```python
[
  {"codigo": "01", "nombre": "IVA"},
  {"codigo": "ZZ", "nombre": "No aplica"}
]
```

#### Codigo Impuesto FE
```python
[
  {"codigo": "01", "nombre": "Impuesto sobre las Ventas (IVA)"},
  {"codigo": "04", "nombre": "Impuesto Nacional al Consumo"},
  {"codigo": "35", "nombre": "Impuesto productos ultraprocesados"}
]
```

#### Tipo Medio Pago FE
```python
[
  {"codigo": "10", "nombre": "Efectivo"},
  {"codigo": "20", "nombre": "Cheque"},
  {"codigo": "42", "nombre": "Consignación"},
  {"codigo": "47", "nombre": "Transferencia"},
  {"codigo": "48", "nombre": "Tarjeta Crédito"},
  {"codigo": "49", "nombre": "Tarjeta Débito"},
  {"codigo": "ZZZ", "nombre": "Otro"}
]
```

#### Unidad Medida FE
```python
[
  {"codigo": "94", "nombre": "Unidad"},
  {"codigo": "KGM", "nombre": "Kilogramo"},
  {"codigo": "GRM", "nombre": "Gramo"},
  {"codigo": "LTR", "nombre": "Litro"},
  {"codigo": "MLT", "nombre": "Mililitro"}
]
```

### Paso 4: Configurar API FE (Single DocType)

Ve a: **Configuracion API FE** (buscar en Awesome Bar)

**Campos principales:**

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `ambiente` | Sandbox / Produccion | Sandbox (para pruebas) |
| `url_base_sandbox` | URL API sandbox | https://api-sandbox.factus.com.co |
| `url_base_produccion` | URL API producción | https://api.factus.com.co |
| `timeout` | Timeout requests (seg) | 30 |
| `cliente_consumidor_final` | Link a Customer CCF | Consumidor Final |
| `enviar_email_automatico` | Enviar email PDF | 0 (deshabilitado) |

**Guardar el documento.**

### Paso 5: Crear Dueño Fiscal

Ve a: **Dueno Fiscal** → New

Un "Dueño Fiscal" representa una entidad legal que emite facturas (puede ser la empresa o un establecimiento).

**Datos básicos:**

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `nombre` | Identificador único | Lorena |
| `razon_social` | Razón social completa | TANIA LORENA DURAN RUEDA |
| `nit` | NIT sin guiones ni DV | 1098769003 |
| `dv` | Dígito de verificación | 0 |

**Credenciales Factus:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `client_id` | Password | UUID del cliente OAuth2 |
| `client_secret` | Password | Secret del cliente OAuth2 |
| `username` | Password | Email cuenta Factus |
| `password` | Password | Contraseña cuenta Factus |

**IMPORTANTE:** Los campos tipo "Password" se encriptan automáticamente en ERPNext en la tabla `__Auth`. El sistema usa `get_decrypted_password()` para leerlos.

**Rango de numeración:**

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `numbering_range_id` | ID del rango en Factus | 6141 (sandbox) |

**Ambiente:**

| Campo | Valores | Descripción |
|-------|---------|-------------|
| `ambiente` | Sandbox / Produccion | Hereda de Configuracion API FE si está vacío |

**Guardar.**

**Validar conexión:**

Después de guardar, puedes probar la autenticación ejecutando en consola:

```python
from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI

api = FacturacionElectronicaAPI("Lorena")
token = api.autenticar()
print(f"✓ Token obtenido: {token[:20]}...")
```

---

## Estructura de Datos

### Custom Fields Agregados a DocTypes Estándar

#### Customer

| Campo | Tipo | Label | Descripción |
|-------|------|-------|-------------|
| `requiere_factura_inmediata` | Check | Requiere Factura Inmediata | 1=B2B (envío inmediato), 0=CCF (resumen diario) |
| `fe_identification_document_code` | Link→Tipo Documento Identidad FE | Tipo Doc Identidad FE | Código DIAN (13=CC, 31=NIT, etc.) |
| `fe_numero_documento` | Data | Numero de Documento FE | NIT o cédula sin guiones |
| `fe_dv` | Data | DV FE | Dígito verificación (solo NIT) |
| `fe_tribute_code` | Link→Tributo FE | Tributo FE | Responsabilidad tributaria (01=IVA, ZZ=No aplica) |
| `fe_municipality_code` | Link→Municipio FE | Municipio FE (DIVIPOLA) | Código DIVIPOLA 5 dígitos |

**Configurar en cada cliente:**

- **B2B (Empresas):** Marcar `requiere_factura_inmediata = 1`, llenar NIT, DV, tributo IVA
- **CCF (Consumidor Final):** Dejar desmarcado, documento genérico (ej: 222222222222)

#### Item

| Campo | Tipo | Label | Descripción |
|-------|------|-------|-------------|
| `dueno_fiscal` | Link→Dueno Fiscal | Dueño Fiscal | Asigna el producto a una entidad legal |

**IMPORTANTE:** Todos los items que se vayan a facturar electrónicamente **deben tener** `dueno_fiscal` asignado.

#### Sales Invoice / POS Invoice

| Campo | Tipo | Label | Descripción |
|-------|------|-------|-------------|
| `estado_fe` | Select | Estado FE | Pendiente / Enviada / Validada / Error / No Aplica / Agrupada |
| `cufe_fe` | Data | CUFE FE | Código Único de Factura Electrónica de DIAN |
| `custom_enviar_dian` | Check | Enviar a DIAN | 1=enviar al someter, 0=no enviar |

El campo `estado_fe` sigue este ciclo:

```
Pendiente → Enviada → Validada (éxito)
    ↓
  Error (fallo, se reintenta automáticamente)
```

#### Account (Cuentas de impuesto)

| Campo | Tipo | Label | Descripción |
|-------|------|-------|-------------|
| `fe_tax_code` | Link→Codigo Impuesto FE | Código Impuesto FE | Código DIAN del impuesto (01=IVA) |
| `fe_is_excluded` | Check | Excluido de Impuesto FE | Marcar para productos exentos |

**Configurar en:**
- Cuenta `2408 - Impuesto sobre las ventas por pagar - SM` → `fe_tax_code = "01"`

#### Mode of Payment

| Campo | Tipo | Label | Descripción |
|-------|------|-------|-------------|
| `fe_tipo_medio_pago` | Link→Tipo Medio Pago FE | Tipo Medio Pago FE | Código DIAN medio de pago |

**Configurar:**
- Cash / Efectivo → `fe_tipo_medio_pago = "10"`
- Transfer / Nequi / Daviplata → `fe_tipo_medio_pago = "47"`
- Credit Card → `fe_tipo_medio_pago = "48"`
- Debit Card → `fe_tipo_medio_pago = "49"`

#### UOM (Unidad de Medida)

| Campo | Tipo | Label | Descripción |
|-------|------|-------|-------------|
| `fe_unit_measure_code` | Link→Unidad Medida FE | Código Unidad Medida FE | Código DIAN unidad |

**Configurar:**
- Nos / Unit → `fe_unit_measure_code = "94"`

---

## Flujos de Facturación

### Flujo 1: B2B (Factura Inmediata)

**Cuando:** Cliente empresa con `requiere_factura_inmediata = 1`

**Proceso:**

1. Se crea una Sales Invoice o POS Invoice para el cliente B2B
2. Al hacer Submit:
   - Hook `on_submit` se ejecuta
   - Se valida que todos los items tengan `dueno_fiscal`
   - Se construye el payload JSON
   - Se envía a Factus API `POST /v2/bills/validate`
   - Se crea registro en Log Factura Electronica con estado "Pendiente"
3. Respuesta de Factus:
   - **Éxito:** estado_fe = "Validada", se guarda CUFE, número Factus, URLs
   - **Error:** estado_fe = "Error", se guarda mensaje de error
4. La factura queda con el estado correspondiente

**Código relevante:**

```python
# facturacion_electronica/events/sales_invoice.py
def on_submit_sales_invoice(doc, method=None):
    if not debe_enviar_fe(doc):
        return
    enviar_factura_fe(doc, dueno, items, "Inmediata B2B")
```

### Flujo 2: CCF (Consumidor Final - Resumen Diario)

**Cuando:** Cliente con `requiere_factura_inmediata = 0` (consumidor final)

**Proceso:**

1. Se crean múltiples POS Invoices durante el día
2. Cada factura queda con `estado_fe = "Pendiente"`
3. Al cerrar caja (POS Closing Entry):
   - Hook `before_submit` verifica que no haya facturas FE pendientes
   - Si hay pendientes, **bloquea el cierre** y muestra error
4. Usuario hace clic en botón **"Enviar pendientes a DIAN"** (custom button)
5. Sistema agrupa todas las facturas pendientes por `dueno_fiscal`
6. Para cada dueño fiscal:
   - Se crea **una única factura consolidada** con todos los items del día
   - Se envía a Factus con `reference_code = "CCF-{dueno}-{fecha}"`
   - Las facturas individuales se marcan `estado_fe = "Agrupada"`
7. Cierre de caja queda desbloqueado y se puede someter

**Código relevante:**

```python
# facturacion_electronica/events/pos_closing_entry.py
def before_submit_pos_closing(doc, method=None):
    pendientes = frappe.get_all("POS Invoice", 
        filters={"pos_closing_entry": doc.name, "estado_fe": "Pendiente"})
    if pendientes:
        frappe.throw("Hay facturas pendientes de enviar a DIAN")

# facturacion_electronica/public/js/pos_closing_entry.js
// Botón "Enviar pendientes a DIAN"
```

### Flujo 3: Reintentos Automáticos

**Cuando:** Una factura queda en estado "Error"

**Proceso:**

1. Scheduler ejecuta cada hora: `facturacion_electronica.utils.retry.reintentar_facturas_fallidas`
2. Busca logs con `estado = "Error"` y `intentos < 3`
3. Para cada log:
   - Recupera el payload original
   - Reintenta envío a Factus
   - Incrementa contador de intentos
   - Actualiza estado según respuesta
4. Después de 3 intentos fallidos, el log queda en "Error" permanente

**Configuración del scheduler:**

```python
# hooks.py
scheduler_events = {
    "hourly": [
        "facturacion_electronica.utils.retry.reintentar_facturas_fallidas"
    ]
}
```

---

## Formato de Payload a Factus

### Estructura General

```json
{
  "reference_code": "MANUAL-Lorena-20260808-abc123",
  "document": "01",
  "operation_type": "10",
  "numbering_range_id": 6141,
  "send_email": false,
  "customer": { /* objeto customer */ },
  "items": [ /* array de items */ ],
  "payment_details": [ /* array de pagos */ ],
  "cash_rounding_amount": "0.00",
  "observation": "Factura consolidada día 2026-08-08"
}
```

### Objeto Customer (Formato Correcto para FAK08)

**IMPORTANTE:** La DIAN requiere formato estructurado para evitar warning FAK08.

```json
{
  "identification_document_code": "31",
  "identification": "1098769003",
  "dv": "0",
  "legal_organization_code": "1",
  "company": "TANIA LORENA DURAN RUEDA",
  "trade_name": "SALSAMENTARIA MULTIESPECIAL",
  "tribute_code": "01",
  "email": "salsamentariamultiespecial@gmail.com",
  "phone": "3001234567",
  "municipality_code": "68406",
  "address": {
    "id": "CL 20 19 02",
    "city_name": "Girón",
    "country_subentity": "Santander",
    "country_subentity_code": "68",
    "address_line": {
      "line": "CL 20 19 02 BRR PORTAL CAMPESTRE GIRON"
    },
    "country": {
      "identification_code": "CO"
    }
  }
}
```

**Campos requeridos para FAK08:**

- `id` — Identificador corto de dirección (primeros 20 chars)
- `city_name` — Nombre ciudad (del campo `city` en Address)
- `country_subentity` — Nombre departamento (del campo `state` en Address)
- `country_subentity_code` — Código departamento DIVIPOLA (2 dígitos, extraídos del código municipio)
- `address_line.line` — Dirección completa (address_line1 + address_line2)
- `country.identification_code` — Siempre "CO" para Colombia

**Código de extracción:**

```python
# Extraer código departamento de DIVIPOLA
muni_codigo = "68406"  # Girón
dept_code = muni_codigo[:2]  # "68" = Santander
```

### Items Array

```json
[
  {
    "name": "Arroz Diana x 500g",
    "product_key": "ARR-500",
    "unit_measure_code": "94",
    "quantity": "10",
    "net_unit_value": "3500.00",
    "discount_percent": "0.00",
    "taxes": [
      {
        "tax_code": "01",
        "tax_name": "IVA",
        "tax_percent": "19.00",
        "tax_amount": "6650.00"
      }
    ]
  }
]
```

**Cálculo de impuestos:**

```
net_unit_value = precio base sin impuestos
subtotal = net_unit_value * quantity
base_imponible = subtotal * (1 - discount_percent/100)
tax_amount = base_imponible * (tax_percent/100)
total_item = base_imponible + tax_amount
```

### Payment Details Array

```json
[
  {
    "payment_form": "1",
    "payment_method_code": "10",
    "amount": "41650.00"
  }
]
```

**Códigos:**

- `payment_form` — Siempre "1" (contado) o "2" (crédito)
- `payment_method_code` — Ver tabla Tipo Medio Pago FE

---

## Ambientes: Sandbox vs Producción

### Diferencias Clave

| Aspecto | Sandbox | Producción |
|---------|---------|------------|
| **URL Base** | api-sandbox.factus.com.co | api.factus.com.co |
| **Dashboard** | app-sandbox.factus.com.co | app.factus.com.co |
| **Certificado DIAN** | No requerido | **Requerido** |
| **Rangos numeración** | Pre-configurados (genéricos) | Debes crearlos con resolución DIAN |
| **Facturas a DIAN** | No se envían | Sí se envían |
| **CUFE** | Válido solo para pruebas | Válido oficialmente |
| **Costo** | Gratuito | Según plan Factus |

### Cambiar de Sandbox a Producción

**Paso 1:** Actualizar Configuracion API FE

```
Ambiente: Produccion
```

**Paso 2:** Actualizar credenciales en Dueno Fiscal

- `client_id` → Credencial de producción
- `client_secret` → Credencial de producción
- `username` → Email cuenta producción
- `password` → Password cuenta producción

**Paso 3:** Instalar certificado digital en Factus

Esto se hace desde el dashboard de Factus:

1. Login a https://app.factus.com.co
2. Configuración → Certificados
3. Subir certificado `.p12` emitido por DIAN
4. Ingresar contraseña del certificado
5. Validar

**Paso 4:** Crear rango de numeración con resolución DIAN

Ver sección [Rangos de Numeración](#rangos-de-numeración).

**Paso 5:** Clear cache y restart

```bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site salsamentariamultiespecial.duckdns.org clear-cache'

# Restart containers
P=vvekd3jmyymltrmfoi8vdbdu
for svc in backend queue-default queue-short queue-long; do
  docker restart $(docker ps -q --filter "name=$svc-$P" | head -1)
done
```

**Paso 6:** Probar con una factura de prueba

Crear una factura de bajo monto y verificar:
- Estado pasa a "Validada"
- Se obtiene CUFE
- PDF descargable desde Factus
- Factura aparece en RADIAN (portal DIAN)

---

## Rangos de Numeración

### ¿Qué es un Rango de Numeración?

Es la autorización de la DIAN para emitir facturas con un prefijo y consecutivo específico.

**Ejemplo de resolución DIAN:**

```
Número de Resolución: 18764116394463
Prefijo: SM
Desde: 1
Hasta: 2000
Vigencia: 24 meses
Fecha inicio: 2026-09-29
Fecha vencimiento: 2028-09-29
```

### Rangos en Sandbox

Factus sandbox viene con rangos pre-configurados genéricos:

| ID | Prefijo | Documento | Rango |
|----|---------|-----------|-------|
| 6141 | SETP | Factura de Venta | 990000000 - 995000000 |
| 6142 | NC | Nota Crédito | 0 - 16000000 |
| 6143 | ND | Nota Débito | 0 - 16000000 |
| 6144 | SEDS | Documento Soporte | 984000000 - 985000000 |
| 6145 | NA | Nota Ajuste Doc Soporte | 0 - 16000000 |

**Usar en sandbox:**

```python
frappe.db.set_value('Dueno Fiscal', 'Lorena', 'numbering_range_id', 6141)
frappe.db.commit()
```

### Crear Rango en Producción

**Requisitos previos:**
- Certificado digital DIAN instalado en Factus
- Resolución DIAN vigente
- Credenciales de producción

**Endpoint:**

```http
POST https://api.factus.com.co/v2/numbering-ranges
Authorization: Bearer {token}
Content-Type: application/json

{
  "document": "21",
  "prefix": "SM",
  "resolution_number": "18764116394463",
  "from": 1,
  "to": 2000,
  "current": 1,
  "start_date": "2026-09-29",
  "end_date": "2028-09-29"
}
```

**Códigos de documento para rangos:**

- `21` — Factura de Venta
- `22` — Nota Crédito
- `23` — Nota Débito
- `24` — Documento Soporte
- `25` — Nota de Ajuste Documento Soporte

**Respuesta exitosa:**

```json
{
  "status": "OK",
  "message": "Rango creado exitosamente",
  "data": {
    "id": 8234,
    "document": "21",
    "document_name": "Factura de Venta",
    "prefix": "SM",
    "from": 1,
    "to": 2000,
    "current": 1,
    "resolution_number": "18764116394463",
    "start_date": "2026-09-29",
    "end_date": "2028-09-29",
    "is_active": true,
    "is_expired": false
  }
}
```

**Actualizar en ERPNext:**

```python
frappe.db.set_value('Dueno Fiscal', 'Lorena', 'numbering_range_id', 8234)
frappe.db.commit()
```

### Consultar Rangos Existentes

```http
GET https://api.factus.com.co/v2/numbering-ranges
Authorization: Bearer {token}
```

**Ejemplo con PowerShell:**

```powershell
# 1. Autenticar
$auth = @{
    'grant_type' = 'password'
    'client_id' = 'tu-client-id'
    'client_secret' = 'tu-secret'
    'username' = 'tu@email.com'
    'password' = 'tu-password'
}
$tokenResp = Invoke-RestMethod -Uri "https://api.factus.com.co/oauth/token" `
    -Method Post -Body $auth

$token = $tokenResp.access_token

# 2. Consultar rangos
$headers = @{ 'Authorization' = "Bearer $token" }
$rangos = Invoke-RestMethod -Uri "https://api.factus.com.co/v2/numbering-ranges" `
    -Headers $headers

$rangos.data.data | Format-Table id, prefix, document_name, current, is_active
```

---

## Resolución de Problemas Comunes

### Problema 1: "Invalid credentials" al autenticar

**Síntoma:**
```
POST /oauth/token → 401 Unauthorized
{
  "error": "invalid_credentials",
  "message": "The user credentials were incorrect."
}
```

**Causas posibles:**

1. **Username no se está desencriptando**

El campo `username` en Dueno Fiscal es tipo Password, pero ERPNext solo encripta automáticamente campos que terminen en `_password` o `_secret`.

**Solución:** Verificar que `get_credenciales()` use `get_decrypted_password()`:

```python
# facturacion_electronica/doctype/dueno_fiscal/dueno_fiscal.py
def get_credenciales(dueno_fiscal):
    dueno = frappe.get_cached_doc("Dueno Fiscal", dueno_fiscal)
    
    # CORRECTO: Desencriptar todos los campos Password
    username = get_decrypted_password("Dueno Fiscal", dueno.name, "username", raise_exception=False) or dueno.username or ""
    password = get_decrypted_password("Dueno Fiscal", dueno.name, "password", raise_exception=False) or dueno.password or ""
    client_id = get_decrypted_password("Dueno Fiscal", dueno.name, "client_id", raise_exception=False) or dueno.client_id or ""
    client_secret = get_decrypted_password("Dueno Fiscal", dueno.name, "client_secret", raise_exception=False) or dueno.client_secret or ""
    
    return {
        "username": username,
        "password": password,
        "client_id": client_id,
        "client_secret": client_secret
    }
```

2. **Credenciales incorrectas**

Validar con curl:

```bash
curl -X POST "https://api-sandbox.factus.com.co/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=a2e0cdc1-ad28-4659-bb0c-6b0b72b8eeb8" \
  -d "client_secret=irQBN5wSWIVKA4Lo0aui2vgHzqNQS3XDwqUaiLUu" \
  -d "username=salsamentariamultiespecial@gmail.com" \
  -d "password=iYTGTy2m"
```

Si curl funciona pero Python falla, el problema es la desencriptación.

### Problema 2: "El campo id rango de numeración es inválido"

**Síntoma:**
```json
{
  "status": "Validation error",
  "data": {
    "errors": {
      "numbering_range_id": ["El campo id rango de numeración es inválido."]
    }
  }
}
```

**Causa:** El `numbering_range_id` no existe en tu cuenta Factus.

**Solución:**

1. Consultar rangos disponibles:
```python
from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI
api = FacturacionElectronicaAPI("Lorena")
token = api.autenticar()

import requests
resp = requests.get(
    f"{api.base_url}/v2/numbering-ranges",
    headers={"Authorization": f"Bearer {token}"}
)
print(resp.json())
```

2. Usar un ID válido de la respuesta

3. Actualizar:
```python
frappe.db.set_value('Dueno Fiscal', 'Lorena', 'numbering_range_id', 6141)
frappe.db.commit()
```

### Problema 3: "Items sin dueno_fiscal"

**Síntoma:**
```
ValidationError: Los siguientes items no tienen Dueño Fiscal asignado: ['PROD-001', 'PROD-002']
```

**Causa:** Items en la factura no tienen el campo `dueno_fiscal` configurado.

**Solución:**

1. **Asignar masivamente vía SQL:**

```sql
UPDATE `tabItem`
SET dueno_fiscal = 'Lorena'
WHERE disabled = 0;
```

2. **O via Python:**

```python
items = frappe.get_all("Item", filters={"disabled": 0})
for item in items:
    frappe.db.set_value("Item", item.name, "dueno_fiscal", "Lorena")
frappe.db.commit()
```

### Problema 4: Warning FAK08 en respuesta DIAN

**Síntoma:**
```json
{
  "FAK08": "Regla: FAK08, Notificación: El grupo deberá estar conformado al menos por el conjunto de elementos ID, CityName, CountrySubentity..."
}
```

**Causa:** La dirección se envía como string simple en lugar de objeto estructurado.

**Solución:** Ya implementada en el código. Verifica que `_get_customer_obj()` construya el objeto así:

```python
obj["address"] = {
    "id": addr_data.get("address")[:20],
    "city_name": addr_data.get("city") or "N/A",
    "country_subentity": addr_data.get("state") or "N/A",
    "country_subentity_code": dept_code or "N/A",
    "address_line": {
        "line": addr_data.get("address")
    },
    "country": {
        "identification_code": "CO"
    }
}
```

### Problema 5: "No se puede cerrar caja, hay facturas FE pendientes"

**Síntoma:** Al intentar someter POS Closing Entry, se bloquea con error.

**Causa:** Hay POS Invoices con `estado_fe = "Pendiente"` que no se han enviado a DIAN.

**Solución:**

1. Hacer clic en botón **"Enviar pendientes a DIAN"** en el POS Closing Entry
2. Esperar a que todas cambien a "Agrupada" o "Validada"
3. Reintentar Submit del cierre

**Si el botón no aparece:** Verificar que el JS custom esté cargado:

```javascript
// public/js/pos_closing_entry.js
frappe.ui.form.on('POS Closing Entry', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Enviar pendientes a DIAN'), function() {
                // código del botón
            });
        }
    }
});
```

---

## Compliance DIAN (FAK08)

### ¿Qué es FAK08?

FAK08 es una regla de validación de la DIAN que exige formato estructurado completo para direcciones en facturas electrónicas.

**Formato requerido:**

```json
{
  "address": {
    "id": "identificador_direccion",
    "city_name": "Nombre Ciudad",
    "country_subentity": "Nombre Departamento",
    "country_subentity_code": "Código Departamento",
    "address_line": {
      "line": "Dirección completa"
    },
    "country": {
      "identification_code": "CO"
    }
  }
}
```

### Implementación en ERPNext

**Datos necesarios:**

1. **Address (DocType estándar):**
   - `address_line1` + `address_line2` → `address_line.line`
   - `city` → `city_name`
   - `state` → `country_subentity`
   - `country` → Siempre "CO"

2. **Customer (Custom Field):**
   - `fe_municipality_code` (Link→Municipio FE) → `municipality_code`
   - Del código DIVIPOLA extraer primeros 2 dígitos → `country_subentity_code`

**Ejemplo:**

```
Municipio FE: Girón (código DIVIPOLA: 68406)
Departamento: 68 (Santander)

Address:
  address_line1: CL 20 19 02
  address_line2: BRR PORTAL CAMPESTRE
  city: Girón
  state: Santander
  country: Colombia

Resultado JSON:
{
  "id": "CL 20 19 02",
  "city_name": "Girón",
  "country_subentity": "Santander",
  "country_subentity_code": "68",
  "address_line": {
    "line": "CL 20 19 02 BRR PORTAL CAMPESTRE"
  },
  "country": {
    "identification_code": "CO"
  }
}
```

### Código Implementado

```python
# facturacion_electronica/utils/api_fe.py

def _get_customer_address(cust):
    # ... obtener Address doc ...
    return {
        "address": addr,
        "phone": a.phone or "",
        "email": a.email_id or "",
        "city": a.city or "",
        "state": a.state or "",
        "country": a.country or "Colombia"
    }

def _get_customer_obj(customer):
    # ...
    addr_data = _get_customer_address(cust)
    
    if addr_data and addr_data.get("address"):
        muni_codigo = _fe_codigo("Municipio FE", cust.get("fe_municipality_code"))
        dept_code = muni_codigo[:2] if muni_codigo and len(muni_codigo) >= 5 else ""
        
        obj["address"] = {
            "id": addr_data.get("address")[:20],
            "city_name": addr_data.get("city") or "N/A",
            "country_subentity": addr_data.get("state") or "N/A",
            "country_subentity_code": dept_code or "N/A",
            "address_line": {
                "line": addr_data.get("address")
            },
            "country": {
                "identification_code": "CO"
            }
        }
```

**Validación:**

Después de implementar, generar una factura de prueba y verificar en el Log Factura Electronica campo `errores` que no aparezca FAK08.

---

## Testing y Validación

### Test 1: Autenticación

```python
from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI

api = FacturacionElectronicaAPI("Lorena")
token = api.autenticar()

if token:
    print(f"✓ Autenticación exitosa: {token[:20]}...")
else:
    print("✗ Error de autenticación")
```

### Test 2: Consultar Rangos

```python
import requests
from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI

api = FacturacionElectronicaAPI("Lorena")
token = api.autenticar()

resp = requests.get(
    f"{api.base_url}/v2/numbering-ranges",
    headers={"Authorization": f"Bearer {token}"}
)

print(resp.json())
```

### Test 3: Factura de Prueba (Payload Manual)

```python
from facturacion_electronica.utils.api_fe import FacturacionElectronicaAPI

api = FacturacionElectronicaAPI("Lorena")

payload = {
    "reference_code": "TEST-001",
    "document": "01",
    "operation_type": "10",
    "numbering_range_id": 6141,
    "send_email": False,
    "customer": {
        "identification_document_code": "13",
        "identification": "222222222222",
        "legal_organization_code": "2",
        "names": "Cliente Prueba",
        "tribute_code": "ZZ",
        "email": "test@example.com",
        "municipality_code": "68406"
    },
    "items": [{
        "name": "Producto Prueba",
        "product_key": "TEST-001",
        "unit_measure_code": "94",
        "quantity": "1",
        "net_unit_value": "1000.00",
        "discount_percent": "0.00",
        "taxes": [{
            "tax_code": "01",
            "tax_name": "IVA",
            "tax_percent": "19.00",
            "tax_amount": "190.00"
        }]
    }],
    "payment_details": [{
        "payment_form": "1",
        "payment_method_code": "10",
        "amount": "1190.00"
    }],
    "cash_rounding_amount": "0.00"
}

resp = api.emitir_factura(payload)
print(resp)
```

### Test 4: Factura Real desde ERPNext

1. Crear cliente de prueba:
   - Customer Type: Individual
   - `requiere_factura_inmediata` = 1
   - `fe_identification_document_code` = CC (13)
   - `fe_numero_documento` = 1234567890
   - `fe_tribute_code` = No aplica (ZZ)
   - `fe_municipality_code` = Girón (68406)

2. Crear item de prueba:
   - Item Code: TEST-ITEM-001
   - Item Name: Producto Test
   - `dueno_fiscal` = Lorena
   - Rate: 1000
   - Default Tax Template: Colombia Tax - SM (19%)

3. Crear Sales Invoice:
   - Customer: Cliente de prueba
   - Item: TEST-ITEM-001
   - Qty: 1
   - Guardar y Submit

4. Verificar:
   - `estado_fe` debe cambiar a "Validada"
   - `cufe_fe` debe tener valor
   - Log Factura Electronica creado

5. Revisar log:
   ```python
   log = frappe.get_last_doc("Log Factura Electronica")
   print(log.estado)
   print(log.cufe)
   print(log.numero_factus)
   ```

### Test 5: Batch de Facturas (Agosto)

```python
from facturacion_electronica.utils.batch_agosto import generar_facturas_agosto_sandbox

# Dry run (solo mostrar plan)
result = generar_facturas_agosto_sandbox(
    dueno_fiscal="Lorena",
    limite=5,
    dry_run=True
)
print(result)

# Generar 2 facturas reales
result = generar_facturas_agosto_sandbox(
    dueno_fiscal="Lorena",
    limite=2,
    dry_run=False
)
print(result)
```

---

## Despliegue de Cambios

### Flujo Completo

```bash
# 1. Desarrollo local
cd /ruta/a/facturacion-electronica
# ... hacer cambios en código ...
git add -A
git commit -m "descripción del cambio"
git push origin master

# 2. SSH al servidor
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129

# 3. Reconstruir imagen Docker custom
cd /root/fe-image
docker build -t erpnext-fe:v16.25.0 .
docker tag erpnext-fe:v16.25.0 frappe/erpnext:v16.25.0

# 4. Reiniciar contenedores
P=vvekd3jmyymltrmfoi8vdbdu
for svc in backend scheduler queue-default queue-short queue-long frontend websocket; do
  cid=$(docker ps -q --filter "name=$svc-$P" | head -1)
  [ -n "$cid" ] && docker restart "$cid"
done

# 5. Migrar (si hay cambios en DocTypes)
BC=$(docker ps -q --filter "name=backend-$P" | head -1)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site salsamentariamultiespecial.duckdns.org migrate'

# 6. Clear cache
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site salsamentariamultiespecial.duckdns.org clear-cache'
```

### Verificar Despliegue

```bash
# Ver logs del backend
docker logs --tail 50 $(docker ps -q --filter "name=backend-$P" | head -1)

# Verificar que la app esté instalada
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site salsamentariamultiespecial.duckdns.org list-apps'

# Debe mostrar: frappe, erpnext, facturacion_electronica
```

### Rollback

Si algo falla:

```bash
# 1. Volver al commit anterior en Git
cd /ruta/local/facturacion-electronica
git log --oneline  # ver commits
git checkout <commit_hash>
git push -f origin master

# 2. Reconstruir imagen con código anterior
# (repetir pasos 2-6 de "Flujo Completo")
```

---

## Mantenimiento

### Logs a Monitorear

1. **Log Factura Electronica**
   - Filtrar por `estado = "Error"`
   - Revisar campo `errores` para diagnosticar

2. **Error Log de ERPNext**
   - https://salsamentariamultiespecial.duckdns.org/app/error-log
   - Filtrar por: `facturacion_electronica`

3. **Docker Logs**
   ```bash
   # Backend
   docker logs --tail 100 -f $(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu")
   
   # Queue workers
   docker logs --tail 100 -f $(docker ps -q --filter "name=queue-default-vvekd3jmyymltrmfoi8vdbdu")
   ```

### Tareas Periódicas

#### Mensual

- Verificar que no haya facturas en estado "Error" acumuladas
- Revisar consumo de rangos de numeración
- Validar certificado digital (fecha vencimiento)

#### Trimestral

- Actualizar catálogos DIAN si hay cambios (municipios, impuestos)
- Revisar versión de Factus API (cambios en endpoints)

#### Anual

- Renovar certificado digital DIAN antes de vencimiento
- Solicitar nueva resolución de numeración a DIAN si se agota el rango
- Actualizar versión de ERPNext si hay mejoras relevantes

### Backup de Configuración

**Exportar configuración:**

```bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Backup completo del sitio
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && \
  bench --site salsamentariamultiespecial.duckdns.org backup --with-files'

# Copiar backup fuera del contenedor
docker cp $BC:/home/frappe/frappe-bench/sites/salsamentariamultiespecial.duckdns.org/private/backups/ \
  /root/fe-backups/backup_$(date +%Y%m%d)/
```

**Exportar solo configuración FE:**

```python
import frappe
import json

# Configuracion API FE
config = frappe.get_single("Configuracion API FE")
with open("config_fe_backup.json", "w") as f:
    json.dump(config.as_dict(), f, indent=2)

# Duenos Fiscales (sin credenciales por seguridad)
duenos = frappe.get_all("Dueno Fiscal", fields=["*"])
with open("duenos_fiscales_backup.json", "w") as f:
    json.dump(duenos, f, indent=2)

# Catálogos
for doctype in ["Municipio FE", "Tributo FE", "Codigo Impuesto FE", 
                "Tipo Documento Identidad FE", "Tipo Medio Pago FE", "Unidad Medida FE"]:
    data = frappe.get_all(doctype, fields=["*"])
    filename = f"{doctype.lower().replace(' ', '_')}_backup.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

### Migración a Otro Servidor

1. **Instalar ERPNext en servidor nuevo**
2. **Clonar repo de la app:**
   ```bash
   bench get-app https://github.com/johssalinas/facturacion-electronica
   bench --site <site> install-app facturacion_electronica
   ```
3. **Restaurar backup:**
   ```bash
   bench --site <site> restore /path/to/backup.sql.gz
   ```
4. **Reconfigurar credenciales Factus** (no se migran por seguridad)
5. **Probar con factura de prueba**

---

## Anexos

### A. Códigos DIAN Completos

#### Departamentos Colombia (primeros 2 dígitos DIVIPOLA)

| Código | Departamento |
|--------|--------------|
| 05 | Antioquia |
| 08 | Atlántico |
| 11 | Bogotá D.C. |
| 13 | Bolívar |
| 15 | Boyacá |
| 17 | Caldas |
| 18 | Caquetá |
| 19 | Cauca |
| 20 | Cesar |
| 23 | Córdoba |
| 25 | Cundinamarca |
| 27 | Chocó |
| 41 | Huila |
| 44 | La Guajira |
| 47 | Magdalena |
| 50 | Meta |
| 52 | Nariño |
| 54 | Norte de Santander |
| 63 | Quindío |
| 66 | Risaralda |
| 68 | Santander |
| 70 | Sucre |
| 73 | Tolima |
| 76 | Valle del Cauca |
| 81 | Arauca |
| 85 | Casanare |
| 86 | Putumayo |
| 88 | San Andrés y Providencia |
| 91 | Amazonas |
| 94 | Guainía |
| 95 | Guaviare |
| 97 | Vaupés |
| 99 | Vichada |

### B. Checklist Pre-Producción

- [ ] Certificado digital DIAN instalado en Factus
- [ ] Resolución de numeración vigente
- [ ] Rango de numeración creado en Factus (producción)
- [ ] `numbering_range_id` actualizado en Dueno Fiscal
- [ ] Credenciales de producción configuradas
- [ ] Ambiente cambiado a "Produccion"
- [ ] Todos los items tienen `dueno_fiscal` asignado
- [ ] Accounts de impuesto tienen `fe_tax_code` configurado
- [ ] Modes of Payment tienen `fe_tipo_medio_pago` configurado
- [ ] Cliente Consumidor Final configurado
- [ ] Factura de prueba exitosa en producción
- [ ] Backup completo del sistema
- [ ] Documentación entregada al cliente
- [ ] Capacitación a usuarios finales

### C. Contactos de Soporte

**Factus:**
- Soporte técnico: soporte@factus.com.co
- Dashboard: https://app.factus.com.co
- Documentación: https://developers.factus.com.co

**DIAN:**
- Portal facturación electrónica: https://www.dian.gov.co
- Mesa de ayuda: 057 605 3990
- RADIAN (consulta facturas): https://catalogo-vpfe.dian.gov.co

**ERPNext:**
- Foro comunidad: https://discuss.frappe.io
- GitHub: https://github.com/frappe/erpnext

---

## Historial de Cambios

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-09-29 | 1.0 | Documento inicial - Integración completa con Factus |
| 2026-09-29 | 1.1 | Agregado fix FAK08 (formato estructurado de dirección) |

---

**Fin del documento.**
