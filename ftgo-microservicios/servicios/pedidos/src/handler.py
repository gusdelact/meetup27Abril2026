"""
Handler Lambda — Microservicio de Pedidos (Order Management Service).

╔══════════════════════════════════════════════════════════════════════╗
║  MICROSERVICIO DE PEDIDOS — FTGO (Food To Go Online)               ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Responsabilidad:                                                    ║
║    Gestionar todo el ciclo de vida de un pedido: creación,           ║
║    cambio de estado, asignación de repartidor y cancelación.         ║
║    Este es el microservicio MÁS COMPLEJO del sistema porque          ║
║    orquesta la comunicación con los demás servicios.                 ║
║                                                                      ║
║  Operaciones expuestas:                                              ║
║    POST   /api/pedidos/                    → Crear nuevo pedido      ║
║    GET    /api/pedidos/                    → Listar todos            ║
║    GET    /api/pedidos/{id}                → Obtener uno por ID      ║
║    PUT    /api/pedidos/{id}/estado         → Cambiar estado          ║
║    PUT    /api/pedidos/{id}/repartidor     → Asignar repartidor     ║
║    DELETE /api/pedidos/{id}                → Cancelar pedido         ║
║                                                                      ║
║  Infraestructura AWS:                                                ║
║    • AWS Lambda      → Ejecuta este código bajo demanda              ║
║    • API Gateway     → Recibe las peticiones HTTP y las enruta       ║
║    • DynamoDB        → Almacena pedidos y sus elementos              ║
║                                                                      ║
║  Comunicación con otros microservicios (síncrona vía HTTP):          ║
║    • Consumidores → Valida que el consumidor exista (al crear)       ║
║    • Restaurantes → Obtiene el menú y precios (al crear)             ║
║    • Entregas     → Verifica disponibilidad del repartidor           ║
║    • Pagos        → Pagos consulta este servicio para obtener total  ║
║                                                                      ║
║  Modelo de datos en DynamoDB (Single-Table Design):                  ║
║    Este servicio usa "single-table design" donde pedidos y sus       ║
║    elementos se almacenan en la misma tabla, diferenciados por       ║
║    la Sort Key (SK):                                                 ║
║      • Pedido:   PK="PED#<id>", SK="METADATA"                       ║
║      • Elemento: PK="PED#<id>", SK="ELEM#<elem_id>"                 ║
║    Esto permite obtener un pedido con todos sus elementos en una     ║
║    sola query por PK — muy eficiente en DynamoDB.                    ║
║                                                                      ║
║  Máquina de estados del pedido:                                      ║
║    CREADO → ACEPTADO → PREPARANDO → LISTO → EN_CAMINO → ENTREGADO   ║
║       ↓        ↓           ↓                                         ║
║    CANCELADO CANCELADO  CANCELADO                                    ║
║    (No se puede cancelar si está EN_CAMINO o ENTREGADO)              ║
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
from decimal import Decimal     # Tipo numérico de precisión exacta (requerido por DynamoDB)

import boto3                              # SDK de AWS para Python
from boto3.dynamodb.conditions import Key  # Construir condiciones para queries DynamoDB
import urllib.request                      # Cliente HTTP estándar de Python (sin dependencias externas)


# ════════════════════════════════════════════════════════════════
# Configuración
# ════════════════════════════════════════════════════════════════

# Nombre de la tabla DynamoDB (definido en template.yaml)
NOMBRE_TABLA = os.environ.get("TABLA_PEDIDOS", "ftgo-pedidos")

# URLs de los otros microservicios — se configuran como variables de
# entorno en template.yaml. Cada URL apunta al API Gateway del servicio.
# Ejemplo: "https://abc123.execute-api.us-east-1.amazonaws.com/Prod"
API_CONSUMIDORES = os.environ.get("API_CONSUMIDORES_URL", "")  # Servicio de Consumidores
API_RESTAURANTES = os.environ.get("API_RESTAURANTES_URL", "")  # Servicio de Restaurantes
API_ENTREGAS = os.environ.get("API_ENTREGAS_URL", "")          # Servicio de Entregas

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
# Máquina de estados — Transiciones válidas del pedido
# ════════════════════════════════════════════════════════════════
# Define qué cambios de estado son permitidos desde cada estado.
# Esto implementa el patrón "State Machine" que garantiza que un
# pedido siga un flujo lógico y no salte estados arbitrariamente.
#
# Ejemplo: Un pedido en estado "CREADO" solo puede pasar a
# "ACEPTADO" o "CANCELADO", nunca directamente a "ENTREGADO".
#
# Los estados terminales (ENTREGADO, CANCELADO) tienen lista vacía
# porque no pueden transicionar a ningún otro estado.
TRANSICIONES_VALIDAS = {
    "CREADO": ["ACEPTADO", "CANCELADO"],       # Recién creado → aceptar o cancelar
    "ACEPTADO": ["PREPARANDO", "CANCELADO"],   # Aceptado → empezar a preparar o cancelar
    "PREPARANDO": ["LISTO", "CANCELADO"],      # En preparación → listo o cancelar
    "LISTO": ["EN_CAMINO"],                    # Listo → asignar repartidor y enviar
    "EN_CAMINO": ["ENTREGADO"],                # En camino → marcar como entregado
    "ENTREGADO": [],                           # Estado terminal — pedido completado
    "CANCELADO": [],                           # Estado terminal — pedido cancelado
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
    Este handler tiene un enrutamiento más complejo que los demás servicios
    porque maneja sub-rutas como /estado y /repartidor:

    - GET    /api/pedidos                    → Listar todos
    - POST   /api/pedidos                    → Crear pedido
    - PUT    /api/pedidos/{id}/estado        → Cambiar estado
    - PUT    /api/pedidos/{id}/repartidor    → Asignar repartidor
    - GET    /api/pedidos/{id}               → Obtener pedido con elementos
    - DELETE /api/pedidos/{id}               → Cancelar pedido

    El orden de las condiciones importa: las rutas más específicas
    (/estado, /repartidor) se evalúan ANTES que la ruta genérica /{id}
    para evitar que se capturen incorrectamente.
    """
    metodo = event["httpMethod"]
    ruta = event.get("path", event.get("resource", ""))
    ruta_norm = ruta.rstrip("/")

    # Responder a preflight CORS
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        # GET /api/pedidos → Listar todos los pedidos
        if ruta_norm == "/api/pedidos" and metodo == "GET":
            return listar_pedidos()

        # POST /api/pedidos → Crear un nuevo pedido
        elif ruta_norm == "/api/pedidos" and metodo == "POST":
            return crear_pedido(json.loads(event["body"]))

        # PUT /api/pedidos/{id}/estado → Cambiar estado del pedido
        # ⚠️ Esta ruta se evalúa ANTES que GET/DELETE /{id} porque
        # contiene "/estado" como sub-ruta
        elif "/api/pedidos/" in ruta and "/estado" in ruta and metodo == "PUT":
            # Extraer el ID del pedido de la URL:
            # "/api/pedidos/abc-123/estado" → split por "/api/pedidos/" → "abc-123/estado"
            # → split por "/" → ["abc-123", "estado"] → [0] = "abc-123"
            pedido_id = ruta.split("/api/pedidos/")[1].split("/")[0]
            return actualizar_estado(pedido_id, json.loads(event["body"]))

        # PUT /api/pedidos/{id}/repartidor → Asignar repartidor al pedido
        elif "/api/pedidos/" in ruta and "/repartidor" in ruta and metodo == "PUT":
            pedido_id = ruta.split("/api/pedidos/")[1].split("/")[0]
            return asignar_repartidor(pedido_id, json.loads(event["body"]))

        # GET /api/pedidos/{id} → Obtener un pedido con sus elementos
        elif "/api/pedidos/" in ruta and metodo == "GET":
            pedido_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/pedidos/")[1].split("/")[0]
            return obtener_pedido(pedido_id)

        # DELETE /api/pedidos/{id} → Cancelar un pedido
        elif "/api/pedidos/" in ruta and metodo == "DELETE":
            pedido_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/pedidos/")[1].split("/")[0]
            return cancelar_pedido(pedido_id)

        # Ruta no encontrada
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ════════════════════════════════════════════════════════════════
# Comunicación con otros microservicios
# ════════════════════════════════════════════════════════════════

