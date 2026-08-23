# Salsamentaria Multiespecial — Documentación Completa del Proyecto

## 1. Credenciales y Accesos

### 1.1 Servidor Hetzner (SSH)
- **IP:** 46.225.227.129
- **Usuario:** root
- **SSH Key:** `~/.ssh/id_ed25519_hetzner`
- **Comando de conexión:**
  ```bash
  ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129
  ```

### 1.2 Coolify
- **URL:** http://46.225.227.129:8000 (accesible desde el navegador)
- **API Token:** `6|pWgM0C9LUAorBNFErd7CUFL9LBMaQosdKz67dGmread6523b`
- **Application UUID:** `vvekd3jmyymltrmfoi8vdbdu`
- **Deploy via API:**
  ```bash
  # Cambiar variable de entorno
  curl -X PATCH -H "Authorization: Bearer 2|WCIlYtdQc0gq8TexAtkPRmWZX6lYc0GwDJlBG3Nl89ba61fd" \
    -H "Content-Type: application/json" \
    -d '{"key":"FRAPPE_VERSION","value":"v16.25.0","is_buildtime":true,"is_preview":false}' \
    "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/envs"

  # Disparar redeploy
  curl -X POST -H "Authorization: Bearer 2|WCIlYtdQc0gq8TexAtkPRmWZX6lYc0GwDJlBG3Nl89ba61fd" \
    "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/start"
  ```

### 1.3 ERPNext — Usuarios y Contraseñas
| Rol | Email | Contraseña | Descripción |
|---|---|---|---|
| Superadmin | johssalinas2work@gmail.com | F..b3QwfYk | Acceso total, todos los roles |
| Contadora | andrea@gmail.com | Andrea.123456 | Contabilidad, inventario, compras, ventas, FE |
| Admin tienda | lorena@gmail.com | Lorena.123456 | Ventas, compras, almacén, reportes, POS |
| Cajera | sharith@gmail.com | Sharith.123456 | Solo vender desde POS |

### 1.4 URL del sitio
- **Producción:** https://salsamentariamultiespecial.duckdns.org
- **Login:** POST a `/api/method/login` con `usr` y `pwd`

### 1.5 GitHub
- **Repo app FE:** https://github.com/johssalinas/facturacion-electronica
- **Remote SSH:** `git@github.com-personal:johssalinas/facturacion-electronica.git`
- **Repo deploy (compose):** https://github.com/johssalinas/salsamentaria-multiespecial (privado, gestión via Coolify)
- **Branch:** master

### 1.6 Factus API (Facturación Electrónica)
- **Ambiente actual:** Sandbox
- **URL Sandbox:** https://api-sandbox.factus.com.co
- **URL Producción:** https://api.factus.com.co
- **Dueño Fiscal:** "Lorena" (NIT: 1098769003)
- **Estado credenciales:** INCOMPLETAS — falta client_id, client_secret, username, password, numbering_range_id

### 1.7 Base de datos MariaDB
- **Root password:** I3CcGBT7iS36t^AK
- **Admin password ERPNext:** 9B6DOOv@LYwRg*#6
- **Host:** db container (docker network)
- **Database:** salsamentariamultiespecial_duckdns_org

---

## 2. Arquitectura del Proyecto

### 2.1 Visión General
ERPNext 16.25.0 (Frappe 16.24.0) desplegado con Coolify 4.1.2 sobre un servidor Hetzner. Se utiliza una **imagen Docker custom** (`erpnext-fe:v16.25.0`) que incluye la app `facturacion_electronica` horneada, para que sobreviva a redeploys sin necesidad de reinstalación manual.

### 2.2 Stack Tecnológico
| Componente | Versión | Propósito |
|---|---|---|
| Frappe Framework | 16.24.0 | Framework base |
| ERPNext | 16.25.0 | ERP |
| MariaDB | 11.8 | Base de datos |
| Redis | 6.2-alpine | Cache, queue, socketio |
| Coolify | 4.1.2 | Orquestador/Deploy |
| Traefik | v3.6 | Reverse proxy + TLS |
| Docker | 29.5.3 | Container runtime |
| Node.js | v24.12.0 | Build de assets (nvm) |
| Python | 3.14 | Runtime frappe |

### 2.3 Contenedores (12 servicios ERPNext + 6 Coolify)
**ERPNext (prefijo `vvekd3jmyymltrmfoi8vdbdu`):**
- `backend` — Gunicorn, sirve la API
- `frontend` — Nginx, sirve assets y proxy al backend
- `configurator` — Configura el site al arrancar
- `scheduler` — Cron de Frappe
- `queue-default` — Worker cola default
- `queue-short` — Worker cola short
- `queue-long` — Worker cola long
- `websocket` — Socket.io
- `db` — MariaDB 11.8
- `redis-cache` — Cache
- `redis-queue` — Queue
- `redis-socketio` — Socketio

**Coolify:**
- `coolify` — Panel principal
- `coolify-db` — PostgreSQL (DB de Coolify)
- `coolify-redis` — Redis de Coolify
- `coolify-proxy` — Traefik v3.6
- `coolify-sentinel` — Monitoreo
- `coolify-realtime` — Websockets de Coolify

