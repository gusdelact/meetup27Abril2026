"""
Handler Lambda — Microservicio de Restaurantes y Menús (Restaurant Service).

╔══════════════════════════════════════════════════════════════════════╗
║  MICROSERVICIO DE RESTAURANTES — FTGO (Food To Go Online)          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Responsabilidad:                                                    ║
║    Gestionar los restaurantes y sus menús (platillos/productos).     ║
║    Cada restaurante tiene datos generales y un menú con N platillos. ║
║                                                                      ║
║  Operaciones expuestas:                                              ║
║    ── Restaurantes ──                                                ║
║    POST   /api/restaurantes/              → Crear restaurante        ║
║    GET    /api/restaurantes/              → Listar todos             ║
║    GET    /api/restaurantes/{id}          → Obtener uno por ID       ║
║    PUT    /api/restaurantes/{id}          → Actualizar datos         ║
║    DELETE /api/restaurantes/{id}          → Eliminar (+ su menú)     ║
║    ── Menú ──                                                        ║
║    POST   /api/restaurantes/{id}/menu     → Agregar platillo         ║
║    GET    /api/restaurantes/{id}/menu     → Obtener menú completo    ║
║    PUT    /api/restaurantes/menu/{elem_id} → Actualizar platillo     ║
║    DELETE /api/restaurantes/menu/{elem_id} → Eliminar platillo       ║
║                                                                      ║
║  Infraestructura AWS:                                                ║
║    • AWS Lambda      → Ejecuta este código bajo demanda              ║
║    • API Gateway     → Recibe las peticiones HTTP y las enruta       ║
║    • DynamoDB        → Almacena restaurantes y menús                 ║
║                                                                      ║
║  Comunicación con otros microservicios:                              ║
║    • El microservicio de Pedidos consulta este servicio para:        ║
║      - Obtener el menú de un restaurante (precios de platillos)      ║
║      - Validar que el restaurante existe al crear un pedido          ║
║                                                                      ║
║  Modelo de datos — Single-Table Design:                              ║
║  ──────────────────────────────────────                              ║
║  Tanto restaurantes como elementos del menú se almacenan en la       ║
║  MISMA tabla de DynamoDB, diferenciados por la Sort Key (SK):        ║
║                                                                      ║
║    ┌─────────────────────┬──────────────┬──────────────────┐         ║
║    │ PK                  │ SK           │ tipo_entidad     │         ║
║    ├─────────────────────┼──────────────┼──────────────────┤         ║
║    │ REST#<rest_id>      │ METADATA     │ restaurante      │         ║
║    │ REST#<rest_id>      │ MENU#<m_id>  │ elemento_menu    │         ║
║    │ REST#<rest_id>      │ MENU#<m_id>  │ elemento_menu    │         ║
║    └─────────────────────┴──────────────┴──────────────────┘         ║
║                                                                      ║
║  Ventaja: Obtener un restaurante con TODO su menú en una sola        ║
║  query por PK — O(1) en DynamoDB, sin necesidad de JOINs.           ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ════════════════════════════════════════════════════════════════
# Importaciones
# ════════════════════════════════════════════════════════════════

import json            # Serializar/deserializar JSON
import uuid            # Generar identificadores únicos (UUID v4)
import os              # Acceder a variables de entorno
from datetime import datetime   # Obtener fecha y hora actual
from decimal import Decimal     # Tipo numérico de precisión exacta (precios)

import boto3                              # SDK de AWS para Python
from boto3.dynamodb.conditions import Key  # Construir condiciones para queries DynamoDB


# ════════════════════════════════════════════════════════════════
# Configuración
# ════════════════════════════════════════════════════════════════

# Nombre de la tabla DynamoDB (definido en template.yaml)
NOMBRE_TABLA = os.environ.get("TABLA_RESTAURANTES", "ftgo-restaurantes")

# Conexión a DynamoDB (se reutiliza entre invocaciones Lambda — warm start)
dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)

# Headers CORS para permitir peticiones desde el frontend
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# ════════════════════════════════════════════════════════════════
# Función principal — Punto de entrada de la Lambda
# ════════════════════════════════════════════════════════════════
def lambda_handler(event, context):
    """
    Punto de entrada que AWS Lambda invoca en cada petición HTTP.

    Parámetros:
    ───────────
    event : dict
        Información de la petición HTTP desde API Gateway.
    context : LambdaContext
        Metadatos del entorno de ejecución Lambda.

    Retorna:
    ────────
    dict : Respuesta HTTP { statusCode, headers, body }

    Enrutamiento:
    ─────────────
    Este handler tiene el enrutamiento más complejo después de Pedidos
    porque maneja dos entidades (restaurantes y menú) con sub-rutas:

    ── Restaurantes ──
    - GET    /api/restaurantes              → Listar todos
    - POST   /api/restaurantes              → Crear restaurante
    - GET    /api/restaurantes/{id}         → Obtener uno
    - PUT    /api/restaurantes/{id}         → Actualizar
    - DELETE /api/restaurantes/{id}         → Eliminar (+ menú)

    ── Menú ──
    - POST   /api/restaurantes/{id}/menu    → Agregar platillo
    - GET    /api/restaurantes/{id}/menu    → Obtener menú
    - PUT    /api/restaurantes/menu/{elem}  → Actualizar platillo
    - DELETE /api/restaurantes/menu/{elem}  → Eliminar platillo

    ⚠️ El orden de las condiciones es CRÍTICO:
    Las rutas de menú (/menu/) se evalúan ANTES que las rutas genéricas
    de restaurante (/{id}) para evitar que "/menu" se interprete como un ID.
    """
    metodo = event["httpMethod"]
    # Usar 'path' (ruta real) para routing, no 'resource' (plantilla con {id})
    ruta = event.get("path", event.get("resource", ""))
    ruta_norm = ruta.rstrip("/")

    # Responder a preflight CORS
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        # ── Rutas de Restaurantes (colección) ──

        # GET /api/restaurantes → Listar todos los restaurantes
        if ruta_norm == "/api/restaurantes" and metodo == "GET":
            return listar_restaurantes()

        # POST /api/restaurantes → Crear un nuevo restaurante
        elif ruta_norm == "/api/restaurantes" and metodo == "POST":
            return crear_restaurante(json.loads(event["body"]))

        # ── Rutas de Menú (se evalúan ANTES que rutas de restaurante individual) ──

        # PUT /api/restaurantes/menu/{elemento_id} → Actualizar un platillo
        elif "/api/restaurantes/menu/" in ruta and metodo == "PUT":
            elemento_id = event.get("pathParameters", {}).get("elemento_id") or ruta.split("/")[-1]
            return actualizar_elemento_menu(elemento_id, json.loads(event["body"]))

        # DELETE /api/restaurantes/menu/{elemento_id} → Eliminar un platillo
        elif "/api/restaurantes/menu/" in ruta and metodo == "DELETE":
            elemento_id = event.get("pathParameters", {}).get("elemento_id") or ruta.split("/")[-1]
            return eliminar_elemento_menu(elemento_id)

        # POST /api/restaurantes/{id}/menu → Agregar platillo al menú
        elif "/api/restaurantes/" in ruta and "/menu" in ruta and metodo == "POST":
            rest_id = ruta.split("/api/restaurantes/")[1].split("/")[0]
            return agregar_elemento_menu(rest_id, json.loads(event["body"]))

        # GET /api/restaurantes/{id}/menu → Obtener menú completo
        elif "/api/restaurantes/" in ruta and "/menu" in ruta and metodo == "GET":
            rest_id = ruta.split("/api/restaurantes/")[1].split("/")[0]
            return obtener_menu(rest_id)

        # ── Rutas de Restaurante individual ──

        # GET /api/restaurantes/{id} → Obtener un restaurante
        elif "/api/restaurantes/" in ruta and metodo == "GET":
            rest_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/restaurantes/")[1].split("/")[0]
            return obtener_restaurante(rest_id)

        # PUT /api/restaurantes/{id} → Actualizar un restaurante
        elif "/api/restaurantes/" in ruta and metodo == "PUT":
            rest_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/restaurantes/")[1].split("/")[0]
            return actualizar_restaurante(rest_id, json.loads(event["body"]))

        # DELETE /api/restaurantes/{id} → Eliminar restaurante y su menú
        elif "/api/restaurantes/" in ruta and metodo == "DELETE":
            rest_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/restaurantes/")[1].split("/")[0]
            return eliminar_restaurante(rest_id)

        # Ruta no encontrada
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ════════════════════════════════════════════════════════════════
# CRUD de Restaurantes
# ════════════════════════════════════════════════════════════════

def crear_restaurante(datos):
    """
    Crea un nuevo restaurante en DynamoDB.

    Parámetros:
    ───────────
    datos : dict
        Datos del restaurante enviados en el body del POST:
        - nombre          (str, requerido) → Nombre del restaurante
        - direccion       (str, requerido) → Dirección física
        - telefono        (str, requerido) → Teléfono de contacto
        - tipo_cocina     (str, requerido) → Tipo de cocina (ej: "mexicana", "italiana")
        - horario_apertura (str, opcional) → Hora de apertura (default: "09:00")
        - horario_cierre   (str, opcional) → Hora de cierre (default: "22:00")

    Retorna:
    ────────
    dict : Respuesta HTTP 201 con los datos del restaurante creado (sin PK/SK),
           o 400 si faltan campos requeridos.

    Modelo de datos:
    ────────────────
    El restaurante se guarda con:
    - PK = "REST#<uuid>"  → Partition Key (agrupa restaurante + menú)
    - SK = "METADATA"     → Sort Key (identifica como datos del restaurante)
    - tipo_entidad = "restaurante" → Discriminador para scan/filter
    """
    # Validar campos requeridos
    campos_requeridos = ["nombre", "direccion", "telefono", "tipo_cocina"]
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo]:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    restaurante_id = str(uuid.uuid4())
    item = {
        "PK": f"REST#{restaurante_id}",             # Partition Key — agrupa con su menú
        "SK": "METADATA",                             # Sort Key — identifica como metadata
        "tipo_entidad": "restaurante",                # Discriminador de tipo
        "id": restaurante_id,                         # ID público del restaurante
        "nombre": datos["nombre"],                    # Nombre del restaurante
        "direccion": datos["direccion"],              # Dirección física
        "telefono": datos["telefono"],                # Teléfono de contacto
        "tipo_cocina": datos["tipo_cocina"],          # Tipo de cocina
        "horario_apertura": datos.get("horario_apertura", "09:00"),  # Default 09:00
        "horario_cierre": datos.get("horario_cierre", "22:00"),      # Default 22:00
        "fecha_registro": datetime.now().isoformat(),  # Timestamp ISO 8601
    }
    tabla.put_item(Item=item)

    # Devolver sin PK/SK (campos internos de DynamoDB que no se exponen al cliente)
    return respuesta(201, limpiar_item_restaurante(item))


def listar_restaurantes():
    """
    Lista todos los restaurantes (solo metadata, sin menús).

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con lista JSON de restaurantes.

    Implementación:
    ───────────────
    Usa scan() con FilterExpression para obtener solo items de tipo
    "restaurante" (SK="METADATA"), excluyendo los elementos del menú
    (SK="MENU#...") que también están en la misma tabla.
    """
    resultado = tabla.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("tipo_entidad").eq("restaurante")
    )
    restaurantes = [limpiar_item_restaurante(item) for item in resultado.get("Items", [])]
    return respuesta(200, restaurantes)


def obtener_restaurante(restaurante_id):
    """
    Obtiene un restaurante por su ID.

    Parámetros:
    ───────────
    restaurante_id : str
        UUID del restaurante a buscar.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con datos del restaurante (sin PK/SK),
           o 404 si no se encontró.

    Implementación:
    ───────────────
    get_item() con clave compuesta (PK + SK) busca directamente el
    item de metadata del restaurante. Es O(1) — la operación más
    eficiente en DynamoDB.
    """
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    item = resultado.get("Item")
    if not item:
        return respuesta(404, {"detail": "Restaurante no encontrado"})
    return respuesta(200, limpiar_item_restaurante(item))


def actualizar_restaurante(restaurante_id, datos):
    """
    Actualiza los datos de un restaurante existente.

    Parámetros:
    ───────────
    restaurante_id : str
        UUID del restaurante a actualizar.
    datos : dict
        Campos a actualizar (merge parcial con valores actuales).

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con datos actualizados, o 404 si no existe.
    """
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Restaurante no encontrado"})

    item_actual = resultado["Item"]

    # Actualizar con merge parcial (campos no enviados conservan su valor)
    tabla.update_item(
        Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"},
        UpdateExpression=(
            "SET nombre = :n, direccion = :d, telefono = :t, "
            "tipo_cocina = :tc, horario_apertura = :ha, horario_cierre = :hc"
        ),
        ExpressionAttributeValues={
            ":n": datos.get("nombre", item_actual["nombre"]),
            ":d": datos.get("direccion", item_actual["direccion"]),
            ":t": datos.get("telefono", item_actual["telefono"]),
            ":tc": datos.get("tipo_cocina", item_actual["tipo_cocina"]),
            ":ha": datos.get("horario_apertura", item_actual["horario_apertura"]),
            ":hc": datos.get("horario_cierre", item_actual["horario_cierre"]),
        },
    )

    actualizado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    return respuesta(200, limpiar_item_restaurante(actualizado["Item"]))


def eliminar_restaurante(restaurante_id):
    """
    Elimina un restaurante Y todos los elementos de su menú.

    Parámetros:
    ───────────
    restaurante_id : str
        UUID del restaurante a eliminar.

    Retorna:
    ────────
    dict : Respuesta HTTP 204 si se eliminó, o 404 si no existe.

    Implementación:
    ───────────────
    Como usamos single-table design, eliminar un restaurante requiere
    eliminar TODOS los items que comparten su PK:
    1. Query por PK = "REST#<id>" → obtiene metadata + todos los platillos
    2. Itera sobre cada item y lo elimina con delete_item()

    En SQL esto sería equivalente a:
      DELETE FROM restaurantes WHERE id = ?
      DELETE FROM menu WHERE restaurante_id = ?
    Pero en DynamoDB no hay CASCADE, así que lo hacemos manualmente.

    ⚠️ En producción con muchos platillos, se usaría BatchWriteItem
    para eliminar hasta 25 items por operación (más eficiente).
    """
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Restaurante no encontrado"})

    # Obtener TODOS los items con este PK (restaurante + platillos del menú)
    items = tabla.query(KeyConditionExpression=Key("PK").eq(f"REST#{restaurante_id}"))

    # Eliminar cada item individualmente
    for item in items.get("Items", []):
        tabla.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    return respuesta(204, None)


# ════════════════════════════════════════════════════════════════
# CRUD del Menú (Platillos)
# ════════════════════════════════════════════════════════════════

def agregar_elemento_menu(restaurante_id, datos):
    """
    Agrega un platillo al menú de un restaurante.

    Parámetros:
    ───────────
    restaurante_id : str
        UUID del restaurante al que se agrega el platillo.
    datos : dict
        Datos del platillo:
        - nombre      (str, requerido)   → Nombre del platillo (ej: "Tacos al pastor")
        - precio      (float, requerido) → Precio del platillo (ej: 85.50)
        - descripcion (str, opcional)    → Descripción del platillo
        - disponible  (int, opcional)    → 1 = disponible, 0 = agotado (default: 1)

    Retorna:
    ────────
    dict : Respuesta HTTP 201 con datos del platillo creado,
           o 400/404 si hay errores.

    Modelo de datos:
    ────────────────
    El platillo se guarda con:
    - PK = "REST#<restaurante_id>"  → Mismo PK que el restaurante (agrupación)
    - SK = "MENU#<menu_id>"         → Sort Key única para este platillo
    - tipo_entidad = "elemento_menu" → Discriminador de tipo

    Al compartir PK con el restaurante, una query por PK devuelve
    tanto el restaurante como todos sus platillos — single-table design.

    Nota sobre Decimal:
    ───────────────────
    El precio se convierte a Decimal(str(precio)) porque:
    1. DynamoDB requiere Decimal para números (no acepta float)
    2. str() intermedio evita errores de precisión:
       Decimal(0.1) = 0.1000000000000000055511151231257827021181583404541015625
       Decimal("0.1") = 0.1
    """
    # Verificar que el restaurante existe
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Restaurante no encontrado"})

    # Validar campos requeridos
    if "nombre" not in datos or "precio" not in datos:
        return respuesta(400, {"detail": "Se requiere 'nombre' y 'precio'"})

    menu_id = str(uuid.uuid4())
    item = {
        "PK": f"REST#{restaurante_id}",             # Mismo PK que el restaurante
        "SK": f"MENU#{menu_id}",                     # Sort Key única para este platillo
        "tipo_entidad": "elemento_menu",             # Discriminador de tipo
        "id": menu_id,                               # ID público del platillo
        "restaurante_id": restaurante_id,            # Referencia al restaurante padre
        "nombre": datos["nombre"],                   # Nombre del platillo
        "descripcion": datos.get("descripcion", ""),  # Descripción (opcional)
        "precio": Decimal(str(datos["precio"])),     # Precio como Decimal (precisión exacta)
        "disponible": datos.get("disponible", 1),    # 1 = disponible, 0 = agotado
    }
    tabla.put_item(Item=item)

    return respuesta(201, limpiar_item_menu(item))


def obtener_menu(restaurante_id):
    """
    Obtiene todos los platillos del menú de un restaurante.

    Parámetros:
    ───────────
    restaurante_id : str
        UUID del restaurante cuyo menú se quiere obtener.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con lista JSON de platillos.

    Implementación:
    ───────────────
    Usa query() con una condición compuesta:
    - PK = "REST#<restaurante_id>"  → Filtra por restaurante
    - SK begins_with "MENU#"        → Solo platillos (no METADATA)

    Esto es MUY eficiente en DynamoDB porque:
    1. La query por PK es O(1) para localizar la partición
    2. begins_with en SK filtra dentro de la partición sin scan
    3. Solo se leen los items del menú, no el restaurante

    El microservicio de Pedidos usa este endpoint para obtener
    los precios de los platillos al crear un pedido.
    """
    resultado = tabla.query(
        KeyConditionExpression=Key("PK").eq(f"REST#{restaurante_id}") & Key("SK").begins_with("MENU#")
    )
    platillos = [limpiar_item_menu(item) for item in resultado.get("Items", [])]
    return respuesta(200, platillos)


def actualizar_elemento_menu(elemento_id, datos):
    """
    Actualiza un platillo del menú.

    Parámetros:
    ───────────
    elemento_id : str
        UUID del platillo a actualizar.
    datos : dict
        Campos a actualizar (merge parcial):
        - nombre, descripcion, precio, disponible

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con datos actualizados, o 404 si no existe.

    Implementación:
    ───────────────
    ⚠️ Aquí hay un trade-off del single-table design:
    Para actualizar un platillo por su ID, necesitamos conocer su PK
    (que incluye el restaurante_id). Como solo tenemos el elemento_id,
    debemos hacer un scan() para encontrar el item completo.

    scan() con FilterExpression busca en toda la tabla — es O(n) y
    costoso. En producción se resolvería con:
    - Un GSI (Global Secondary Index) por elemento_id
    - Pasar el restaurante_id en la URL o body
    - Mantener un mapeo elemento_id → PK en otra tabla

    Para este ejemplo educativo, el scan es aceptable con pocos datos.
    """
    # Buscar el elemento por su ID (necesitamos el PK completo para update)
    resultado = tabla.scan(
        FilterExpression=(
            boto3.dynamodb.conditions.Attr("tipo_entidad").eq("elemento_menu")
            & boto3.dynamodb.conditions.Attr("id").eq(elemento_id)
        )
    )
    items = resultado.get("Items", [])
    if not items:
        return respuesta(404, {"detail": "Elemento del menú no encontrado"})

    item = items[0]

    # Actualizar con merge parcial
    tabla.update_item(
        Key={"PK": item["PK"], "SK": item["SK"]},
        UpdateExpression="SET nombre = :n, descripcion = :d, precio = :p, disponible = :disp",
        ExpressionAttributeValues={
            ":n": datos.get("nombre", item["nombre"]),
            ":d": datos.get("descripcion", item.get("descripcion", "")),
            ":p": Decimal(str(datos.get("precio", item["precio"]))),
            ":disp": datos.get("disponible", item.get("disponible", 1)),
        },
    )

    actualizado = tabla.get_item(Key={"PK": item["PK"], "SK": item["SK"]})
    return respuesta(200, limpiar_item_menu(actualizado["Item"]))


def eliminar_elemento_menu(elemento_id):
    """
    Elimina un platillo del menú.

    Parámetros:
    ───────────
    elemento_id : str
        UUID del platillo a eliminar.

    Retorna:
    ────────
    dict : Respuesta HTTP 204 si se eliminó, o 404 si no existe.

    Implementación:
    ───────────────
    Similar a actualizar_elemento_menu(), necesita un scan() para
    encontrar el PK completo del item antes de poder eliminarlo.
    """
    resultado = tabla.scan(
        FilterExpression=(
            boto3.dynamodb.conditions.Attr("tipo_entidad").eq("elemento_menu")
            & boto3.dynamodb.conditions.Attr("id").eq(elemento_id)
        )
    )
    items = resultado.get("Items", [])
    if not items:
        return respuesta(404, {"detail": "Elemento del menú no encontrado"})

    tabla.delete_item(Key={"PK": items[0]["PK"], "SK": items[0]["SK"]})
    return respuesta(204, None)


# ════════════════════════════════════════════════════════════════
# Utilidades — Limpieza de items de DynamoDB
# ════════════════════════════════════════════════════════════════

def limpiar_item_restaurante(item):
    """
    Remueve campos internos de DynamoDB y devuelve datos limpios del restaurante.

    Parámetros:
    ───────────
    item : dict
        Item crudo de DynamoDB con campos PK, SK, tipo_entidad.

    Retorna:
    ────────
    dict : Datos del restaurante sin campos internos de DynamoDB.
           Solo incluye los campos que el cliente del API necesita.

    Nota: PK, SK y tipo_entidad son campos de infraestructura necesarios
    para el single-table design de DynamoDB, pero no tienen significado
    para el consumidor del API — por eso se "limpian" antes de responder.
    """
    return {
        "id": item["id"],
        "nombre": item["nombre"],
        "direccion": item["direccion"],
        "telefono": item["telefono"],
        "tipo_cocina": item["tipo_cocina"],
        "horario_apertura": item.get("horario_apertura", "09:00"),
        "horario_cierre": item.get("horario_cierre", "22:00"),
        "fecha_registro": item.get("fecha_registro", ""),
    }


def limpiar_item_menu(item):
    """
    Remueve campos internos de DynamoDB para elementos del menú.

    Parámetros:
    ───────────
    item : dict
        Item crudo de DynamoDB con campos PK, SK, tipo_entidad.

    Retorna:
    ────────
    dict : Datos del platillo sin campos internos.
           El precio se convierte de Decimal a float para JSON.
           El campo disponible se convierte de Decimal a int.
    """
    return {
        "id": item["id"],
        "restaurante_id": item["restaurante_id"],
        "nombre": item["nombre"],
        "descripcion": item.get("descripcion", ""),
        "precio": float(item["precio"]),           # Decimal → float para JSON
        "disponible": int(item.get("disponible", 1)),  # Decimal → int
    }


def respuesta(codigo_estado, cuerpo):
    """
    Construye el diccionario de respuesta HTTP que Lambda devuelve a API Gateway.

    Parámetros:
    ───────────
    codigo_estado : int
        Código HTTP (200, 201, 204, 400, 404, 500).
    cuerpo : dict | list | None
        Datos a serializar como JSON. None produce body vacío.

    Retorna:
    ────────
    dict : { "statusCode": int, "headers": dict, "body": str }
    """
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo is not None else "",
    }
