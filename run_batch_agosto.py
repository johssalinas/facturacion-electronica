import frappe
from facturacion_electronica.utils.batch_agosto import generar_facturas_agosto_sandbox

def run():
    resultado = generar_facturas_agosto_sandbox(
        dueno_fiscal="Lorena",
        limite=2,
        dry_run=False
    )
    print("\n" + "="*60)
    print(f"Total días procesados: {resultado['total_dias']}")
    print(f"Exitosas: {resultado['exitosas']}")
    print(f"Errores: {resultado['errores']}")
    print("="*60 + "\n")
    
    for r in resultado['resultados']:
        print(f"Fecha: {r['fecha']}")
        print(f"  Items: {r['items_count']}")
        print(f"  Estado: {r['status']}")
        if r.get('numero_factus'):
            print(f"  Número Factus: {r['numero_factus']}")
        if r.get('cufe'):
            print(f"  CUFE: {r['cufe'][:20]}...")
        if r.get('error'):
            print(f"  Error: {r['error']}")
        print()