### 2.4 Volúmenes Docker Persistentes
| Volumen | Contenido | Sobrevive redeploy |
|---|---|---|
| `vvekd3jmyymltrmfoi8vdbdu_sites` | Sitios, DB config, assets compilados, uploads | **SÍ** |
| `vvekd3jmyymltrmfoi8vdbdu_logs` | Logs de Frappe | **SÍ** |
| `vvekd3jmyymltrmfoi8vdbdu_db-data` | Datos MariaDB | **SÍ** |
| `vvekd3jmyymltrmfoi8vdbdu_redis-*` | Datos Redis | **SÍ** |

> **IMPORTANTE:** El directorio `apps/` NO está en un volumen. Está dentro de la imagen Docker. Por eso se usa una imagen custom con la app horneada.

### 2.5 Dockerfile Custom
**Ubicación en el servidor:** `/root/fe-image/Dockerfile`
**Ubicación del script compile_po.py:** `/root/fe-image/compile_po.py`

```dockerfile
FROM frappe/erpnext:v16.25.0
USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:frappe compile_po.py /tmp/compile_po.py
RUN rm -rf apps/facturacion_electronica \
    && git clone --depth 1 https://github.com/johssalinas/facturacion-electronica apps/facturacion_electronica \
    && env/bin/pip install --no-cache-dir -e apps/facturacion_electronica
RUN mkdir -p apps/frappe/frappe/locale apps/erpnext/erpnext/locale \
    && curl -sL https://raw.githubusercontent.com/frappe/frappe/v16.24.0/frappe/locale/es.po -o apps/frappe/frappe/locale/es.po \
    && curl -sL https://raw.githubusercontent.com/frappe/frappe/v16.24.0/frappe/locale/main.pot -o apps/frappe/frappe/locale/main.pot \
    && curl -sL https://raw.githubusercontent.com/frappe/erpnext/v16.25.0/erpnext/locale/es.po -o apps/erpnext/erpnext/locale/es.po \
    && curl -sL https://raw.githubusercontent.com/frappe/erpnext/v16.25.0/erpnext/locale/main.pot -o apps/erpnext/erpnext/locale/main.pot
RUN env/bin/python /tmp/compile_po.py
```

> **NOTA:** NO se ejecuta `bench build` en el Dockerfile porque rompe los assets CSS/JS (el `assets.json` se desincroniza con los hashes de los archivos). Las traducciones .po se compilan manualmente con `compile_po.py` (babel) sin tocar los assets.

### 2.6 Script de Actualización
**Ubicación en el servidor:** `/root/fe-update-image.sh`

Uso:
```bash
/root/fe-update-image.sh v16.25.0
```
Este script:
1. Actualiza el Dockerfile FROM
2. Construye la imagen `erpnext-fe:v16.25.0`
3. La reetiqueta como `frappe/erpnext:v16.25.0` (reemplaza la stock localmente)
4. Da instrucciones para actualizar FRAPPE_VERSION en Coolify y hacer redeploy

---

## 3. App Custom: facturacion_electronica

### 3.1 Propósito
Integración con **Factus API** para facturación electrónica colombiana (DIAN). Soporta:
- **B2B Inmediata:** Cliente empresa → factura enviada a DIAN al someter
- **CCF Resumen Diario:** Consumidor final → facturas agrupadas al cerrar caja

### 3.2 Doctypes Custom
| Doctype | Tipo | Propósito |
|---|---|---|
| Configuracion API FE | Single | Config global (sandbox/producción, timeouts, defaults) |
| Dueno Fiscal | Normal | Entidad legal con credenciales Factus (NIT, DV, rango numeración) |
| Log Factura Electronica | Document | Registro de cada envío a DIAN (payload, respuesta, CUFE, errores) |
| Tipo Documento Identidad FE | Normal | Catálogo DIAN (CC=13, NIT=31, etc.) |
| Tributo FE | Normal | Catálogo DIAN (IVA=01, No Aplica=ZZ) |
| Municipio FE | Normal | Catálogo DIVIPOLA |
| Codigo Impuesto FE | Normal | Catálogo DIAN (IVA=01, INC=04, Ultraprocesados=35) |
| Unidad Medida FE | Normal | Catálogo DIAN (Unidad=94, KGM, LBR, etc.) |
| Tipo Medio Pago FE | Normal | Catálogo DIAN (Efectivo=10, Transferencia=47, etc.) |

### 3.3 Custom Fields en Doctypes Estándar
| Doctype | Campo | Tipo | Propósito |
|---|---|---|---|
| Item | dueno_fiscal | Link→Dueno Fiscal | Asigna producto a entidad legal |
| Account | fe_tax_code | Link→Codigo Impuesto FE | Mapeo impuesto DIAN |
| Account | fe_is_excluded | Check | Excluido de impuesto |
| UOM | fe_unit_measure_code | Link→Unidad Medida FE | Mapeo unidad DIAN |
| Customer | requiere_factura_inmediata | Check | B2B (marcado) vs CCF (desmarcado) |
| Customer | fe_numero_documento | Data | Número de documento |
| Customer | fe_identification_document_code | Link→Tipo Doc Identidad FE | Tipo de documento |
| Customer | fe_dv | Data | Dígito de verificación |
| Customer | fe_tribute_code | Link→Tributo FE | Responsabilidad tributaria |
| Customer | fe_municipality_code | Link→Municipio FE | Municipio DIVIPOLA |
| Sales Invoice | estado_fe | Select | Pendiente/Enviada/Validada/Error/No Aplica/Agrupada |
| Sales Invoice | cufe_fe | Data | CUFE de DIAN |
| Sales Invoice | custom_enviar_dian | Check | Enviar a DIAN al someter |
| POS Invoice | (mismos campos que Sales Invoice) | | |
| Mode of Payment | fe_tipo_medio_pago | Link→Tipo Medio Pago FE | Mapeo medio de pago DIAN |

