# Importación Inteligente de Facturas de Compra con IA — Requerimientos

## Introducción

Esta funcionalidad permite crear una **Factura de Compra** (`Purchase Invoice`) de ERPNext de forma automática a partir de:

1. Una **factura electrónica recibida** de un tercero (el proveedor emite a nombre nuestro y la DIAN la valida) — se obtiene el XML estructurado.
2. Una **fotografía de una factura física** tomada desde un teléfono móvil — se extrae el contenido con IA de visión/OCR.

El contenido extraído se envía a un clasificador de IA (**JEV**) que, con acceso controlado y de solo lectura a la base de datos, propone la correspondencia entre lo que dice la factura y los registros existentes en ERPNext (proveedor, productos, impuestos, unidades de medida). El usuario valida el formulario prediligenciado, corrige lo que esté mal justificando cada cambio, y el sistema aprende de esas correcciones para mejorar las importaciones futuras.

> **IMPORTANTE:** El alcance principal son las facturas que **terceros emiten a nuestro NIT**, no las que nosotros emitimos con Factus. En Colombia la representación electrónica de esas facturas se obtiene mediante el módulo de **Recepción de documentos** de Factus, que actúa como receptor autorizado ante la DIAN. La DIAN no expone una API pública para descargar el XML por CUFE: su portal `catalogo-vpfe.dian.gov.co` es una interfaz web con captcha, no apta para integración.

### Glosario

| Término | Significado |
|---|---|
| **CUFE** | Código Único de Factura Electrónica. Identificador hash que la DIAN asigna a cada factura de venta validada. |
| **CUDE / CUDS / CUNE** | Equivalentes del CUFE para notas crédito/débito, documentos soporte y nómina electrónica. |
| **UBL 2.1** | Estándar XML en el que se expresa la factura electrónica colombiana. |
| **AttachedDocument** | Sobre XML de la DIAN que envuelve la factura real (`Invoice`) embebida como CDATA. |
| **RADIAN** | Registro de la DIAN para eventos del adquirente sobre facturas recibidas (acuse de recibo, aceptación, reclamo). |
| **JEV** | Nombre del agente de IA que clasifica y normaliza el contenido de la factura contra la base de datos. |
| **Dueño Fiscal** | DocType existente que representa un NIT emisor con sus propias credenciales de Factus. |
| **Propuesta** | JSON estructurado generado por la IA que representa una Factura de Compra completa. |

---

## Requerimientos

### R1 — Punto de entrada "Importar con IA"

**Historia:** Como usuario de compras, quiero iniciar la importación de una factura desde la pantalla de Facturas de Compra, para no tener que digitar la información manualmente.

**Criterios de aceptación:**

1. CUANDO el usuario esté en la vista de lista de `Purchase Invoice` ENTONCES el sistema DEBE mostrar una acción **"Importar con IA"**.
2. CUANDO el usuario esté en un `Purchase Invoice` nuevo sin guardar ENTONCES el sistema DEBE mostrar un botón **"Importar con IA"**.
3. CUANDO el usuario active "Importar con IA" ENTONCES el sistema DEBE ofrecer los métodos de origen disponibles: **Bandeja DIAN**, **CUFE / Código QR**, **Fotografía** y **Archivo XML**.
4. El sistema DEBE procesar **una factura a la vez**. Una factura PUEDE requerir varias fotografías (por ejemplo, una tirilla larga), y esas imágenes se tratan como un único documento.
5. CUANDO el usuario no tenga el rol requerido ENTONCES el sistema NO DEBE mostrar la acción.
6. CUANDO la configuración de IA esté incompleta o desactivada ENTONCES el sistema DEBE mostrar un mensaje explicando qué falta configurar, en lugar de fallar con un error técnico.

---

### R2 — Ingesta desde la Bandeja DIAN (facturas recibidas de terceros)

**Historia:** Como usuario de compras, quiero ver la lista de facturas electrónicas que mis proveedores emitieron a nuestro NIT y seleccionar una para registrarla, para tener los datos exactos sin transcribir ni fotografiar nada.

**Criterios de aceptación:**

