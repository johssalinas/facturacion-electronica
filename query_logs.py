import frappe

def run():
    logs = frappe.get_all("Log Factura Electronica", 
        filters={"reference_code": ["like", "AGO-%"]},
        fields=["name", "reference_code", "estado", "numero_factus", "cufe", "public_url"],
        order_by="creation desc",
        limit=5
    )
    
    print("\n" + "="*80)
    print(f"FACTURAS DE AGOSTO GENERADAS EN SANDBOX ({len(logs)} encontradas)")
    print("="*80)
    
    for log in logs:
        print(f"\nLog: {log.name}")
        print(f"  Reference: {log.reference_code}")
        print(f"  Estado: {log.estado}")
        print(f"  Número Factus: {log.numero_factus}")
        if log.cufe:
            print(f"  CUFE: {log.cufe[:40]}...")
        if log.public_url:
            print(f"  URL Pública: {log.public_url}")
    
    print("\n" + "="*80)
    print("Para ver los logs completos, ve a:")
    print("https://salsamentariamultiespecial.duckdns.org/app/log-factura-electronica")
    print("="*80 + "\n")