### 3.4 Hooks Principales
- `on_submit` de Sales Invoice → envía a DIAN si `custom_enviar_dian=1`
- `on_submit` de POS Invoice (override class) → envía a DIAN si cliente B2B
- `before_submit` de POS Closing Entry → bloquea cierre si hay facturas FE pendientes
- `on_cancel` de POS Invoice → avisa que se necesita nota crédito electrónica
- `scheduler_events.hourly` → reintenta facturas fallidas (máx 3 intentos)
- `on_login` → redirige cajera/admin/contadora a `/desk/desktop`
- `boot_session` → agrega `desktop_redirect` al boot data

### 3.5 Flujo de Facturación Electrónica

**B2B (Cliente empresa, requiere_factura_inmediata=1):**
1. Crear/someter POS Invoice o Sales Invoice
2. `custom_enviar_dian` se setea automáticamente a 1
3. Se llama `enviar_factura_fe(doc, dueno, items, "Inmediata B2B")`
4. Se crea Log Factura Electronica con estado "Pendiente"
5. Se envía a Factus API (`POST /v2/bills/validate`)
6. Si OK → estado="Validada", se guarda CUFE
7. Si error → estado="Error", se reintentará cada hora

**CCF (Consumidor final, requiere_factura_inmediata=0):**
1. Vender normalmente en POS
2. POS Invoice queda con `estado_fe = "Pendiente"`
3. Al cerrar caja (POS Closing Entry):
   - Botón "Enviar pendientes a DIAN" agrupa por dueño_fiscal
   - Se crea un "Resumen Diario CCF" (una factura electrónica por dueño)
   - Los POS Invoice se marcan `estado_fe = "Agrupada"`
4. El cierre de caja se bloquea si hay pendientes

### 3.6 Requisitos para que funcione
1. **Items deben tener `dueno_fiscal` asignado** (campo en Item)
2. **Dueno Fiscal debe tener credenciales Factus completas** (client_id, client_secret, username, password, numbering_range_id)
3. **Configuracion API FE** debe tener `cliente_consumidor_final` configurado
4. **Accounts de impuesto** deben tener `fe_tax_code` asignado
5. **Mode of Payment** debe tener `fe_tipo_medio_pago` asignado

---

## 4. Configuraciones del Sistema

### 4.1 Roles y Permisos
| Rol | Usuario | Permisos clave |
|---|---|---|
| Superadmin | johssalinas2work@gmail.com | Todos los roles, System Manager |
| Contadora | andrea@gmail.com | Accounts Manager, Sales/Purchase/Stock Manager, Item Manager |
| Admin tienda | lorena@gmail.com | Sales Manager, Purchase Manager, Stock Manager, Accounts Manager, Item Manager |
| Cajera | sharith@gmail.com | Sales User (POS Invoice, POS Opening/Closing, Customer, Item read, Mode of Payment read) |

### 4.2 Desktop Layouts
| Usuario | Redirigido a | Iconos en desktop |
|---|---|---|
| Sharith (cajera) | /desk/desktop | Solo Punto de Venta |
| Lorena (admin) | /desk/desktop | POS, caja, ventas, compras, inventario, maestros, log FE (16 iconos) |
| Andrea (contadora) | /desk/desktop | Facturas, pagos, asientos, cuentas, reportes, log FE, config FE (16 iconos) |
| Johs (superadmin) | Workspace normal | No redirigido |

### 4.3 Traducciones
- **Idioma del sistema:** es (Español)
- **Todos los usuarios:** language=es
- **.po files:** Descargados de frappe v16.24.0 y erpnext v16.25.0, compilados a .mo con babel
- **Translation doctype:** ~3,027 traducciones en BD (incluye POS, operadores de filtro, dashboards, etc.)
- **Item → Producto** (no "Artículo")

### 4.4 Migración de Siigo
- **429 Sales Invoices** migradas (Enero-Junio 2026)
- **Item genérico:** MIGRACION-SIIGO (no inventariado, UOM=Nos)
- **Tax templates:** "Colombia Tax - SM" (19%) e "IVA 5% - SM" (5%)
- **Pagos:** Cancelados vía Journal Entry contra cuenta 3710 (Pérdidas acumuladas), NO afecta caja
- **Total migrado:** $122,087,245 base + $21,894,804 impuesto = $143,982,050

### 4.5 Company / Warehouse / Cost Center
- **Company:** Salsamentaria Multiespecial (abrev: SM)
- **Warehouse:** Principal - SM
- **Cost Center:** Principal - SM
- **AR Account:** 13051 - Clientes - SM
- **Tax Account:** 2408 - Impuesto sobre las ventas por pagar - SM

---

## 5. Procedimientos Operacionales

### 5.1 Conectarse al Servidor
```bash
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129
```

