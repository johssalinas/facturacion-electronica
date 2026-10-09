# Importación Inteligente de Facturas de Compra con IA — Plan de Implementación

Cada tarea referencia los requerimientos que cubre (`R1`–`R13` de `requirements.md`). Las fases están ordenadas para entregar valor temprano y reducir riesgo: **la vía XML va antes que la fotografía**, porque permite construir y probar toda la capa de mapeo y creación de la factura con datos exactos, antes de añadirle el ruido del OCR.

---

## Fase 0 — Verificación de viabilidad (*gate*)

> **IMPORTANTE:** Esta fase es un punto de control. Si F0.1 falla, la vía XML no es viable con el proveedor actual y hay que replantear el alcance con el usuario antes de escribir código de producción. No avanzar a la Fase 1 sin cerrar F0.1, F0.2 y F0.5.

- [ ] **F0.1 — Confirmar el módulo de Recepción de documentos contra sandbox**
  - Verificar que el plan contratado de Factus incluye Recepción de documentos y que la compañía está habilitada como receptora ante la DIAN.
  - Autenticar con las credenciales del `Dueno Fiscal` y llamar `GET /v2/receptions/bills` sin filtros.
  - Registrar el **esquema real de la respuesta**: nombres de campos, paginación, formato de fechas, presencia del NIT y nombre del emisor, total y estado de eventos.
  - Llamar `GET /v2/documents/:trackId/download-xml` con un CUFE real de una factura recibida y confirmar el formato de retorno (base64 o texto) y el nombre del campo.
  - Probar `POST /v2/receptions/upload` con el CUFE de una factura que no esté aún en el receptor.
  - Documentar los códigos de error y los límites de peticiones observados.
  - _Requerimientos: R2, R3, R4_

- [ ] **F0.2 — Recolectar XML reales de proveedores habituales**
  - Obtener entre 10 y 15 XML de facturas realmente recibidas, de proveedores distintos.
  - Confirmar cuántos vienen envueltos en `AttachedDocument` y cuántos como `Invoice` directo.
  - Verificar que traen el detalle de líneas completo y no solo totales.
  - Anonimizar y guardar en `facturacion_electronica/tests/fixtures_ia/`.
  - _Requerimientos: R4_

- [ ] **F0.3 — Probar la decodificación de QR sobre facturas reales**
  - Fotografiar con un teléfono entre 10 y 15 representaciones gráficas impresas.
  - Medir la tasa de acierto de `cv2.QRCodeDetector` con la cascada de reintentos prevista.
  - Registrar los formatos de contenido del QR encontrados en la práctica.
  - Decidir si se añade `pyzbar` con `libzbar0` en el Dockerfile como respaldo.
  - _Requerimientos: R3_

- [ ] **F0.4 — Evaluar el proveedor de IA**
  - Probar dos o tres modelos de visión con las mismas 5 facturas físicas, midiendo campos correctos, líneas correctas, latencia y costo por factura.
  - Probar el mismo ejercicio con el modelo de clasificación usando *tool calling*.
  - Decidir proveedor, modelos y si se usa el SDK oficial o `requests`.
  - Estimar el costo mensual con el volumen real de facturas de compra.
  - _Requerimientos: R5, R6, R12_

- [ ] **F0.5 — Validar las dependencias en el contenedor real**
  - Instalar `pillow`, `opencv-python-headless`, `rapidfuzz` y `defusedxml` en el entorno con Python 3.14 y confirmar que importan.
  - Confirmar que el contenedor tiene salida HTTPS hacia el proveedor de IA.
  - Verificar que los *workers* de background y Redis están operativos para encolar trabajos largos.
  - _Requerimientos: R7, R12_

- [ ] **F0.6 — Verificar el comportamiento del redirector de escritorio en móvil**
  - Abrir el sistema desde un navegador móvil y comprobar si `public/js/desktop_redirect.js` interfiere con el formulario de `Purchase Invoice`.
  - Si interfiere, definir la excepción necesaria.
  - _Requerimientos: R1, R5_

**Entregable de la fase:** una nota técnica con el esquema real de los endpoints, la decisión de proveedor de IA con su costo estimado, la tasa de acierto del QR y la confirmación de dependencias. Con eso se cierran o se descartan los supuestos S1 a S5 de `requirements.md`.