def llamar_servicio(url):
    """
    Hace una petición HTTP GET a otro microservicio.

    Parámetros:
    ───────────
    url : str
        URL completa del endpoint a consultar.
        Ejemplo: "https://abc123.execute-api.us-east-1.amazonaws.com/Prod/api/consumidores/uuid-123"

    Retorna:
    ────────
    dict | list | None
        - dict/list → Respuesta JSON parseada del servicio remoto
        - None      → Si la petición falló (timeout, error de red, 404, etc.)

    Implementación:
    ───────────────
    En microservicios, los servicios se comunican entre sí por HTTP.
    Esta función implementa comunicación SÍNCRONA: el servicio que llama
    se queda esperando la respuesta del servicio remoto.

    Se usa urllib.request (librería estándar de Python) en vez de la
    librería 'requests' para evitar dependencias externas en la Lambda.
    Esto reduce el tamaño del paquete de despliegue y el cold start.

    El timeout de 10 segundos evita que la Lambda se quede bloqueada
    indefinidamente si el servicio remoto no responde.

    Alternativas en arquitecturas más avanzadas:
    - Comunicación asíncrona con Amazon SQS (colas de mensajes)
    - Eventos con Amazon EventBridge
    - Orquestación con AWS Step Functions
    """
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except Exception as error:
        print(f"Error llamando a {url}: {error}")
    return None