1. CUANDO el usuario abra la Bandeja DIAN ENTONCES el sistema DEBE listar las facturas electrónicas recibidas consultando el módulo de recepción de Factus, mostrando al menos: NIT y nombre del emisor, número de factura, fecha de emisión, valor total, CUFE y estado de eventos.
2. El sistema DEBE permitir filtrar la bandeja por rango de fechas, NIT del proveedor, nombre del proveedor y número de factura.
3. CUANDO una factura recibida ya tenga un `Purchase Invoice` registrado en ERPNext ENTONCES el sistema DEBE marcarla visiblemente como **ya registrada** e indicar el documento asociado.
4. CUANDO el usuario seleccione una factura de la bandeja ENTONCES el sistema DEBE descargar su XML original y usarlo como fuente de datos, sin recurrir a OCR.
5. CUANDO la consulta a la bandeja falle o devuelva vacío ENTONCES el sistema DEBE informarlo con un mensaje accionable y DEBE permitir continuar por las otras vías de ingesta.
6. El sistema DEBE consultar la bandeja usando las credenciales del **Dueño Fiscal** correspondiente a la compañía receptora.

---

### R3 — Ingesta por CUFE o código QR

**Historia:** Como usuario de compras, quiero escanear el QR de la representación gráfica impresa de una factura electrónica, o pegar el CUFE, para traer el XML estructurado de esa factura.

**Criterios de aceptación:**

1. CUANDO el usuario cargue una imagen que contenga un código QR ENTONCES el sistema DEBE intentar detectarlo y decodificarlo.
2. CUANDO el contenido del QR corresponda al formato de la DIAN ENTONCES el sistema DEBE extraer el CUFE y, cuando estén presentes, los campos de control (número de factura, fecha, NIT del emisor, NIT del adquirente y valores).
3. CUANDO no se detecte un QR legible ENTONCES el sistema DEBE permitir al usuario **ingresar o pegar el CUFE manualmente**.
4. CUANDO se disponga de un CUFE ENTONCES el sistema DEBE solicitar la carga de ese documento en el receptor y luego descargar su XML.
5. CUANDO el CUFE no exista, no corresponda a nuestro NIT como adquirente, o no esté disponible en el receptor ENTONCES el sistema DEBE informarlo con precisión y DEBE ofrecer continuar por la vía de fotografía/OCR.
6. CUANDO el CUFE tenga un formato inválido ENTONCES el sistema DEBE rechazarlo antes de hacer cualquier llamada externa.
7. El sistema DEBE aceptar también la carga directa de un archivo **XML** entregado por el proveedor, y procesarlo por la misma ruta de parseo.

---

### R4 — Extracción desde XML electrónico

**Historia:** Como usuario de compras, quiero que cuando exista el XML se usen esos datos y no OCR, para que la información sea exacta.

**Criterios de aceptación:**

1. CUANDO el XML esté envuelto en un sobre `AttachedDocument` ENTONCES el sistema DEBE desenvolver el documento embebido y procesar la factura real.
2. El sistema DEBE soportar los tipos `Invoice`, `CreditNote` y `DebitNote`.
3. El sistema DEBE extraer del XML como mínimo: identificación y razón social del emisor, número y prefijo de la factura, fecha y hora de emisión, moneda, forma y medio de pago, fecha de vencimiento, líneas de detalle (descripción, código del vendedor, cantidad, unidad de medida, precio unitario, descuentos, total de línea), impuestos por línea y totales, y los totales del documento (subtotal, impuestos, total a pagar).
4. CUANDO el XML contenga campos no reconocidos ENTONCES el sistema DEBE conservarlos en el registro de importación sin perder información.
5. CUANDO el XML esté corrupto o no cumpla la estructura esperada ENTONCES el sistema DEBE registrar el error con el detalle técnico y NO DEBE crear una propuesta parcial silenciosamente.
6. Los datos provenientes de XML DEBEN marcarse con fuente `XML DIAN` para efectos del cálculo de confianza.

---

### R5 — Extracción desde fotografía (visión / OCR)

**Historia:** Como usuario de compras, quiero tomar una foto de una factura física con mi teléfono y que el sistema lea su contenido, para registrar compras de proveedores que no facturan electrónicamente o cuando solo tengo el papel.

**Criterios de aceptación:**

