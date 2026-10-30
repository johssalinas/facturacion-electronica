import frappe

def run():
    from facturacion_electronica.utils.batch_agosto import generar_facturas_agosto_sandbox
    
    print("="*80)
    print("PRUEBA DE INTEGRACION SANDBOX - 1 FACTURA")
    print("="*80)
    
    # Generar 1 factura de prueba
    resultado = generar_facturas_agosto_sandbox(
        dueno_fiscal="Lorena",
        limite=1,
        dry_run=False
    )
    
    print(f"\nResultado:")
    print(f"  Total dias procesados: {resultado['total_dias']}")
    print(f"  Exitosas: {resultado['exitosas']}")
    print(f"  Errores: {resultado['errores']}")
    
    if resultado['resultados']:
        r = resultado['resultados'][0]
        print(f"\nDetalle factura generada:")
        print(f"  Fecha: {r['fecha']}")
        print(f"  Items: {r['items_count']}")
        print(f"  Estado: {r['status']}")
        if r.get('numero_factus'):
            print(f"  Numero Factus: {r['numero_factus']}")
        if r.get('cufe'):
            print(f"  CUFE: {r['cufe'][:40]}...")
        if r.get('error'):
            print(f"  Error: {r['error']}")
    
    print("="*80)