# ════════════════════════════════════════════════════════════════
# CRUD de Pedidos
# ════════════════════════════════════════════════════════════════

def crear_pedido(datos):
    """
    Crea un nuevo pedido — la operación más compleja del sistema.

    Parámetros:
    ───────────
    datos : dict
        Datos del pedido enviados en el body del POST:
        - consumidor_id    (str, requerido) → UUID del consumidor que hace el pedido
        - restaurante_id   (str, requerido) → UUID del restaurante
        - direccion_entrega (str, requerido) → Dirección donde entregar
        - elementos        (list, requerido) → Lista de platillos a pedir:
            [
                {"elemento_menu_id": "uuid-platillo", "cantidad": 2},
                {"elemento_menu_id": "uuid-otro", "cantidad": 1}
            ]

    Retorna:
    ────────
    dict : Respuesta HTTP 201 con el pedido creado (incluyendo total calculado),
           o 400/404 si hay errores de validación.

    Flujo detallado (orquestación entre microservicios):
    ────────────────────────────────────────────────────
    1. VALIDACIÓN DE ENTRADA
       Verifica que todos los campos requeridos estén presentes y que
       haya al menos un elemento en el pedido.

    2. VALIDAR CONSUMIDOR (llamada HTTP → Microservicio de Consumidores)
       Hace GET /api/consumidores/{id} para verificar que el consumidor
       existe. Si no existe, devuelve 404.

    3. OBTENER MENÚ DEL RESTAURANTE (llamada HTTP → Microservicio de Restaurantes)
       Hace GET /api/restaurantes/{id}/menu/ para obtener la lista de
       platillos con sus precios. Esto permite calcular el total del pedido
       con precios actualizados del restaurante.

    4. CALCULAR TOTAL Y GUARDAR ELEMENTOS
       Para cada elemento del pedido:
       a. Busca el platillo en el menú del restaurante
       b. Obtiene su precio actual
       c. Calcula subtotal = precio × cantidad
       d. Acumula el total general
       e. Guarda el elemento en DynamoDB con SK="ELEM#<id>"

    5. GUARDAR PEDIDO PRINCIPAL
       Guarda el registro del pedido en DynamoDB con SK="METADATA"
       y estado inicial "CREADO".

    Modelo de datos (Single-Table Design):
    ──────────────────────────────────────
    Todos los items de un pedido comparten el mismo PK (Partition Key):
      PK = "PED#<pedido_id>"

    Pero tienen diferentes SK (Sort Key):
      SK = "METADATA"       → Datos del pedido (estado, total, fechas)
      SK = "ELEM#<elem_id>" → Cada elemento/platillo del pedido

    Esto permite obtener TODO el pedido (metadata + elementos) con una
    sola query por PK, lo cual es O(1) en DynamoDB — muy eficiente.

    Uso de Decimal:
    ───────────────
    Los precios se manejan como Decimal (no float) porque:
    - float tiene errores de redondeo: 0.1 + 0.2 = 0.30000000000000004
    - Decimal tiene precisión exacta: Decimal("0.1") + Decimal("0.2") = Decimal("0.3")
    - DynamoDB almacena números como Decimal internamente
    """
    # ── Paso 1: Validar campos requeridos ──
    campos_requeridos = ["consumidor_id", "restaurante_id", "direccion_entrega", "elementos"]
    for campo in campos_requeridos:
        if campo not in datos:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    if not datos["elementos"]:
        return respuesta(400, {"detail": "El pedido debe tener al menos un elemento"})

    # ── Paso 2: Validar consumidor (llamada inter-servicio) ──
    # Comunicación síncrona: Pedidos → Consumidores (HTTP GET)
    if API_CONSUMIDORES:
        consumidor = llamar_servicio(
            f"{API_CONSUMIDORES}/api/consumidores/{datos['consumidor_id']}"
        )
        if not consumidor:
            return respuesta(404, {"detail": "Consumidor no encontrado"})

    # ── Paso 3: Obtener menú del restaurante (llamada inter-servicio) ──
    # Comunicación síncrona: Pedidos → Restaurantes (HTTP GET)
    menu = []
    if API_RESTAURANTES:
        menu = llamar_servicio(
            f"{API_RESTAURANTES}/api/restaurantes/{datos['restaurante_id']}/menu/"
        )
        if menu is None:
            return respuesta(404, {"detail": "Restaurante no encontrado"})

    # ── Paso 4: Calcular total y guardar elementos ──
    pedido_id = str(uuid.uuid4())
    total = Decimal("0")
    elementos_guardados = []

    for elem in datos["elementos"]:
        elemento_menu_id = elem["elemento_menu_id"]
        cantidad = elem.get("cantidad", 1)  # Default: 1 unidad

        # Buscar el precio del platillo en el menú del restaurante
        # next() con generador busca el primer platillo que coincida por ID
        platillo = next((p for p in menu if p["id"] == elemento_menu_id), None)
        if platillo:
            precio = Decimal(str(platillo["precio"]))
        else:
            # Si no se puede validar el menú (ej: API_RESTAURANTES vacío),
            # usar precio 0 — en producción esto sería un error
            precio = Decimal("0")

        subtotal = precio * cantidad
        total += subtotal

        # Guardar el elemento del pedido en DynamoDB
        # PK = "PED#<pedido_id>" (mismo que el pedido principal)
        # SK = "ELEM#<elem_id>" (diferencia este item del METADATA)
        elem_id = str(uuid.uuid4())
        elemento_item = {
            "PK": f"PED#{pedido_id}",           # Partition Key — agrupa con el pedido
            "SK": f"ELEM#{elem_id}",             # Sort Key — identifica este elemento
            "tipo_entidad": "elemento_pedido",   # Discriminador de tipo (para scan/filter)
            "id": elem_id,                       # ID propio del elemento
            "pedido_id": pedido_id,              # Referencia al pedido padre
            "elemento_menu_id": elemento_menu_id,  # Referencia al platillo del menú
            "cantidad": cantidad,                # Cantidad pedida
            "precio_unitario": precio,           # Precio al momento del pedido
            "subtotal": subtotal,                # precio × cantidad
        }
        tabla.put_item(Item=elemento_item)

        # Acumular para la respuesta (con float en vez de Decimal para JSON)
        elementos_guardados.append({
            "id": elem_id,
            "elemento_menu_id": elemento_menu_id,
            "cantidad": cantidad,
            "precio_unitario": float(precio),
            "subtotal": float(subtotal),
        })

    # ── Paso 5: Guardar el pedido principal ──
    ahora = datetime.now().isoformat()
    pedido_item = {
        "PK": f"PED#{pedido_id}",                # Partition Key
        "SK": "METADATA",                         # Sort Key — identifica como metadata del pedido
        "tipo_entidad": "pedido",                 # Discriminador de tipo
        "id": pedido_id,                          # ID del pedido (UUID)
        "consumidor_id": datos["consumidor_id"],  # Quién hizo el pedido
        "restaurante_id": datos["restaurante_id"],  # De qué restaurante
        "repartidor_id": None,                    # Aún no asignado (se asigna después)
        "estado": "CREADO",                       # Estado inicial de la máquina de estados
        "total": total,                           # Total calculado (Decimal)
        "direccion_entrega": datos["direccion_entrega"],
        "fecha_creacion": ahora,                  # Timestamp de creación
        "fecha_actualizacion": ahora,             # Timestamp de última actualización
    }
    tabla.put_item(Item=pedido_item)

    # Devolver el pedido creado con sus elementos
    return respuesta(201, {
        "id": pedido_id,
        "consumidor_id": datos["consumidor_id"],
        "restaurante_id": datos["restaurante_id"],
        "repartidor_id": None,
        "estado": "CREADO",
        "total": float(total),
        "direccion_entrega": datos["direccion_entrega"],
        "fecha_creacion": ahora,
        "fecha_actualizacion": ahora,
        "elementos": elementos_guardados,
    })