### 5.2 Ejecutar comandos en el backend de ERPNext
```bash
# Obtener el container ID del backend
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Ejecutar bench command
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org <comando>'

# Ejecutar script Python
docker cp script.py $BC:/tmp/script.py
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && cat > /path/to/app/utils/_temp.py << PYEOF
import frappe
def run():
    # código aquí
PYEOF
bench --site salsamentariamultiespecial.duckdns.org execute module.path._temp.run'
```

### 5.3 Crear Backup
```bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Backup del sitio (DB + archivos)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org backup --with-files'

# Copiar backup fuera del contenedor
docker cp $BC:/home/frappe/frappe-bench/sites/salsamentariamultiespecial.duckdns.org/private/backups/ /root/fe-backups/

# Backup adicional: dump directo de MariaDB
docker exec $(docker ps -q --filter "name=db-vvekd3jmyymltrmfoi8vdbdu" | head -1) \
  mariadb-dump -u root --password='I3CcGBT7iS36t^AK' \
  --single-transaction salsamentariamultiespecial_duckdns_org | gzip > /root/fe-backups/db_dump_$(date +%Y%m%d).sql.gz
```

### 5.4 Restaurar Backup
```bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Restaurar desde archivo
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org restore /path/to/backup.sql.gz --with-private-files /path/to/private-files.tar --with-public-files /path/to/files.tar'
```

### 5.5 Desplegar Cambios de la App (sin perder datos)

**PASO 1: Hacer push de cambios a GitHub**
```bash
cd /Users/johs.brayan.salinas/Documents/facturacion-electronica
git add -A
git commit -m "descripción del cambio"
git push origin master
```

**PASO 2: Reconstruir la imagen Docker custom en el servidor**
```bash
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129

# Construir nueva imagen
docker build -t erpnext-fe:v16.25.0 /root/fe-image/

# Reetiquetar como frappe/erpnext (Coolify usa este tag)
docker tag erpnext-fe:v16.25.0 frappe/erpnext:v16.25.0
```

**PASO 3: Disparar redeploy via Coolify API**
```bash
curl -X POST \
  -H "Authorization: Bearer 2|WCIlYtdQc0gq8TexAtkPRmWZX6lYc0GwDJlBG3Nl89ba61fd" \
  "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/start"
```

> **Coolify NO hace `docker compose pull`** — usa la imagen local. Por eso el re-tag funciona.

**PASO 4: Después del redeploy, ejecutar migrate si hay cambios en doctypes**
```bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org migrate'
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org clear-cache'
```

**PASO 5: Reiniciar contenedores bench si es necesario**
```bash
P=vvekd3jmyymltrmfoi8vdbdu
for svc in backend scheduler queue-default queue-short queue-long frontend websocket; do
  cid=$(docker ps -q --filter "name=$svc-$P" | head -1)
  [ -n "$cid" ] && docker restart "$cid"
done
```

### 5.6 Actualizar Versión de ERPNext/Frappe
```bash
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129

# 1. Actualizar el Dockerfile (el script lo hace)
/root/fe-update-image.sh v16.XX.X

# 2. Hacer pull de la imagen stock (para que el FROM tenga base limpia)
docker pull frappe/erpnext:v16.XX.X

# 3. Reconstruir imagen custom
docker build -t erpnext-fe:v16.XX.X /root/fe-image/
docker tag erpnext-fe:v16.XX.X frappe/erpnext:v16.XX.X

# 4. Actualizar FRAPPE_VERSION en Coolify via API
curl -X PATCH \
  -H "Authorization: Bearer 2|WCIlYtdQc0gq8TexAtkPRmWZX6lYc0GwDJlBG3Nl89ba61fd" \
  -H "Content-Type: application/json" \
  -d '{"key":"FRAPPE_VERSION","value":"v16.XX.X","is_buildtime":true,"is_preview":false}' \
  "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/envs"

# 5. Redeploy
curl -X POST \
  -H "Authorization: Bearer 2|WCIlYtdQc0gq8TexAtkPRmWZX6lYc0GwDJlBG3Nl89ba61fd" \
  "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/start"

# 6. Después del deploy: migrate + build + clear-cache
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec $BC bash -lc 'export PATH=/home/frappe/.nvm/versions/node/v24.12.0/bin:$PATH; cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org migrate'
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org clear-cache'
```

> **ADVERTENCIA:** NUNCA ejecutar `bench build` en el contenedor para las traducciones — rompe los assets CSS/JS. Solo compilar .po a .mo con babel.

### 5.7 Cambiar de Sandbox a Producción (Factus)
1. Ir a: https://salsamentariamultiespecial.duckdns.org/app/configuracion-api-fe
2. Cambiar "Ambiente" de `Sandbox` a `Produccion`
3. Ir a: https://salsamentariamultiespecial.duckdns.org/app/dueno-fiscal/Lorena
4. Completar credenciales de PRODUCCIÓN de Factus
5. Verificar con el botón "Probar Conexión" (si está disponible)
6. Clear cache: `bench --site <site> clear-cache`

### 5.8 Limpiar Cache
```bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org clear-cache'
```

### 5.9 Ver Logs
```bash
# Backend
docker logs --tail 50 $(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Frontend (nginx)
docker logs --tail 50 $(docker ps -q --filter "name=frontend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Coolify deploy logs
docker exec coolify-db psql -U coolify -d coolify -c "SELECT logs FROM application_deployment_queues WHERE application_id='1' ORDER BY created_at DESC LIMIT 1;" | tail -50
```