1. CUANDO el usuario abra la captura desde un dispositivo móvil ENTONCES el sistema DEBE permitir usar la cámara directamente.
2. El sistema DEBE aceptar imágenes en formatos `JPG`, `PNG`, `HEIC`/`HEIF` y `WEBP`, y archivos `PDF`.
3. ANTES de enviar la imagen al servicio de IA el sistema DEBE corregir la orientación según metadatos EXIF y DEBE reducir resolución y peso hasta los límites configurados.
4. CUANDO la imagen exceda el peso máximo configurado y no pueda comprimirse dentro del límite ENTONCES el sistema DEBE rechazarla con un mensaje que indique el límite.
5. El sistema DEBE extraer el contenido textual completo de la factura, incluyendo como mínimo: datos del proveedor (nombre, NIT, dirección, teléfono), número de factura, fecha de emisión, líneas de productos o servicios con cantidad y precio unitario, impuestos, subtotales, total, forma de pago y cualquier otro dato presente en el documento.
6. El sistema DEBE conservar el texto extraído íntegro además de los datos estructurados.
7. CUANDO la imagen sea ilegible o no parezca una factura ENTONCES el sistema DEBE informarlo y DEBE permitir volver a cargar otra imagen sin perder el registro de importación.
8. Los datos provenientes de OCR DEBEN marcarse con fuente `OCR` para efectos del cálculo de confianza.
9. El sistema DEBE almacenar la imagen original adjunta al registro de importación, como soporte de auditoría.

---

### R6 — Clasificación y normalización con JEV

**Historia:** Como usuario de compras, quiero que la IA relacione lo que dice la factura con los proveedores, productos e impuestos que ya existen en el sistema, para no tener que buscarlos uno por uno.

**Criterios de aceptación:**

1. CUANDO se tenga el contenido de la factura ENTONCES el sistema DEBE invocar al clasificador JEV para determinar la correspondencia con los registros existentes.
2. JEV DEBE poder consultar, mediante funciones expuestas explícitamente, información de referencia de: proveedores, productos, grupos de productos, marcas, plantillas de impuesto de compra, unidades de medida y cuentas contables aplicables.
3. El acceso de JEV a la base de datos DEBE ser **de solo lectura**, limitado a las funciones expuestas, con parámetros validados y con un límite máximo de filas por consulta.
4. El sistema NO DEBE permitir que JEV ejecute consultas SQL arbitrarias, escriba en la base de datos, ni acceda a doctypes distintos a los expuestos.
5. ANTES de invocar a JEV el sistema DEBE resolver de forma determinista las correspondencias que puedan establecerse por coincidencia exacta (NIT normalizado del proveedor, reglas de clasificación aprendidas, código de barras o referencia del proveedor), y DEBE marcarlas con confianza máxima.
6. JEV DEBE proponer para cada línea de la factura: el producto correspondiente, la unidad de medida, la plantilla de impuesto y una lista de alternativas consideradas.
7. CUANDO JEV no encuentre una correspondencia razonable para un elemento ENTONCES DEBE indicarlo explícitamente como *sin correspondencia* en lugar de inventar un valor.
8. CUANDO el proveedor identificado no exista en el sistema ENTONCES el sistema DEBE proponer su creación con los datos extraídos, sin crearlo automáticamente salvo que la configuración lo autorice.
9. CUANDO un producto no exista en el sistema ENTONCES el sistema DEBE proponer su creación con los datos extraídos, sin crearlo automáticamente salvo que la configuración lo autorice.

---

### R7 — Propuesta estructurada de Factura de Compra

**Historia:** Como usuario de compras, quiero que el resultado de la IA sea una estructura completa que llene el formulario de factura de compra, para revisarla y confirmarla directamente.

**Criterios de aceptación:**

1. El sistema DEBE producir un JSON estructurado que represente completamente una Factura de Compra, con: encabezado, datos del proveedor, líneas de producto, cantidades, costos unitarios, impuestos, totales, observaciones y metadatos de confianza.
2. El JSON DEBE validarse contra un esquema definido, y DEBE rechazarse si no cumple.
3. El sistema DEBE verificar la consistencia aritmética de la propuesta: cantidad × precio unitario frente al total de línea, suma de líneas frente al subtotal, y subtotal más impuestos frente al total del documento.
4. CUANDO una verificación aritmética falle ENTONCES el sistema DEBE registrar la discrepancia y DEBE marcar los campos implicados como de baja confianza.
5. El JSON de la propuesta DEBE guardarse como **instantánea inmutable**, para poder comparar después contra lo que el usuario dejó finalmente.
6. El sistema DEBE registrar los metadatos de cada llamada a la IA: etapa, modelo usado, tokens consumidos, duración y costo estimado.
7. CUANDO la generación de la propuesta tarde más de unos segundos ENTONCES DEBE ejecutarse en segundo plano informando el progreso al usuario, sin bloquear la interfaz.

---

### R8 — Validación por parte del usuario con indicadores de confianza

