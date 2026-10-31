# Plan de Facturación Electrónica - Producción

## ✅ Estado Actual

### Configuración Completada
- ✅ Rango SM creado en Factus producción (ID: 3312)
  - Prefijo: SM
  - Rango: 1 - 2000
  - Resolución DIAN: 18764116394463
- ✅ Credenciales de producción configuradas
- ✅ Ambiente cambiado a "Produccion"
- ✅ Scripts corregidos (sin "Sandbox Test")

### Factura Ya Generada en Producción
- **SM1** - 2026-09-01
  - Subtotal: $1,760,212
  - IVA: $334,440
  - **Total: $2,094,652** ✅
  - CUFE: 7565e1eb7abfd6c3d7f380705df079626fe3f3d29028fbe53032075b8bee4f966ab4d392897abea2a30ce3d4c2cea41b

## 📊 Metas Ajustadas (CON IVA)

### Septiembre 2026
**Meta total:** $36,300,000  
**Ya generada:** $2,094,652 (SM1)  
**Pendiente:** ~$34,205,348

**Rango calculado:** 02 al 13 de septiembre (12 días)

| Día | Fecha | Total con IVA | Acumulado |
|-----|-------|---------------|-----------|
| YA | 2026-09-01 | $2,094,652 | $2,094,652 |
| 2 | 2026-09-02 | $1,923,217 | $4,017,869 |
| 3 | 2026-09-03 | $3,456,059 | $7,473,928 |
| 4 | 2026-09-04 | $2,487,234 | $9,961,162 |
| 5 | 2026-09-05 | $2,885,364 | $12,846,526 |
| 6 | 2026-09-06 | $4,291,818 | $17,138,344 |
| 7 | 2026-09-07 | $3,621,695 | $20,760,039 |
| 8 | 2026-09-08 | $1,632,482 | $22,392,521 |
| 9 | 2026-09-09 | $2,528,868 | $24,921,389 |
| 10 | 2026-09-10 | $3,305,610 | $28,226,999 |
| 11 | 2026-09-11 | $2,666,372 | $30,893,371 |
| 12 | 2026-09-12 | $3,810,489 | $34,703,860 |
| 13 | 2026-09-13 | $4,137,188 | **$38,841,048** |

**Total final proyectado:** $38,841,048 (excede meta en $2.5M)  
**Ajuste sugerido:** Hasta Sep 12 → $34,703,860 (~$34.7M, cerca de meta)

### Octubre 2026
**Meta total:** $37,400,000

**Rango calculado:** 01 al 10 de octubre (10 días)

| Día | Fecha | Total con IVA | Acumulado |
|-----|-------|---------------|-----------|
| 1 | 2026-10-01 | $4,398,712 | $4,398,712 |
| 2 | 2026-10-02 | $4,602,554 | $9,001,266 |
| 3 | 2026-10-03 | $3,885,316 | $12,886,582 |
| 4 | 2026-10-04 | $5,760,048 | $18,646,630 |
| 5 | 2026-10-05 | $5,151,969 | $23,798,599 |
| 6 | 2026-10-06 | $1,087,682 | $24,886,281 |
| 7 | 2026-10-07 | $3,847,202 | $28,733,483 |
| 8 | 2026-10-08 | $2,807,260 | $31,540,743 |
| 9 | 2026-10-09 | $2,774,887 | $34,315,630 |
| 10 | 2026-10-10 | $3,648,320 | **$37,963,950** |

**Total final proyectado:** $37,963,950 ✅ (muy cerca de meta $37.4M)

## 🚀 Comandos para Ejecutar

### Septiembre (Sep 02-12) - 11 facturas pendientes

**Dry run (simulación):**
```bash
ssh root@46.225.227.129
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec $BC bash -c 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org execute facturacion_electronica.utils.batch_septiembre.generar_facturas_septiembre_sandbox --kwargs "{\"dueno_fiscal\":\"Lorena\",\"fecha_inicio\":\"2026-09-02\",\"fecha_fin\":\"2026-09-12\",\"dry_run\":True}"'
```

**Producción (REAL):**
```bash
docker exec $BC bash -c 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org execute facturacion_electronica.utils.batch_septiembre.generar_facturas_septiembre_sandbox --kwargs "{\"dueno_fiscal\":\"Lorena\",\"fecha_inicio\":\"2026-09-02\",\"fecha_fin\":\"2026-09-12\",\"dry_run\":False}"'
```

### Octubre (Oct 01-10) - 10 facturas

**Dry run (simulación):**
```bash
docker exec $BC bash -c 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org execute facturacion_electronica.utils.batch_octubre.generar_facturas_octubre_sandbox --kwargs "{\"dueno_fiscal\":\"Lorena\",\"fecha_inicio\":\"2026-10-01\",\"fecha_fin\":\"2026-10-10\",\"dry_run\":True}"'
```

**Producción (REAL):**
```bash
docker exec $BC bash -c 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org execute facturacion_electronica.utils.batch_octubre.generar_facturas_octubre_sandbox --kwargs "{\"dueno_fiscal\":\"Lorena\",\"fecha_inicio\":\"2026-10-01\",\"fecha_fin\":\"2026-10-10\",\"dry_run\":False}"'
```

## ⚠️ Notas Importantes

1. **Observaciones corregidas:** Se eliminó "(Sandbox Test)" de las observaciones
2. **Totales con IVA:** Los montos mostrados incluyen IVA (grand_total)
3. **SM1 ya existe:** La factura del 1 de septiembre ya fue generada
4. **Rango de producción:** SM 1-2000 está activo y funcionando
5. **Validación DIAN:** Todas las facturas serán reportadas a la DIAN

## 📋 Resumen Final

| Mes | Facturas | Total Proyectado | Meta | Diferencia |
|-----|----------|------------------|------|------------|
| Septiembre | 12 (SM1-SM12) | $34,703,860 | $36,300,000 | -$1,596,140 |
| Octubre | 10 (SM13-SM22) | $37,963,950 | $37,400,000 | +$563,950 |
| **TOTAL** | **22** | **$72,667,810** | **$73,700,000** | **-$1,032,190** |

**Uso del rango:** 22 de 2000 folios (1.1%)

---
**Última actualización:** 2026-10-30  
**Estado:** ✅ Listo para producción - Esperando confirmación del usuario