---

## Fase 1 — Cimientos

- [ ] **F1.1 — Crear el DocType `Configuracion IA FE` (Single)**
  - Todos los campos de la sección 3.7 del diseño, con sus valores por defecto.
  - `api_key` como `Password`; `crear_item_automatico` en `0`.
  - Controlador con `validate` que verifique la coherencia de los umbrales y funciones de módulo `get_config_ia()`, `get_api_key()`, `esta_activo()`.
  - Botón "Probar conexión con el proveedor de IA", siguiendo el patrón de `probar_conexion` de `Dueno Fiscal`.
  - _Requerimientos: R12_

- [ ] **F1.2 — Crear las tablas hijas**
  - `Importacion Factura IA Item`, `Confianza Campo IA`, `Llamada IA` con los campos de las secciones 3.2 a 3.4.
  - _Requerimientos: R7, R8_

- [ ] **F1.3 — Crear el DocType `Importacion Factura IA`**
  - Campos, secciones, `autoname` `IMP-FC-.YYYY.-.#####`, `estado` con las ocho opciones.
  - Índice sobre `cufe`.
  - Permisos por rol según la sección 3.1.
  - Controlador con la máquina de estados y un método `_cambiar_estado` que valide las transiciones permitidas.
  - _Requerimientos: R7, R13_

- [ ] **F1.4 — Crear `Decision Importacion IA` y `Regla Clasificacion IA`**
  - Campos de las secciones 3.5 y 3.6.
  - Índices compuestos para la recuperación de contexto.
  - Permisos: decisiones de solo lectura para el usuario operativo.
  - Funciones de módulo `registrar_decision()` y `consolidar_regla()` con `ignore_permissions`, siguiendo el patrón de `crear_log`.
  - _Requerimientos: R9, R10_

- [ ] **F1.5 — Añadir los campos personalizados**
  - En `fixtures/custom_field.json`: los cinco de `Purchase Invoice` y los tres de `Supplier`.
  - Añadirlos a la lista filtrada de `fixtures` en `hooks.py`, e incluir de paso los cuatro campos de `Sales Invoice Reference` y `POS Invoice Reference` que faltan hoy.
  - _Requerimientos: R11_

- [ ] **F1.6 — Llevar la cuenta de IVA descontable a configuración**
  - En `events/purchase_invoice.py`, leer la cuenta desde `Configuracion IA FE.cuenta_iva_descontable`, con la constante actual como valor de respaldo.
  - Extraer una función reutilizable que resuelva la plantilla de impuesto y la tarifa de un producto, para poder simularla desde el clasificador sin duplicar lógica.
  - Verificar que el comportamiento actual no cambia cuando no hay configuración.
  - _Requerimientos: R11 · Riesgo T2_

- [ ] **F1.7 — Preparar dependencias y parches**
  - `requirements.txt` con las nuevas dependencias **y versiones fijadas**, incluida `requests`.
  - `patches/v0_1_0/crear_configuracion_ia.py`: crear el Single con valores por defecto de forma idempotente.
  - Registrar el parche en `patches.txt`.
  - _Requerimientos: R12_

- [ ] **F1.8 — Definir el documento canónico (`esquema.py`)**
  - Estructura de la sección 4.1, constructores, validación y serialización con `Decimal` como cadena.
  - Función compartida de normalización de texto, que usarán la pasada determinista, las reglas y la recuperación de contexto. Debe ser una sola implementación.
  - _Requerimientos: R4, R5, R7_

**Criterio de cierre:** `bench migrate` instala todo limpio, los formularios abren sin errores y la configuración se puede diligenciar y probar.

---

## Fase 2 — Vía XML: de la factura recibida al documento canónico

- [ ] **F2.1 — Cliente del módulo de recepción (`dian_recepcion.py`)**
  - Clase que reutilice el OAuth2 y el token en caché de `utils/api_fe.py`, sin duplicar la autenticación.
  - Métodos `listar_facturas_recibidas`, `cargar_por_cufe`, `descargar_xml`.
  - Tiempos de espera, manejo de errores y de límite de peticiones; registro en `frappe.log_error` con título identificable.
  - Ajustar el mapeo al esquema real confirmado en F0.1.
  - _Requerimientos: R2, R3_