**Historia:** Como usuario de compras, quiero ver el formulario prediligenciado con señales claras de qué campos son dudosos, para revisar solo lo necesario comparando contra la factura física.

**Criterios de aceptación:**

1. CUANDO la propuesta esté lista ENTONCES el sistema DEBE mostrar el formulario completamente diligenciado con los valores propuestos.
2. El sistema DEBE mostrar un indicador de confianza por cada campo propuesto y para el documento en conjunto.
3. El sistema DEBE clasificar la confianza en tres niveles: **Alta**, **Media** y **Baja**, según umbrales configurables.
4. Los campos de confianza **Media** o **Baja** DEBEN resaltarse visualmente mediante color, ícono de revisión y la etiqueta **"Requiere validación"**.
5. El sistema DEBE indicar la **fuente** de cada valor propuesto (XML DIAN, OCR, regla aprendida, inferencia de la IA) y el motivo de la sugerencia.
6. El sistema DEBE permitir ver la imagen o el documento original junto al formulario, para comparar.
7. El sistema DEBE mostrar de forma destacada las discrepancias aritméticas detectadas.
8. El sistema NO DEBE permitir aplicar la propuesta mientras existan campos obligatorios sin resolver o correspondencias marcadas como *sin correspondencia*.
9. El sistema DEBE permitir descartar la importación en cualquier momento, conservando el registro para auditoría.

---

### R9 — Captura obligatoria de la justificación de las decisiones del usuario

**Historia:** Como responsable del proceso, quiero que cada vez que alguien cambie una sugerencia de la IA quede registrado el motivo, para tener trazabilidad y para que el sistema aprenda.

**Criterios de aceptación:**

1. CUANDO el usuario modifique un valor sugerido por la IA ENTONCES el sistema DEBE exigir un comentario de **justificación obligatorio** para ese cambio.
2. El sistema DEBE detectar los cambios comparando los valores finales contra la instantánea inmutable de la propuesta.
3. La validación de la justificación DEBE ejecutarse **en el servidor**, de modo que no pueda omitirse desde el cliente.
4. CUANDO exista al menos un cambio sin justificación ENTONCES el sistema DEBE bloquear la aplicación de la propuesta e indicar exactamente qué cambios faltan justificar.
5. El sistema DEBE clasificar cada decisión registrada por tipo: proveedor, producto, impuesto, unidad de medida, cantidad, precio, cuenta contable u otro.
6. El sistema DEBE registrar por cada decisión: el valor sugerido por la IA, el valor elegido por el usuario, la justificación, el texto original de la factura que originó la sugerencia, el proveedor, la confianza original de la IA, el usuario y la fecha.
7. CUANDO el usuario **acepte** la sugerencia de la IA sin cambios ENTONCES el sistema DEBE registrar la confirmación sin exigir justificación.
8. El sistema DEBE permitir una justificación única aplicable a varios cambios homogéneos, sin dejar de registrar cada cambio individualmente.

---

### R10 — Aprendizaje a partir de las decisiones históricas

**Historia:** Como responsable del proceso, quiero que el sistema replique las decisiones que ya tomamos en situaciones parecidas, para que cada importación requiera menos correcciones que la anterior.

**Criterios de aceptación:**

1. El sistema DEBE almacenar todas las correcciones y justificaciones en una tabla de auditoría especializada, consultable y filtrable.
2. CUANDO se ejecute una nueva importación ENTONCES el sistema DEBE recuperar las decisiones históricas relevantes para el proveedor y para los textos de la factura, y DEBE incorporarlas como contexto adicional para JEV.
3. CUANDO una misma correspondencia se confirme repetidamente ENTONCES el sistema DEBE consolidarla como **regla de clasificación** reutilizable.
4. CUANDO exista una regla de clasificación aplicable ENTONCES el sistema DEBE aplicarla de forma determinista antes de consultar a la IA, y DEBE informar al usuario que el valor proviene de una regla aprendida.
5. El sistema DEBE permitir consultar, desactivar y corregir las reglas aprendidas.
6. CUANDO el usuario contradiga una regla aprendida ENTONCES el sistema DEBE registrar la contradicción y DEBE reducir la fuerza de esa regla.
7. La recuperación del contexto histórico DEBE estar acotada en volumen, para no exceder los límites del modelo ni encarecer las llamadas.
8. El sistema DEBE exponer métricas del aprendizaje: número de campos corregidos por importación, confianza promedio y tasa de aplicación de reglas, para verificar que la precisión mejora con el tiempo.

---

### R11 — Creación de la Factura de Compra