### 5.10 Agregar Traducciones
```python
# Crear script temporal en el contenedor
import frappe

def run():
    translations = {
        "English String": "Traducción Español",
    }
    for source, translated in translations.items():
        existing = frappe.db.get_value("Translation", {"language": "es", "source_text": source})
        if not existing:
            doc = frappe.get_doc({
                "doctype": "Translation",
                "language": "es",
                "source_text": source,
                "translated_text": translated,
            })
            doc.flags.ignore_permissions = True
            doc.insert()
    frappe.db.commit()
```

Después: `bench --site <site> clear-cache` + restart frontend.

---

## 6. Pendientes y Estados Conocidos

### 6.1 Facturación Electrónica — PENDIENTE
- [ ] **Items sin dueno_fiscal:** NINGÚN producto tiene Dueño Fiscal asignado. Sin esto, no se genera ninguna factura electrónica.
- [ ] **Dueno Fiscal sin credenciales:** Falta client_id, client_secret, username, password, numbering_range_id de Factus.
- [ ] **Accounts sin fe_tax_code:** Verificar que las cuentas de impuesto tengan el código DIAN asignado.
- [ ] **Mode of Payment:** Ya están asignados (Cash→Efectivo, Credit Card→Tarjeta de Crédito, etc.)

### 6.2 Inventario — PENDIENTE
- [ ] El usuario debe hacer un ajuste de inventario manual producto por producto

### 6.3 Traducciones
- 3,027 traducciones en BD. Algunas pueden tener errores menores de word-replacement.
- Si se encuentran strings en inglés, agregar vía Translation doctype + clear cache.

### 6.4 Assets CSS/JS
- Los assets vienen de la imagen stock (consistentes). NO ejecutar `bench build` o se desincroniza `assets.json`.
- Las traducciones .mo se compilan con babel (`compile_po.py`), no con `bench build`.

---

## 7. Estructura del Repo Local

```
/Users/johs.brayan.salinas/Documents/facturacion-electronica/
├── facturacion_electronica/
│   ├── hooks.py                          # Hooks principales (on_login, boot_session, doc_events, etc.)
│   ├── patches.txt                       # Patches de migración
│   ├── __init__.py
│   ├── events/
│   │   ├── auth.py                       # on_login redirect + boot_session desktop_redirect
│   │   ├── sales_invoice.py             # before_submit, on_submit (envío DIAN)
│   │   ├── pos_invoice.py               # on_cancel, reenviar_pos_invoice_dian
│   │   └── pos_closing_entry.py         # before_submit (bloquear si pendientes), enviar_pendientes_fe
│   ├── overrides/
│   │   └── pos_invoice.py               # CustomPOSInvoice (before_submit, on_submit)
│   ├── utils/
│   │   ├── api_fe.py                     # API Factus (auth, emitir, descargar PDF, _fe_codigo helper)
│   │   ├── agrupacion.py                 # Agrupar CCF para resumen diario
│   │   ├── retry.py                      # Scheduler hourly reintentar facturas fallidas
│   │   └── validacion.py                # Cálculo de dígito de verificación NIT
│   ├── fixtures/
│   │   └── custom_field.json             # Definición de todos los Custom Fields
│   ├── facturacion_electronica/
│   │   └── doctype/
│   │       ├── configuracion_api_fe/     # Single - config global
│   │       ├── dueno_fiscal/             # Normal - entidad legal
│   │       ├── log_factura_electronica/  # Document - log de envíos DIAN
│   │       ├── tipo_documento_identidad_fe/
│   │       ├── tributo_fe/
│   │       ├── municipio_fe/
│   │       ├── codigo_impuesto_fe/
│   │       ├── unidad_medida_fe/
│   │       └── tipo_medio_pago_fe/
│   ├── patches/
│   │   ├── v0_0_2/remove_item_fe_tax_fields.py
│   │   ├── v0_0_3/remove_item_fe_uom_standard_fields.py
│   │   └── v0_0_4/migrar_campos_link_fe.py  # Migración Select→Link + crear registros default
│   └── public/
│       └── js/
│           ├── sales_invoice.js           # Botones FE en Sales/POS Invoice
│           ├── pos_closing_entry.js       # Botón "Enviar pendientes a DIAN"
│           └── desktop_redirect.js        # Redirect cajera/admin/contadora a /desk/desktop
├── pyproject.toml
├── setup.py
└── requirements.txt
```

---

## 8. Comandos Rápidos de Referencia

```bash
# SSH al servidor
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129

# Backend container ID
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Migrate
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org migrate'

# Clear cache
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org clear-cache'

# Backup
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org backup --with-files'

# Build app (solo si es necesario, NO hacer build general)
docker exec $BC bash -lc 'export PATH=/home/frappe/.nvm/versions/node/v24.12.0/bin:$PATH; cd /home/frappe/frappe-bench && bench build --app facturacion_electronica'

# Redeploy Coolify
curl -X POST -H "Authorization: Bearer 2|WCIlYtdQc0gq8TexAtkPRmWZX6lYc0GwDJlBG3Nl89ba61fd" "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/start"

# Reconstruir imagen custom
docker build -t erpnext-fe:v16.25.0 /root/fe-image/ && docker tag erpnext-fe:v16.25.0 frappe/erpnext:v16.25.0

# Restart todos los bench containers
P=vvekd3jmyymltrmfoi8vdbdu; for svc in backend scheduler queue-default queue-short queue-long frontend websocket; do cid=$(docker ps -q --filter "name=$svc-$P" | head -1); [ -n "$cid" ] && docker restart "$cid"; done
```

