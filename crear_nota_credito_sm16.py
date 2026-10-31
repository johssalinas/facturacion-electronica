#!/usr/bin/env python3
"""
Genera nota crédito para anular factura SM16
"""
import requests
import json
from datetime import datetime

# Credenciales producción
auth_data = {
    "grant_type": "password",
    "client_id": "a2e0ce83-133b-4c5d-814b-0ed000fc148c",
    "client_secret": "vgALTD2S4IeMohc8cbNhn8CmgKM951ZSg6RJxNCZ",
    "username": "salsamentariamultiespecial@gmail.com",
    "password": "iYTGTy2m",
}

print("\n=== AUTENTICANDO ===")
resp = requests.post("https://api.factus.com.co/oauth/token", data=auth_data)
token = resp.json()["access_token"]
print(f"Token: {token[:30]}...")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Consultar factura original SM16
print("\n=== CONSULTANDO FACTURA SM16 ===")
resp = requests.get("https://api.factus.com.co/v2/bills/SM16", headers=headers)

if resp.status_code != 200:
    print(f"Error consultando SM16: {resp.status_code} - {resp.text}")
    exit(1)

factura_original = resp.json()["data"]
print(f"Número: {factura_original['number']}")
print(f"CUFE: {factura_original['cufe']}")
print(f"Reference Code: {factura_original['reference_code']}")

# Necesitamos el rango de nota crédito
print("\n=== CONSULTANDO RANGOS DISPONIBLES ===")
resp = requests.get("https://api.factus.com.co/v2/numbering-ranges", headers=headers)
rangos = resp.json()["data"]["data"]

# Buscar rango de nota crédito o usar el mismo SM
rango_nc = None
for r in rangos:
    if r.get("document") == "22":  # Nota Crédito
        rango_nc = r
        break

if not rango_nc:
    print("⚠️  No hay rango de Nota Crédito configurado")
    print("Necesitas crear un rango con document='22' en Factus")
    print("\nRangos disponibles:")
    for r in rangos:
        print(f"  ID: {r['id']} | Document: {r['document']} | Prefix: {r['prefix']}")
    exit(1)

print(f"Rango NC encontrado: ID {rango_nc['id']} - Prefix {rango_nc['prefix']}")

# Crear payload nota crédito
# Según Factus API v2, debe referenciar la factura original
payload_nc = {
    "reference_code": f"NC-SM16-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "document": "22",  # Nota Crédito
    "numbering_range_id": rango_nc["id"],
    "discrepancy_response": {
        "reference_document_number": "SM16",
        "reference_document_cufe": factura_original["cufe"],
        "correction_concept_id": "1",  # 1 = Anulación de factura electrónica
        "correction_concept_observation": "Anulación total de factura SM16 por ajuste de montos"
    },
    "send_email": False,
    # Copiar customer y items de la factura original
    "customer": factura_original["customer"],
    "items": factura_original["invoice_lines"],
    "payment_details": factura_original["payment_form"],
}

print("\n=== CREANDO NOTA CRÉDITO ===")
print(f"Payload: {json.dumps(payload_nc, indent=2, ensure_ascii=False)[:500]}...")

resp = requests.post(
    "https://api.factus.com.co/v2/credit-notes/validate",
    headers=headers,
    json=payload_nc,
    timeout=30
)

print(f"\nStatus: {resp.status_code}")
print(f"Respuesta: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")

if resp.status_code in (200, 201):
    nc_data = resp.json()["data"]
    print(f"\n✅ Nota Crédito creada!")
    print(f"Número: {nc_data.get('number')}")
    print(f"CUFE: {nc_data.get('cufe')}")
else:
    print(f"\n❌ Error al crear nota crédito")