**Historia:** Como usuario de compras, quiero que al confirmar se cree la factura de compra en ERPNext respetando las reglas contables que ya tenemos configuradas.

**Criterios de aceptación:**

1. CUANDO el usuario confirme la propuesta validada ENTONCES el sistema DEBE crear un `Purchase Invoice` en estado **borrador**.
2. El sistema NO DEBE enviar (`submit`) la factura automáticamente.
3. El `Purchase Invoice` creado DEBE quedar vinculado al registro de importación, y DEBE conservar el CUFE de la factura del proveedor cuando exista.
4. El sistema DEBE respetar la lógica existente de plantillas de impuesto de compra por producto.
5. CUANDO el impuesto calculado por la lógica existente difiera del impuesto que trae la factura del proveedor ENTONCES el sistema DEBE marcar la diferencia como campo que requiere validación y DEBE mostrar ambos valores, en lugar de sobrescribir silenciosamente cualquiera de los dos.
6. ANTES de crear la factura el sistema DEBE verificar que no exista ya un `Purchase Invoice` para la misma combinación de proveedor y número de factura, ni para el mismo CUFE.
7. CUANDO se detecte un duplicado ENTONCES el sistema DEBE bloquear la creación e indicar el documento existente.
8. CUANDO la creación falle ENTONCES el sistema DEBE conservar el registro de importación con el error, sin dejar documentos parciales, y DEBE permitir reintentar tras corregir.
9. Una misma importación NO DEBE poder aplicarse dos veces.

---

### R12 — Configuración, seguridad y costos

**Historia:** Como administrador, quiero controlar el proveedor de IA, sus credenciales, los umbrales y el gasto, para operar la funcionalidad de forma segura y previsible.

**Criterios de aceptación:**

1. El sistema DEBE ofrecer una configuración centralizada con: proveedor de IA, modelo de visión, modelo de clasificación, credenciales, umbrales de confianza, límites de imagen, límite de contexto histórico y activación de cada vía de ingesta.
2. Las credenciales del proveedor de IA DEBEN almacenarse cifradas, y NO DEBEN aparecer en logs, mensajes de error ni documentación.
3. El sistema DEBE permitir activar o desactivar la funcionalidad completa sin desinstalar nada.
4. El sistema DEBE registrar el consumo de tokens y el costo estimado por importación, y DEBE permitir consultar el acumulado.
5. El sistema DEBE aplicar un límite de tamaño y de tiempo de espera a cada llamada externa, y DEBE manejar los errores de red sin dejar el registro de importación en un estado inconsistente.
6. CUANDO el proveedor de IA devuelva un error de cuota o de límite de peticiones ENTONCES el sistema DEBE informarlo de forma clara y DEBE permitir reintentar más tarde.
7. El acceso a los registros de importación y a la tabla de decisiones DEBE regirse por roles, y la tabla de decisiones NO DEBE ser editable por el usuario operativo una vez registrada.
8. El sistema DEBE advertir explícitamente, en la documentación y en la configuración, que las imágenes y el texto de las facturas se transmiten a un servicio externo de IA.

---

### R13 — Trazabilidad y operación

**Historia:** Como administrador, quiero poder auditar y depurar qué hizo la IA en cada importación, para resolver problemas y responder por los registros contables.

**Criterios de aceptación:**

1. El sistema DEBE conservar por cada importación: el archivo original, el texto o XML extraído, la propuesta generada, las llamadas a la IA realizadas, las decisiones del usuario y el documento resultante.
2. El sistema DEBE registrar el estado de cada importación a lo largo del flujo, con marcas de tiempo.
3. CUANDO ocurra un error en cualquier etapa ENTONCES el sistema DEBE registrar el detalle técnico y DEBE presentar al usuario un mensaje comprensible.
4. El sistema DEBE permitir reintentar una etapa fallida sin reiniciar todo el flujo.
5. El sistema DEBE ofrecer un reporte de importaciones con su estado, confianza, número de correcciones y usuario responsable.

---

## Alcance

### Incluido

- Registro de facturas de compra a partir de facturas electrónicas **recibidas** de terceros (XML vía receptor autorizado).
- Registro de facturas de compra a partir de **fotografías** de facturas físicas.
- Clasificación y normalización con IA contra los maestros existentes de ERPNext.
- Validación humana con indicadores de confianza por campo.
- Registro obligatorio de justificaciones y aprendizaje a partir de ellas.
- Creación del `Purchase Invoice` en borrador.