def listar_pedidos():
    """
    Lista todos los pedidos (solo metadata, sin elementos individuales).

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con lista JSON de todos los pedidos.

    Implementación:
    ───────────────
    Usa scan() con FilterExpression para obtener solo los items de tipo
    "pedido" (SK="METADATA"), excluyendo los elementos individuales
    (SK="ELEM#..."). Esto es necesario porque ambos tipos de items
    están en la misma tabla (single-table design).

    Attr("tipo_entidad").eq("pedido") filtra del lado del servidor,
    pero DynamoDB aún lee toda la tabla internamente (scan es O(n)).
    En producción con muchos pedidos se usaría un GSI o paginación.
    """
    resultado = tabla.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("tipo_entidad").eq("pedido")
    )
    pedidos = []
    for item in resultado.get("Items", []):
        pedidos.append(limpiar_pedido(item))
    return respuesta(200, pedidos)


def obtener_pedido(pedido_id):
    """
    Obtiene un pedido completo con todos sus elementos.

    Parámetros:
    ───────────
    pedido_id : str
        UUID del pedido a buscar.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con el pedido y sus elementos,
           o 404 si no se encontró.

    Implementación (Single-Table Query):
    ────────────────────────────────────
    Usa query() con KeyConditionExpression para obtener TODOS los items
    que comparten el mismo PK = "PED#<pedido_id>".

    Esto devuelve en una sola operación:
    - El item con SK="METADATA" → datos del pedido
    - Los items con SK="ELEM#..." → elementos/platillos del pedido

    Luego separamos los items por tipo de SK:
    - SK == "METADATA" → es el pedido principal
    - SK.startswith("ELEM#") → es un elemento del pedido

    Esta es la ventaja principal del single-table design: obtener
    datos relacionados en una sola query en vez de múltiples queries
    o JOINs (que no existen en DynamoDB).
    """
    # Query por PK — obtiene pedido + todos sus elementos en una operación
    resultado = tabla.query(
        KeyConditionExpression=Key("PK").eq(f"PED#{pedido_id}")
    )
    items = resultado.get("Items", [])

    if not items:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    # Separar metadata del pedido y elementos individuales
    pedido = None
    elementos = []
    for item in items:
        if item["SK"] == "METADATA":
            # Este item es el pedido principal
            pedido = limpiar_pedido(item)
        elif item["SK"].startswith("ELEM#"):
            # Este item es un elemento/platillo del pedido
            elementos.append({
                "id": item["id"],
                "elemento_menu_id": item["elemento_menu_id"],
                "cantidad": int(item["cantidad"]),
                "precio_unitario": float(item["precio_unitario"]),
                "subtotal": float(item["subtotal"]),
            })

    if not pedido:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    # Adjuntar los elementos al pedido
    pedido["elementos"] = elementos
    return respuesta(200, pedido)