- [ ] **F2.2 — Parser UBL (`ubl.py`)**
  - Desenvolver el sobre `AttachedDocument` leyendo el CDATA de `cbc:Description`.
  - Soportar `Invoice`, `CreditNote` y `DebitNote`.
  - Extraer todos los campos de la sección 4.1, incluyendo impuestos por línea.
  - Acumular lo no mapeado en `campos_no_mapeados`.
  - Parseo con `defusedxml` y límite de tamaño.
  - _Requerimientos: R4_

- [ ] **F2.3 — Pruebas del parser (`test_ubl.py`)**
  - Contra los XML reales anonimizados de F0.2, sin red.
  - Casos: sobre `AttachedDocument`, `Invoice` directo, nota crédito, factura sin IVA, factura con descuentos, IVA mixto, XML malformado.
  - Verificar que los totales parseados coinciden con los del documento.
  - _Requerimientos: R4_

- [ ] **F2.4 — Validación aritmética (`confianza.py`, primera parte)**
  - Las cinco validaciones de la sección 7, con tolerancia configurable.
  - `test_confianza.py` cubriendo cada validación y sus casos límite.
  - _Requerimientos: R7_

- [ ] **F2.5 — Ingesta desde la Bandeja DIAN y por CUFE**
  - Métodos whitelisted `listar_bandeja_dian`, `importar_desde_bandeja`, `importar_desde_cufe`.
  - Validación del formato del CUFE antes de cualquier llamada externa.
  - Marcar en la bandeja las facturas que ya tienen un `Purchase Invoice`, con su enlace.
  - Ingesta de XML cargado directamente por el usuario.
  - _Requerimientos: R2, R3, R4_

- [ ] **F2.6 — Orquestador y ejecución en segundo plano (`orquestador.py`)**
  - `procesar_importacion` con `frappe.enqueue` en la cola larga.
  - Progreso por `frappe.publish_realtime`; transiciones de estado; `reintentar_etapa`.
  - Todo error deja estado `Error` con el detalle en `errores`.
  - _Requerimientos: R7, R13_

**Criterio de cierre:** desde la bandeja se selecciona una factura recibida real y la importación queda en estado `Extraido` con el documento canónico completo y las validaciones aritméticas ejecutadas. Todavía sin IA.

---

## Fase 3 — Clasificación y creación de la Factura de Compra

- [ ] **F3.1 — Herramientas de consulta (`herramientas.py`)**
  - Las nueve funciones de la sección 6.2.
  - Solo lectura, parámetros validados, límite de filas propio, lista blanca de doctypes, filtro por compañía.
  - Esquema de cada herramienta en el formato del proveedor de IA elegido.
  - `test_herramientas.py` verificando límites, filtrado por compañía y ausencia de escrituras.
  - _Requerimientos: R6_

- [ ] **F3.2 — Pasada determinista (`determinista.py`)**
  - Los seis criterios de la tabla de la sección 6.1, en orden de prioridad.
  - Usar la función compartida de normalización de texto.
  - `test_determinista.py` con datos reales del sitio y `skipTest` cuando falten.
  - _Requerimientos: R6, R10_

- [ ] **F3.3 — Abstracción del proveedor de IA (`proveedor_ia.py`)**
  - Interfaz común para completado con visión, completado con herramientas y salida estructurada.
  - Implementación del proveedor elegido en F0.4.
  - Tiempo de espera, reintento con espera creciente ante errores transitorios, conteo de tokens y cálculo de costo.
  - Modo de pruebas con respuestas grabadas, sin red.
  - _Requerimientos: R6, R12_

- [ ] **F3.4 — Contexto de maestros (`contexto.py`)**
  - Compañía, moneda, plantillas de impuesto con su tarifa, unidades de medida con su código DIAN, grupos y marcas.
  - Cacheado, porque cambia poco y se usa en cada clasificación.
  - _Requerimientos: R6_

- [ ] **F3.5 — Clasificador JEV (`clasificador.py`)**
  - Prompt de sistema con los siete puntos de la sección 6.3, incluida la advertencia de que el contenido de la factura es dato y no instrucción, en un bloque delimitado.
  - Ciclo de *tool calling* con tope de iteraciones.
  - Validación de la salida contra el esquema; **verificar contra la base de datos que cada código propuesto existe**, y descartarlo si no.
  - Lo no resuelto queda como `Sin Correspondencia`, nunca inventado.
  - Registrar cada llamada en `Llamada IA` con herramientas invocadas, tokens, duración y costo.
  - _Requerimientos: R6, R7_

