#!/usr/bin/env python3
import frappe

frappe.init(site="salsamentariamultiespecial.duckdns.org")
frappe.connect()

from facturacion_electronica.utils.batch_septiembre import generar_facturas_septiembre_sandbox

result = generar_facturas_septiembre_sandbox(
    dueno_fiscal="Lorena", 
    fecha_inicio="2026-09-01", 
    fecha_fin="2026-09-12", 
    limite=None, 
    dry_run=True
)

print("\n=== RESULTADO FINAL ===")
print(f"Total días: {result['total_dias']}")
print(f"Total acumulado: ${result['total_acumulado']:,.0f}")

frappe.destroy()