---

*Documento generado el 30 de Junio de 2026. Mantener actualizado ante cambios en credenciales o arquitectura.*


---

## 9. Análisis de Cierres de Caja y Mejoras al POS Closing Entry

### 9.1 Análisis de Cierre — 20 de agosto de 2026 (POS-CLO-2026-00019)

#### Problema reportado
El total general del cierre mostraba **$3.119.086** pero la suma manual de los montos esperados por modo de pago daba **$3.089.796**, una diferencia de **$29.290**.

Cálculo manual que producía la diferencia:
```
Monto esperado Efectivo:   2.102.202
Monto esperado Nequi:        174.284
Monto esperado Llave:        948.510
Monto apertura Efectivo:    -135.200
─────────────────────────────────────
Total:                     3.089.796   ≠   3.119.086
```

#### Causa raíz
ERPNext calcula el `grand_total` del cierre como la **suma de `grand_total` de todas las facturas asignadas**, independientemente de si están pagadas o no. Los `expected_amount` de cada modo de pago, en cambio, sólo reflejan lo que realmente entró a caja (pagos registrados en `tabSales Invoice Payment` menos vueltos más apertura).

La diferencia de $29.290 corresponde exactamente al `outstanding_amount` total de 3 facturas que quedaron dentro del cierre sin estar cobradas:

| Factura | Hora | Total | Cobrado | Pendiente | Estado |
|---|---|---|---|---|---|
| ACC-SINV-2026-00917 | 13:20 | $2.500 | $0 | $2.500 | Sin pago — sin registro en `tabSales Invoice Payment` |
| ACC-SINV-2026-00925 | 17:03 | $10.250 | $0 | $10.250 | Sin pago — sin registro en `tabSales Invoice Payment` |
| ACC-SINV-2026-00950 | 18:39 | $32.740 | $16.200 (Llave) | $16.540 | Pago parcial |

Verificación: `3.089.796 + 29.290 = 3.119.086 ✓`

#### Cómo se calcula el `expected_amount` de Efectivo

```
Pagos en efectivo (bruto desde tabSales Invoice Payment):  2.238.294
Menos vueltos dados (change_amount):                        -271.292
Efectivo neto del día:                                     1.967.002
Más fondo de apertura (tabPOS Opening Entry Detail):        +135.200
─────────────────────────────────────────────────────────────────────
expected_amount Efectivo:                                  2.102.202  ✓
```

#### Conclusión
- El `grand_total` del cierre **incluye facturas sin cobrar** — es el total de ventas generadas, no de caja recaudada.
- Los `expected_amount` representan **lo que físicamente debería estar en caja**.
- Las 3 facturas con saldo pendiente están "en la calle" como deuda. Para que el sistema cuadre completamente deben cancelarse, cobrarse o documentarse como crédito a clientes.

---

### 9.2 Mejora: Columna de Estado de Pago y Sin Límite de 50 Filas en el Cierre de Caja

**Fecha de implementación:** 22 de agosto de 2026  
**Commit:** `d1bf400` — `feat: columna estado de pago y sin limite en tabla del cierre de caja`

#### Problema
1. La tabla de facturas en el POS Closing Entry sólo mostraba 50 filas (paginación por defecto del grid de Frappe), ocultando el resto de ventas del día.
2. No había forma de ver directamente en la tabla qué facturas estaban pagadas, sin pagar o con pago parcial — había que abrir cada factura individualmente.

#### Solución implementada

Se modificaron 4 archivos y se agregaron 4 Custom Fields:

##### 9.2.1 `fixtures/custom_field.json`
Se agregaron los siguientes Custom Fields para que las columnas aparezcan en el grid del POS Closing Entry:

| Doctype | Campo | Tipo | Descripción |
|---|---|---|---|
| Sales Invoice Reference | `custom_modo_de_pago` | Data | Modo(s) de pago usados en la factura |
| Sales Invoice Reference | `custom_estado_pago` | Select | Pagada / Sin Pago / Pago Parcial |
| POS Invoice Reference | `custom_modo_de_pago` | Data | Modo(s) de pago usados en la factura |
| POS Invoice Reference | `custom_estado_pago` | Select | Pagada / Sin Pago / Pago Parcial |

Ambos campos tienen `in_list_view: 1` y `columns: 2` para que aparezcan como columnas visibles en el grid.

##### 9.2.2 `overrides/pos_closing_entry.py` — función `get_invoices`
Se agregó el cálculo de `custom_estado_pago` en el bucle de enriquecimiento, usando `outstanding_amount` de cada factura:

```python
outstanding = frappe.db.get_value(inv.doctype, inv.name, "outstanding_amount") or 0
grand_total = inv.get("grand_total") or 0
if outstanding <= 0:
    inv["custom_estado_pago"] = "Pagada"
elif grand_total and outstanding >= grand_total:
    inv["custom_estado_pago"] = "Sin Pago"
else:
    inv["custom_estado_pago"] = "Pago Parcial"
```