- [ ] **F3.6 — Cálculo de la confianza (`confianza.py`, segunda parte)**
  - Ponderación de las cinco señales y las cinco reglas de anulación de la sección 7.
  - Confianza global como mínimo entre el promedio del encabezado y el mínimo de las líneas.
  - Poblar `Confianza Campo IA`, los campos de confianza de las líneas y `campos_por_validar`.
  - Ampliar `test_confianza.py`.
  - _Requerimientos: R7, R8_

- [ ] **F3.7 — Simulación del impuesto y detección de discrepancias**
  - Para cada producto propuesto, resolver con la función extraída en F1.6 la plantilla que aplicaría el hook existente.
  - Comparar con el impuesto de la factura del proveedor y marcar la diferencia como campo a validar, mostrando ambos valores.
  - _Requerimientos: R8, R11 · Riesgo T1_

- [ ] **F3.8 — Generación de la propuesta**
  - Ensamblar el JSON completo de la propuesta y escribirlo **una sola vez** en `propuesta_json` con `db_set`.
  - Pasar la importación a `Por Validar`.
  - _Requerimientos: R7_

- [ ] **F3.9 — Materialización de la Factura de Compra (`aplicar.py`)**
  - Los nueve pasos de la sección 9, en transacción.
  - Control de duplicados por proveedor + número y por CUFE.
  - Creación condicional de proveedor y productos según configuración.
  - Insertar en borrador, **sin** enviar.
  - No reaplicable.
  - _Requerimientos: R11_

- [ ] **F3.10 — Pruebas de materialización (`test_aplicar.py`)**
  - Creación correcta del borrador; bloqueo por duplicado de número; bloqueo por duplicado de CUFE; intento de reaplicación; interacción con `apply_purchase_tax_template`; rollback ante error.
  - _Requerimientos: R11_

**Criterio de cierre:** una factura recibida real recorre el flujo completo desde la bandeja hasta un `Purchase Invoice` en borrador correcto, con confianza calculada por campo.

---

## Fase 4 — Vía fotografía

- [ ] **F4.1 — Preprocesamiento de imagen (`imagen.py`)**
  - Corrección de orientación por EXIF, conversión de HEIC/HEIF, PDF a imágenes, redimensionado, compresión iterativa hasta el límite de peso.
  - Rechazo con mensaje claro cuando no se pueda cumplir el límite.
  - Validación del tipo real por contenido, no por extensión.
  - _Requerimientos: R5_

- [ ] **F4.2 — Decodificación del QR (`qr.py`)**
  - Cascada de cinco pasos de la sección 5.3, incluido el respaldo de ingreso manual del CUFE.
  - Parseo tolerante del contenido, según los formatos encontrados en F0.3.
  - `test_qr.py` con las imágenes recolectadas.
  - _Requerimientos: R3_

- [ ] **F4.3 — Extracción por visión (`vision.py`)**
  - Una llamada con salida estructurada al documento canónico.
  - Instrucción estricta de transcribir sin inferir, con `null` para lo ausente.
  - Indicador de legibilidad por campo, que alimenta la confianza.
  - Conservar el texto íntegro en `texto_extraido`.
  - Soporte de varias imágenes de una misma factura.
  - _Requerimientos: R5_

- [ ] **F4.4 — Verificación cruzada con el QR**
  - Cuando el QR aportó campos de control, compararlos con lo extraído y marcar las diferencias.
  - _Requerimientos: R3, R7, R8_

- [ ] **F4.5 — Enrutamiento de la ingesta por imagen**
  - Al cargar una foto: intentar QR primero; si hay CUFE, ir por la vía XML; si no, ir por visión.
  - Permitir forzar la vía de visión cuando el usuario lo prefiera.
  - _Requerimientos: R1, R3, R5_

**Criterio de cierre:** una foto tomada con teléfono produce una propuesta con confianza calculada y, cuando la factura es electrónica, el sistema salta automáticamente a la vía XML por el QR.

---