### Excluido (posible trabajo posterior)

| Fuera de alcance | Motivo |
|---|---|
| Procesamiento por lotes de múltiples facturas | El requerimiento define explícitamente una factura a la vez. |
| Envío automático (`submit`) de la factura de compra | Decisión contable que debe permanecer en manos del usuario. |
| Emisión de **eventos RADIAN** (acuse de recibo, aceptación expresa, reclamo) | Obligación legal del adquirente, relacionada pero independiente. Ver nota abajo. |
| Emisión de **Documento Soporte** para proveedores no obligados a facturar electrónicamente | Obligación legal independiente, hoy no implementada en la app. |
| Conciliación con órdenes de compra y recibos de compra | Requiere definir reglas de tolerancia y de tres vías. |
| Lectura automática del buzón de correo del proveedor | Vía de ingesta adicional, evaluada como opcional. |
| Reconocimiento de notas crédito/débito como documentos independientes | El parseo se soporta, pero el registro contable de devoluciones no. |

> **NOTA:** Los eventos RADIAN quedan fuera del alcance funcional de esta entrega, pero el diseño reserva el espacio para incorporarlos, porque el adquirente debe emitirlos para soportar el IVA descontable. Conviene decidir pronto si entran como fase adicional.

---

## Riesgos y supuestos

### Supuestos a confirmar antes de implementar

| # | Supuesto | Impacto si es falso |
|---|---|---|
| S1 | El plan contratado de Factus incluye el módulo de **Recepción de documentos** y la compañía está habilitada como receptora ante la DIAN. | Se pierden las vías 1 y 2 (bandeja y CUFE); solo quedaría OCR, con menor precisión. |
| S2 | Las facturas de nuestros proveedores llegan efectivamente al receptor con el detalle de líneas completo. | Habría que complementar con OCR incluso teniendo XML. |
| S3 | El entorno permite instalar dependencias de Python adicionales y salida HTTPS hacia el proveedor de IA. | Bloquea la funcionalidad completa. |
| S4 | Existe presupuesto operativo para el consumo de la API de IA. | Obliga a replantear a un modelo local o a limitar el uso. |
| S5 | Los usuarios de compras tienen teléfonos con cámara y acceso al sistema desde el navegador móvil. | Habría que replantear la captura. |

### Riesgos técnicos identificados

| # | Riesgo | Mitigación prevista |
|---|---|---|
| T1 | El hook existente `apply_purchase_tax_template` borra los impuestos de cabecera y fuerza la plantilla del producto en cada validación, lo que puede sobrescribir lo propuesto por la IA. | Se respeta la lógica existente y las diferencias se exponen como campos a validar. Ver diseño. |
| T2 | La cuenta de IVA descontable está fija en el código, acoplada a una sola compañía. | Llevarla a configuración como parte de este trabajo. |
| T3 | La confianza autoreportada por un modelo de lenguaje está mal calibrada. | La confianza se calcula combinando fuente, similitud textual, refuerzo histórico y validación aritmética. |
| T4 | Las fotografías de facturas térmicas o arrugadas producen OCR de baja calidad. | Se prioriza la vía XML; el OCR siempre pasa por validación humana. |
| T5 | La redirección global a escritorio existente en la app puede interferir con el uso desde el móvil. | Verificar y exceptuar la ruta de captura. |
| T6 | Costos y latencia crecientes si toda la clasificación pasa por la IA. | Pasada determinista previa y reglas aprendidas reducen las llamadas. |
| T7 | Envío de información fiscal a un tercero. | Credenciales cifradas, advertencia explícita, y opción de desactivar la vía de IA. |
| T8 | Una importación aplicada dos veces genera doble registro contable. | Verificación de duplicados por proveedor + número y por CUFE, y bloqueo de reaplicación. |

---

## Trazabilidad con el requerimiento original

| Sección del requerimiento original | Requerimientos de esta especificación |
|---|---|
| 1. Opción "Importar con IA" | R1 |
| 2. Extracción — facturas físicas | R5 |
| 2. Extracción — facturas electrónicas DIAN | R2, R3, R4 |
| 3. Clasificación y normalización mediante JEV | R6 |
| 4. Generación de estructura de datos | R7 |
| 5. Validación por parte del usuario | R8 |
| 6. Captura de decisiones del usuario | R9 |
| 7. Aprendizaje basado en decisiones históricas | R10 |
| Resultado esperado | R11, R13 |
| (No explícito en el original, necesario para operar) | R12 |