Este enriquecimiento ocurre cuando ERPNext carga las facturas al abrir un cierre nuevo (antes de guardarlo).

##### 9.2.3 `events/pos_closing_entry.py` — función `get_mode_of_payment_map`
Se cambió la firma de retorno: antes devolvía `{invoice_name: "Efectivo, Llave"}` (string), ahora devuelve:

```python
{invoice_name: {"modo_de_pago": "Efectivo, Llave", "estado_pago": "Pagada"}}
```

Se consulta `outstanding_amount` y `grand_total` desde `tabSales Invoice` en la misma llamada, usando la misma lógica de clasificación. Este endpoint es el que usa el JS para refrescar las columnas en cierres ya guardados (docstatus=0).

##### 9.2.4 `public/js/pos_closing_entry.js`
Dos cambios principales:

**a) Sin límite de 50 filas — función `set_grid_page_length`:**
```javascript
function set_grid_page_length(frm) {
    ["pos_invoices", "sales_invoices"].forEach(function (fieldname) {
        var field = frm.get_field(fieldname);
        if (field && field.grid) {
            if (field.grid.grid_pagination) {
                field.grid.grid_pagination.page_length = 10000;
            }
            field.grid.page_length = 10000;
            field.grid.refresh();
        }
    });
}
```
Se llama en el evento `refresh` (antes que cualquier otra cosa) y también al final de `fill_mode_of_payment` para que el límite no se restaure después del `refresh_field`.

> **⚠️ Nota (importante):** En Frappe v15+ la paginación del grid ya **no** se guarda en `grid.page_length`, sino en `grid.grid_pagination.page_length`. La versión original de este commit sólo seteaba `grid.page_length`, que en v16 era un **no-op**: el límite de 50 seguía activo. La versión corregida (commit `0b1caa7`, sección 9.4) setea ambos campos, por eso el "sin límite" ahora sí funciona.

**b) Escritura de `custom_estado_pago` en cada fila:**
```javascript
var info = row.sales_invoice && info_map[row.sales_invoice];
if (info) {
    row.custom_modo_de_pago = info.modo_de_pago || "";
    row.custom_estado_pago  = info.estado_pago  || "";
}
```

#### Despliegue

```bash
# 1. Reconstruir imagen custom en el servidor
docker build -t erpnext-fe:v16.25.0 /root/fe-image/
docker tag erpnext-fe:v16.25.0 frappe/erpnext:v16.25.0

# 2. Redeploy via Coolify API
curl -X POST -H "Authorization: Bearer 6|pWgM0C9LUAorBNFErd7CUFL9LBMaQosdKz67dGmread6523b" \
  "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/start"

# 3. Migrate para crear los Custom Fields en BD
BC=$(docker ps -q --filter 'name=backend-vvekd3jmyymltrmfoi8vdbdu')
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org migrate'

# 4. Clear cache
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org clear-cache'
```

#### Resultado
- La tabla del cierre de caja muestra **todas las facturas** sin paginación de 50.
- Dos columnas nuevas visibles: **Modo de Pago** y **Estado**.
- Las facturas sin cobrar o con pago parcial quedan identificadas visualmente de inmediato, sin necesidad de abrir cada una.

---

### 9.3 Referencia: Lógica de Totales del Cierre de Caja

Esta sección explica cómo ERPNext construye cada número del cierre para facilitar futuros análisis.

| Campo | Cómo se calcula |
|---|---|
| `grand_total` del cierre | `SUM(grand_total)` de todas las facturas asignadas, incluidas las sin pagar |
| `expected_amount` Efectivo | `SUM(SIP.amount WHERE modo=Efectivo)` − `SUM(change_amount)` + `opening_amount Efectivo` |
| `expected_amount` Nequi/Llave | `SUM(SIP.amount WHERE modo=X)` (sin descuento de vueltos ni apertura) |
| `opening_amount` | Viene de `tabPOS Opening Entry Detail` para el `pos_opening_entry` del cierre |
| Dinero físico esperado en caja | `SUM(expected_amount)` − `SUM(opening_amount)` = ventas netas cobradas del día |
| Facturas sin cobrar | `SUM(outstanding_amount)` de las facturas del cierre con `outstanding_amount > 0` |

**Fórmula de cuadre:**
```
grand_total del cierre
= dinero cobrado del día (expected_amount neto sin apertura)
+ outstanding_amount pendiente (facturas sin cobrar)
```

Si `grand_total ≠ sum(expected_amount) - opening_amount`, la diferencia son **ventas registradas pero no cobradas** en ese cierre.

---

### 9.4 Fix: el "sin límite de 50 filas" no funcionaba en Frappe v16 + problema de caché

**Fecha de implementación:** 23 de agosto de 2026  
**Commit:** `0b1caa7` — `fix: quitar limite de 50 filas en tabla del cierre de caja (compat Frappe v16 grid_pagination)`

#### Problema reportado
1. La tabla de facturas del cierre seguía mostrando sólo 50 filas (con paginador) tanto al **ver un cierre guardado** como al **crear un cierre nuevo** — a pesar del cambio 9.2.
2. Al hacer deploy, los cambios de JS no aparecían "a la primera": había que hacer `Ctrl+Shift+R` (recargar con limpieza de caché).