## Fase 5 — Interfaz de validación y justificaciones

- [ ] **F5.1 — Punto de entrada "Importar con IA" (`purchase_invoice_ia.js`)**
  - Botón en formulario nuevo y en vista de lista de `Purchase Invoice`, condicionado por rol y por configuración activa.
  - Diálogo de selección de método con las cuatro vías, mostrando solo las habilitadas.
  - Campo de archivo con `accept="image/*"` y `capture="environment"` para la cámara del teléfono.
  - Mensajes claros cuando falte configuración.
  - Seguir el estilo de la app: ES5, envoltorio sobre `frappe.call`, `add_custom_button` agrupado.
  - _Requerimientos: R1, R5, R12_

- [ ] **F5.2 — Bandeja DIAN en la interfaz**
  - Diálogo con tabla paginada y filtros de fecha, NIT, nombre y número.
  - Marca visible de las facturas ya registradas con enlace al documento.
  - _Requerimientos: R2_

- [ ] **F5.3 — Formulario de validación (`importacion_factura_ia.js` + `importacion_ia.css`)**
  - Barra de estado con confianza global y campos por validar.
  - Resaltado por nivel de confianza con color, ícono y la etiqueta "Requiere validación" — nunca solo color.
  - Indicador de fuente y motivo por campo.
  - Bloque de discrepancias aritméticas destacado.
  - Panel lateral con la imagen original con zoom, o el resumen del XML.
  - Selector de alternativas por línea con su puntaje.
  - Indicador de progreso en vivo durante el procesamiento.
  - Registrar el CSS con `app_include_css`.
  - _Requerimientos: R8_

- [ ] **F5.4 — Detección de cambios y justificación obligatoria**
  - Comparación en el servidor contra `propuesta_json`, en `validate` y al aplicar.
  - Exigencia de `justificacion` por cambio, con soporte de `justificacion_general` para cambios homogéneos.
  - Mensaje de bloqueo que liste exactamente lo que falta justificar.
  - Diálogo en el cliente que pida el motivo al cambiar un valor propuesto, como comodidad, sin que sea la única barrera.
  - Pruebas que verifiquen que el bloqueo no se puede eludir modificando el documento por la API.
  - _Requerimientos: R9_

- [ ] **F5.5 — Registro de decisiones al aplicar**
  - Crear un `Decision Importacion IA` por cada cambio y por cada confirmación, con el texto de origen, el proveedor y la confianza original.
  - Las confirmaciones no exigen justificación.
  - _Requerimientos: R9_

- [ ] **F5.6 — Descartar importación**
  - Estado `Descartada` con motivo, conservando el registro y los adjuntos.
  - _Requerimientos: R8, R13_

**Criterio de cierre:** un usuario de compras completa el flujo en el navegador de su teléfono, ve resaltado lo dudoso, corrige justificando y obtiene la factura en borrador.

---

## Fase 6 — Aprendizaje

- [ ] **F6.1 — Recuperación del contexto histórico (`aprendizaje.py`)**
  - Los tres niveles de selección de la sección 6.4, con similitud por `rapidfuzz` y recorte por `max_decisiones_contexto`.
  - _Requerimientos: R10_

- [ ] **F6.2 — Incorporación del contexto al prompt de JEV**
  - Inyectar reglas aplicables como instrucciones y decisiones históricas como ejemplos.
  - Medir el efecto sobre el número de correcciones en un lote de control.
  - _Requerimientos: R10_

- [ ] **F6.3 — Consolidación de reglas**
  - Promover a `Regla Clasificacion IA` cuando una decisión se repita el número configurado de veces con el mismo resultado.
  - Recalcular `fuerza` con confirmaciones y contradicciones; desactivar por debajo del mínimo.
  - Ejecutar al aplicar la importación y, adicionalmente, en un trabajo programado diario para consolidaciones diferidas.
  - _Requerimientos: R10_

- [ ] **F6.4 — Aplicación de reglas en la pasada determinista**
  - Integrar la búsqueda de reglas en `determinista.py`, con los tres tipos de coincidencia.
  - Informar en la interfaz que el valor viene de una regla aprendida, indicando cuál.
  - _Requerimientos: R10_