def actualizar_estado(pedido_id, datos):
    """
    Cambia el estado de un pedido validando la máquina de estados.

    Parámetros:
    ───────────
    pedido_id : str
        UUID del pedido a actualizar.
    datos : dict
        Debe contener:
        - estado (str, requerido) → Nuevo estado deseado (ej: "ACEPTADO")

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con el pedido actualizado,
           o 400 si la transición no es válida, o 404 si no existe.

    Validación de la máquina de estados:
    ────────────────────────────────────
    Antes de cambiar el estado, se verifica que la transición sea válida
    consultando el diccionario TRANSICIONES_VALIDAS.

    Ejemplo:
    - Estado actual: "CREADO" → Permitidos: ["ACEPTADO", "CANCELADO"]
    - Si se intenta cambiar a "ENTREGADO" → Error 400 con mensaje explicativo
    - Si se intenta cambiar a "ACEPTADO" → OK, se actualiza

    Esto previene estados inconsistentes como:
    - Un pedido que pasa de "CREADO" directamente a "ENTREGADO"
    - Un pedido "ENTREGADO" que se vuelve a poner en "PREPARANDO"
    """
    if "estado" not in datos:
        return respuesta(400, {"detail": "El campo 'estado' es requerido"})

    # Obtener el pedido actual de DynamoDB
    resultado = tabla.get_item(Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = resultado["Item"]
    estado_actual = pedido["estado"]
    nuevo_estado = datos["estado"].upper()  # Normalizar a mayúsculas

    # Validar que la transición sea permitida
    estados_permitidos = TRANSICIONES_VALIDAS.get(estado_actual, [])
    if nuevo_estado not in estados_permitidos:
        return respuesta(400, {
            "detail": f"No se puede cambiar de '{estado_actual}' a '{nuevo_estado}'. "
                      f"Estados permitidos: {estados_permitidos}"
        })

    # Actualizar estado y timestamp en DynamoDB
    ahora = datetime.now().isoformat()
    tabla.update_item(
        Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"},
        UpdateExpression="SET estado = :e, fecha_actualizacion = :f",
        ExpressionAttributeValues={":e": nuevo_estado, ":f": ahora},
    )

    pedido["estado"] = nuevo_estado
    pedido["fecha_actualizacion"] = ahora
    return respuesta(200, limpiar_pedido(pedido))


def asignar_repartidor(pedido_id, datos):
    """
    Asigna un repartidor a un pedido — comunicación Pedidos → Entregas.

    Parámetros:
    ───────────
    pedido_id : str
        UUID del pedido al que se asignará el repartidor.
    datos : dict
        Debe contener:
        - repartidor_id (str, requerido) → UUID del repartidor a asignar

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con el pedido actualizado,
           o 400/404 si hay errores.

    Flujo:
    ──────
    1. Valida que el pedido exista y esté en estado "LISTO"
       (solo se puede asignar repartidor cuando la comida está lista)
    2. Llama al microservicio de Entregas (HTTP GET) para:
       a. Verificar que el repartidor existe
       b. Verificar que está disponible (disponible == 1)
    3. Actualiza el pedido con el repartidor_id asignado

    Comunicación inter-servicio:
    ───────────────────────────
    Este es un ejemplo de cómo un microservicio (Pedidos) consulta
    a otro (Entregas) para validar datos antes de una operación.
    En una arquitectura más avanzada, también se actualizaría la
    disponibilidad del repartidor (PUT con disponible=0).
    """
    if "repartidor_id" not in datos:
        return respuesta(400, {"detail": "El campo 'repartidor_id' es requerido"})

    # Verificar que el pedido existe
    resultado = tabla.get_item(Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = resultado["Item"]

    # Validar que el pedido esté en estado LISTO
    if pedido["estado"] != "LISTO":
        return respuesta(400, {
            "detail": "Solo se puede asignar repartidor a pedidos en estado LISTO"
        })

    repartidor_id = datos["repartidor_id"]

    # Verificar repartidor en el microservicio de Entregas (HTTP GET)
    if API_ENTREGAS:
        repartidor = llamar_servicio(
            f"{API_ENTREGAS}/api/repartidores/{repartidor_id}"
        )
        if not repartidor:
            return respuesta(404, {"detail": "Repartidor no encontrado"})
        if not repartidor.get("disponible"):
            return respuesta(400, {"detail": "El repartidor no está disponible"})

    # Actualizar el pedido con el repartidor asignado
    ahora = datetime.now().isoformat()
    tabla.update_item(
        Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"},
        UpdateExpression="SET repartidor_id = :r, fecha_actualizacion = :f",
        ExpressionAttributeValues={":r": repartidor_id, ":f": ahora},
    )

    pedido["repartidor_id"] = repartidor_id
    pedido["fecha_actualizacion"] = ahora
    return respuesta(200, limpiar_pedido(pedido))


def cancelar_pedido(pedido_id):
    """
    Cancela un pedido cambiando su estado a "CANCELADO".

    Parámetros:
    ───────────
    pedido_id : str
        UUID del pedido a cancelar.

    Retorna:
    ────────
    dict : Respuesta HTTP 204 (No Content) si se canceló,
           o 400 si el pedido no se puede cancelar, o 404 si no existe.

    Reglas de negocio:
    ──────────────────
    - Un pedido EN_CAMINO no se puede cancelar (el repartidor ya salió)
    - Un pedido ENTREGADO no se puede cancelar (ya se completó)
    - Cualquier otro estado sí permite cancelación
    """
    resultado = tabla.get_item(Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = resultado["Item"]

    # Validar que el pedido se pueda cancelar
    if pedido["estado"] in ["EN_CAMINO", "ENTREGADO"]:
        return respuesta(400, {
            "detail": "No se puede cancelar un pedido en camino o ya entregado"
        })

    # Cambiar estado a CANCELADO
    ahora = datetime.now().isoformat()
    tabla.update_item(
        Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"},
        UpdateExpression="SET estado = :e, fecha_actualizacion = :f",
        ExpressionAttributeValues={":e": "CANCELADO", ":f": ahora},
    )
    return respuesta(204, None)


# ════════════════════════════════════════════════════════════════
# Utilidades
# ════════════════════════════════════════════════════════════════

def limpiar_pedido(item):
    """
    Convierte un item de DynamoDB a formato de respuesta limpio.

    Parámetros:
    ───────────
    item : dict
        Item crudo de DynamoDB que incluye campos internos como
        PK, SK, tipo_entidad que no deben exponerse al cliente.

    Retorna:
    ────────
    dict : Datos del pedido sin campos internos de DynamoDB.
           El campo 'total' se convierte de Decimal a float.
           El campo 'elementos' se inicializa como lista vacía
           (se llena después si se consultan los elementos).

    Nota: Esta función "limpia" la respuesta removiendo los campos
    de infraestructura (PK, SK, tipo_entidad) que son necesarios
    para DynamoDB pero no tienen significado para el cliente del API.
    """
    return {
        "id": item["id"],
        "consumidor_id": item.get("consumidor_id", ""),
        "restaurante_id": item.get("restaurante_id", ""),
        "repartidor_id": item.get("repartidor_id"),
        "estado": item["estado"],
        "total": float(item.get("total", 0)),
        "direccion_entrega": item.get("direccion_entrega", ""),
        "fecha_creacion": item.get("fecha_creacion", ""),
        "fecha_actualizacion": item.get("fecha_actualizacion", ""),
        "elementos": [],
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