#### Causa raíz
1. **El `set_grid_page_length` era un no-op en Frappe v16.** Desde Frappe v15+, la paginación del grid se guarda en `grid.grid_pagination.page_length` (clase `GridPagination`, default 50), **no** en `grid.page_length`. Setear `grid.page_length = 10000` no afectaba nada.
   - Verificado empíricamente en producción (Frappe 16.24.3): con el código anterior, `grid_pagination.page_length` seguía en 50, `total_pages = 2` y se renderizaban sólo 50 filas con paginador (5 botones).
2. **Al crear un cierre nuevo**, las facturas se cargan de forma asíncrona (`get_invoices` → `freeze` → `add_child` → `refresh_field`). El `setTimeout` fijo de 2s en el handler `pos_opening_entry` podía ejecutarse antes de que existieran filas; `fill_mode_of_payment` retornaba temprano y nunca se volvía a aplicar el sin-límite.
3. **Caché:** el JS del doctype se entrega dentro de la respuesta de `getdoctype` (campo `__js`), que Frappe cachea en redis (`doctype_form_meta::<doctype>`, ClientCache con TTL 10 min). Tras un deploy, el servidor seguía sirviendo el `__js` viejo hasta `bench clear-cache`.

#### Solución implementada

En `facturacion_electronica/public/js/pos_closing_entry.js`:

**a) `set_grid_page_length` compatible con v15+** — setea ambos campos:
```javascript
function set_grid_page_length(frm) {
	["pos_invoices", "sales_invoices"].forEach(function (fieldname) {
		var field = frm.get_field(fieldname);
		if (field && field.grid) {
			if (field.grid.grid_pagination) {
				field.grid.grid_pagination.page_length = 10000;
			}
			field.grid.page_length = 10000;
			field.grid.refresh();
		}
	});
}
```

**b) Esperar a que las facturas carguen en un cierre nuevo** — nuevo handler `pos_opening_entry` que hace polling (cada 500ms, máx 30s) hasta que `get_invoices` termine de poblar las tablas, y recién ahí aplica el sin-límite y llena las columnas Modo de Pago / Estado:
```javascript
pos_opening_entry: function (frm) {
	apply_when_invoices_loaded(frm);
}

function has_invoices(frm) {
	return (frm.doc.pos_invoices || []).length > 0 || (frm.doc.sales_invoices || []).length > 0;
}

function apply_when_invoices_loaded(frm) {
	var attempts = 0;
	var apply = function () {
		attempts++;
		set_grid_page_length(frm);
		if (has_invoices(frm) || attempts > 60) {
			fill_mode_of_payment(frm);
			return;
		}
		setTimeout(apply, 500);
	};
	setTimeout(apply, 500);
}
```

#### Verificación en producción (con navegador real, Frappe 16.24.3)
| Escenario | Filas en la tabla | `grid_pagination.page_length` | Filas renderizadas | Paginador |
|---|---|---|---|---|
| Cierre guardado (85 facturas) | 85 | 10000 | 85 (todas) | No |
| Cierre nuevo (93 facturas) | 93 | 10000 | 93 (todas) | No |

Sin errores de consola. Antes del fix: 50 filas, paginador de 2 páginas.

#### Despliegue (incluye limpieza de caché obligatoria)
```bash
# 1. Reconstruir imagen custom (--no-cache para forzar git clone nuevo)
cd /root/fe-image && docker build --no-cache -t erpnext-fe:v16.25.0 .
docker tag erpnext-fe:v16.25.0 frappe/erpnext:v16.25.0

# 2. Redeploy via Coolify API
curl -X POST -H "Authorization: Bearer 6|pWgM0C9LUAorBNFErd7CUFL9LBMaQosdKz67dGmread6523b" \
  "http://localhost:8000/api/v1/applications/vvekd3jmyymltrmfoi8vdbdu/start"

# 3. Migrate (solo si cambió BD; para JS no es necesario, pero no daña)
BC=$(docker ps -q --filter 'name=backend-vvekd3jmyymltrmfoi8vdbdu')
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org migrate'

# 4. Clear cache — OBLIGATORIO: invalida doctype_form_meta::* (el __js viejo queda cacheado)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org clear-cache'

# 5. Reiniciar servicios
for svc in backend scheduler queue-default queue-short queue-long; do
  cid=$(docker ps -q --filter "name=$svc-vvekd3jmyymltrmfoi8vdbdu" | head -1)
  [ -n "$cid" ] && docker restart "$cid" >/dev/null
done
sleep 8
for svc in frontend websocket; do
  cid=$(docker ps -q --filter "name=$svc-vvekd3jmyymltrmfoi8vdbdu" | head -1)
  [ -n "$cid" ] && docker restart "$cid" >/dev/null
done
```

> **Nota sobre la caché del usuario:** El `__js` se entrega por la API `getdoctype` con `Cache-Control: no-store`, así que el navegador no lo cachea por HTTP. El comportamiento de "recién aparece tras Ctrl+Shift+R" se debía a la caché del servidor (resuelta con `clear-cache`). Un usuario con la pestaña/sesión abierta de antes del deploy puede necesitar **una** recarga para tomar el JS nuevo; a partir de ahí funciona a la primera.