- [ ] **F6.5 — Gestión de reglas**
  - Vista de lista utilizable con filtros por proveedor, tipo y fuerza.
  - Permitir desactivar y corregir reglas.
  - Registrar las contradicciones del usuario y reducir la fuerza correspondiente.
  - _Requerimientos: R10_

- [ ] **F6.6 — Reporte de métricas**
  - Las siete métricas de la sección 14 del diseño, en un *Query Report*.
  - La métrica central es campos corregidos por importación a lo largo del tiempo: es la que demuestra si el sistema aprende.
  - _Requerimientos: R10, R13_

**Criterio de cierre:** procesar dos facturas del mismo proveedor y comprobar que la segunda requiere menos correcciones, con reglas aplicadas visibles.

---

## Fase 7 — Endurecimiento y puesta en producción

- [ ] **F7.1 — Repaso de seguridad**
  - Confirmar que la clave de IA no aparece en logs, mensajes ni respuestas.
  - Confirmar que las herramientas de JEV no pueden escribir ni salirse de la lista blanca.
  - Revisar los permisos de los nuevos doctypes con un usuario de cada rol.
  - Comprobar el parseo seguro del XML con entradas maliciosas.
  - Verificar que la salida del modelo nunca se usa sin validar contra la base de datos.
  - _Requerimientos: R6, R12_

- [ ] **F7.2 — Control de costos**
  - Verificar el registro de tokens y costo por importación y el acumulado.
  - Confirmar el comportamiento ante errores de cuota o de límite de peticiones.
  - _Requerimientos: R12_

- [ ] **F7.3 — Prueba de aceptación con facturas reales**
  - Procesar entre 20 y 30 facturas reales de proveedores habituales por ambas vías.
  - Medir campos correctos, campos corregidos, tiempo por factura y costo.
  - Comparar contra el tiempo del registro manual actual, para tener una cifra de productividad real.
  - Ajustar umbrales de confianza con esos resultados.
  - _Requerimientos: todos_

- [ ] **F7.4 — Documentación**
  - Nueva sección en `DOCUMENTACION_COMPLETA.md` con configuración, operación y solución de problemas, **sin credenciales**.
  - Guía breve de uso para el personal de compras, incluida la captura desde el teléfono.
  - Advertencia explícita de que las facturas se transmiten a un servicio externo de IA.
  - _Requerimientos: R12, R13_

- [ ] **F7.5 — Despliegue gradual**
  - Activar primero solo la vía XML, con un usuario piloto.
  - Habilitar la fotografía después de validar la vía XML en producción.
  - Definir el procedimiento de desactivación rápida mediante el interruptor `activo`.
  - _Requerimientos: R12_

---

## Trabajo relacionado, fuera de este plan

Estas piezas son adyacentes y conviene decidir pronto si entran como fase adicional:

| Tema | Por qué importa |
|---|---|
| **Eventos RADIAN** (`030`, `032`, `033`) | El adquirente debe emitirlos para soportar el IVA descontable. La infraestructura de esta funcionalidad los deja al alcance: el `bill_id` de la factura recibida ya estaría disponible. |
| **Documento Soporte** para proveedores no obligados a facturar electrónicamente | Obligación legal hoy no implementada en la app. Aplica justo a las compras que llegarían por la vía de fotografía. |
| **Ingesta desde el buzón de correo** | Los proveedores están obligados a enviar el XML por correo. Leerlo automáticamente eliminaría incluso el paso de elegir en la bandeja. |
| **Limpieza de secretos en `DOCUMENTACION_COMPLETA.md`** y rotación de las credenciales expuestas | Riesgo de seguridad preexistente e independiente de esta funcionalidad. |

---

## Resumen de dependencias entre fases

```
F0 (gate)
 └─► F1 ─┬─► F2 ──► F3 ─┬─► F4 ──► F5 ──► F6 ──► F7
         │               │
         └───────────────┘
                 F3 requiere F2 (documento canónico con datos limpios)
                 F4 requiere F3 (la capa de clasificación ya probada)
                 F6 requiere F5 (sin decisiones registradas no hay aprendizaje)
```

La secuencia no es arbitraria: cada fase se apoya en que la anterior ya validó su parte del pipeline con datos conocidos. Intentar la fotografía antes de la vía XML obligaría a depurar simultáneamente el OCR, el mapeo y la creación de la factura.
