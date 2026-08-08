# Integración Báscula MORESCO MAVIN HY918

## Estado: PENDIENTE DE CALIBRACIÓN

La integración está implementada y desplegada. Falta conectar la báscula física y ajustar el parser del formato de datos.

## Equipamiento

- **Báscula:** MORESCO MAVIN HY918
- **Conexión:** Cable RS232 directo al computador (puerto COM3)
- **No requiere** adaptador USB (el PC ya tiene puerto serial)

## Cómo funciona en el POS

1. Al abrir el POS aparece el panel de báscula (debajo del carrito)
2. Presionar "Conectar Báscula" → Chrome muestra selector de puerto → elegir COM3
3. El display muestra peso en tiempo real
4. Escanear producto → Presionar "Pesar" (o tecla F9) → la cantidad se actualiza con el peso

## Archivo de configuración

`facturacion_electronica/public/js/pos_scale.js` — Objeto `POS_SCALE_CONFIG` al inicio del archivo.

## Pasos para calibrar

### 1. Conectar la báscula al PC

Conectar el cable RS232 de la báscula al puerto serial del computador.

### 2. Verificar con PuTTY qué envía la báscula

1. Descargar PuTTY: https://www.putty.org/
2. Abrir PuTTY → Connection type: **Serial**
3. Serial line: **COM3** (verificar en Administrador de Dispositivos)
4. Speed: **9600**
5. Click "Open"
6. Poner peso en la báscula y anotar el texto que aparece

### 3. Ajustar el parser

Abrir `facturacion_electronica/public/js/pos_scale.js` y editar la función `parseWeight` según el formato observado.

Ejemplos comunes:

| Formato recibido | Parser |
|---|---|
| `ST,GS,  0.325 kg` | Extraer número decimal → 0.325 |
| `+  0.500 kg` | Extraer número decimal → 0.500 |
| `0325` (sin punto) | Dividir entre 1000 → 0.325 |
| `W: 1.250 KG\r\n` | Extraer número decimal → 1.250 |

El parser actual es genérico (extrae el primer número decimal de la línea). Si el dato llega sin punto decimal (ej: `0325` = 325 gramos), ajustar la división.

### 4. Ajustar otros parámetros si es necesario

```javascript
var POS_SCALE_CONFIG = {
    baudRate: 9600,         // Casi siempre 9600, verificar manual
    dataBits: 8,            // Casi siempre 8
    stopBits: 1,            // Casi siempre 1
    parity: "none",         // "none", "even", "odd"
    mode: "continuous",     // "continuous" si envía datos sola, "on_demand" si hay que pedirle
    requestCommand: "W\r\n", // Solo para on_demand
    minWeight: 0.005,       // Peso mínimo válido (5g)
};
```

### 5. Desplegar cambios

```bash
cd ~/Documents/facturacion-electronica
git add -A && git commit -m "Calibrar parser bascula" && git push origin master
```

Luego copiar al servidor:
```bash
ssh -i ~/.ssh/id_ed25519_hetzner root@46.225.227.129
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
FE=$(docker ps -q --filter "name=frontend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
# copiar archivo y limpiar cache
```

## Requisitos del navegador

- **Chrome o Edge** (Web Serial API no funciona en Firefox/Safari)
- La primera vez pide permiso para acceder al puerto serial
- Solo funciona en el computador donde está conectada la báscula (no desde celular)

## Atajo de teclado

- **F9** — Tomar peso y aplicar al último producto del carrito
