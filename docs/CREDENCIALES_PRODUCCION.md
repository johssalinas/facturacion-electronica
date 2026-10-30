# Credenciales y Configuración de Producción

## 🔐 Credenciales Factus

### Sandbox (Actual - Configurado)
- **Email:** salsamentariamultiespecial@gmail.com
- **Contraseña:** iYTGTy2m
- **Client ID:** a2e0cdc1-ad28-4659-bb0c-6b0b72b8eeb8
- **Client Secret:** irQBN5wSWIVKA4Lo0aui2vgHzqNQS3XDwqUaiLUu
- **Numbering Range ID:** 6141 (Prefijo SETP - Sandbox Test)

### Producción (Pendiente Configurar)
- **Email:** salsamentariamultiespecial@gmail.com
- **Contraseña:** iYTGTy2m
- **Client ID:** a2e0ce83-133b-4c5d-814b-0ed000fc148c
- **Client Secret:** vgALTD2S4IeMohc8cbNhn8CmgKM951ZSg6RJxNCZ
- **Numbering Range ID:** ⚠️ **PENDIENTE** - Configurar en portal Factus

## 📜 Resolución DIAN - Producción

- **NIT:** 1098769003
- **Razón Social:** SALSAMENTARIA MULTIESPECIAL
- **Prefijo:** SM
- **Rango:** 1 - 2000
- **Resolución DIAN:** 18764116394463
- **Vigencia:** 24 meses

## ✅ Pasos para Activar Producción

### 1. Configurar Rango en Portal Factus
1. Ir a https://app.factus.com.co/
2. Iniciar sesión con credenciales de producción
3. Navegar a "Rangos de Numeración"
4. Crear nuevo rango:
   - Prefijo: **SM**
   - Desde: **1**
   - Hasta: **2000**
   - Resolución DIAN: **18764116394463**
5. Anotar el **Numbering Range ID** asignado por Factus

### 2. Cargar Certificado Digital
1. En el portal Factus, sección "Certificados"
2. Cargar el archivo .p12 o .pfx del certificado digital
3. Ingresar la contraseña del certificado
4. Activar el certificado

### 3. Actualizar ERPNext con Credenciales de Producción

#### En Configuracion API FE (SingleDocType):
```python
frappe.db.set_value("Configuracion API FE", "Configuracion API FE", "ambiente", "Produccion")
```

#### En Dueno Fiscal "Lorena":
```python
dueno = frappe.get_doc("Dueno Fiscal", "Lorena")
dueno.client_id = "a2e0ce83-133b-4c5d-814b-0ed000fc148c"
dueno.set("client_secret", "vgALTD2S4IeMohc8cbNhn8CmgKM951ZSg6RJxNCZ")
dueno.set("username", "salsamentariamultiespecial@gmail.com")
dueno.set("password", "iYTGTy2m")
dueno.numbering_range_id = [NÚMERO_ASIGNADO_POR_FACTUS]  # Ejemplo: 7234
dueno.save()
```

O via bench console:
```bash
ssh root@46.225.227.129
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec -i $BC bench --site salsamentariamultiespecial.duckdns.org console

# Luego ejecutar:
frappe.db.set_value("Configuracion API FE", "Configuracion API FE", "ambiente", "Produccion")
frappe.db.commit()

dueno = frappe.get_doc("Dueno Fiscal", "Lorena")
dueno.client_id = "a2e0ce83-133b-4c5d-814b-0ed000fc148c"
dueno.set("client_secret", "vgALTD2S4IeMohc8cbNhn8CmgKM951ZSg6RJxNCZ")
dueno.set("username", "salsamentariamultiespecial@gmail.com")
dueno.set("password", "iYTGTy2m")
dueno.numbering_range_id = [NÚMERO_DEL_RANGO_SM]
dueno.save()
frappe.db.commit()
```

### 4. Ejecutar Prueba en Producción
Una vez configurado todo:
```python
from facturacion_electronica.utils.batch_septiembre import generar_facturas_septiembre_sandbox
result = generar_facturas_septiembre_sandbox(
    dueno_fiscal="Lorena",
    fecha_inicio="2026-09-01",
    fecha_fin="2026-09-12",
    limite=1,  # Empezar con 1 factura de prueba
    dry_run=False
)
```

## 📊 Estado Actual

### ✅ Completado
- [x] Integración Factus API v2 FAK08
- [x] Autenticación OAuth2
- [x] Formato de direcciones FAK08 compliance
- [x] Generación batch de facturas consolidadas
- [x] 12 facturas de prueba en Sandbox (Septiembre 1-12)
  - Total: $34,825,873 (~$35M)
  - Rango SETP990000085 - SETP990000096
  - Estado: Todas validadas ✅

### ⏳ Pendiente
- [ ] Usuario configura rango SM en portal Factus producción
- [ ] Usuario carga certificado digital en Factus
- [ ] Obtener numbering_range_id del rango SM
- [ ] Actualizar credenciales de producción en ERPNext
- [ ] Prueba con 1 factura en producción
- [ ] Generación masiva en producción

## 🔗 Enlaces Útiles

- **Portal Factus:** https://app.factus.com.co/
- **Documentación API:** https://docs.factus.com.co/
- **Servidor ERPNext:** ssh root@46.225.227.129
- **Sitio:** salsamentariamultiespecial.duckdns.org

## 📝 Notas

- Las credenciales de sandbox y producción usan el **mismo email/contraseña**
- Solo cambian los **Client ID** y **Client Secret**
- El ambiente se controla desde **Configuracion API FE**
- Cada dueño fiscal tiene sus propias credenciales OAuth2
- En producción se debe usar el prefijo **SM** (no SETP)

---
**Última actualización:** 2026-10-29
**Estado:** Documentado - Pendiente configuración de rangos en portal
