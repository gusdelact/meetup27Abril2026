"""
Handler Lambda — Microservicio de Entregas / Repartidores (Delivery Service).

╔══════════════════════════════════════════════════════════════════════╗
║  MICROSERVICIO DE ENTREGAS — FTGO (Food To Go Online)              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Responsabilidad:                                                    ║
║    Gestionar los repartidores que entregan los pedidos a los         ║
║    consumidores. Controla su registro, datos y disponibilidad.       ║
║                                                                      ║
║  Operaciones CRUD expuestas:                                         ║
║    POST   /api/repartidores/          → Registrar nuevo repartidor   ║
║    GET    /api/repartidores/          → Listar todos                 ║
║    GET    /api/repartidores/{id}      → Obtener uno por ID           ║
║    PUT    /api/repartidores/{id}      → Actualizar datos/disponib.   ║
║    DELETE /api/repartidores/{id}      → Eliminar repartidor          ║
║                                                                      ║
║  Infraestructura AWS:                                                ║
║    • AWS Lambda      → Ejecuta este código bajo demanda              ║
║    • API Gateway     → Recibe las peticiones HTTP y las enruta       ║
║    • DynamoDB        → Base de datos NoSQL para persistencia         ║
║                                                                      ║
║  Comunicación con otros microservicios:                              ║
║    • El microservicio de Pedidos consulta este servicio para:        ║
║      - Verificar que un repartidor existe antes de asignarlo         ║
║      - Comprobar su disponibilidad (campo 'disponible')              ║
║    • El microservicio de Pedidos también puede actualizar la         ║
║      disponibilidad del repartidor (PUT) al asignarle un pedido.    ║
║                                                                      ║
║  Campo 'disponible':                                                 ║
║    • 1 = El repartidor está libre y puede recibir pedidos            ║
║    • 0 = El repartidor está ocupado entregando un pedido             ║
║    DynamoDB almacena números como tipo Decimal de Python, por eso    ║
║    se convierte a int antes de devolver en las respuestas JSON.      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ════════════════════════════════════════════════════════════════
# Importaciones
# ════════════════════════════════════════════════════════════════

import json       # Serializar/deserializar JSON (formato de intercambio de datos)
import uuid       # Generar identificadores únicos universales (UUID v4)
import os         # Acceder a variables de entorno del sistema operativo
from datetime import datetime  # Obtener la fecha y hora actual

import boto3      # SDK de AWS para Python — permite interactuar con DynamoDB


# ════════════════════════════════════════════════════════════════
# Configuración de DynamoDB
# ════════════════════════════════════════════════════════════════

# El nombre de la tabla viene de una variable de entorno definida en
# template.yaml (infraestructura como código con AWS SAM).
# Si la variable no existe, usa un valor por defecto para desarrollo local.
NOMBRE_TABLA = os.environ.get("TABLA_REPARTIDORES", "ftgo-repartidores")

# Crear el recurso de DynamoDB y obtener referencia a la tabla.
# Estas líneas se ejecutan UNA sola vez cuando Lambda carga el módulo
# (cold start). En invocaciones posteriores (warm start), se reutiliza
# la conexión existente — esto mejora el rendimiento significativamente.
dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)

# ════════════════════════════════════════════════════════════════
# Headers CORS (Cross-Origin Resource Sharing)
# ════════════════════════════════════════════════════════════════
# Permiten que el frontend (servido desde otro dominio/origen) pueda
# hacer peticiones HTTP a este API sin ser bloqueado por el navegador.
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
        Contiene toda la información de la petición HTTP enviada por
        API Gateway. Campos principales:
        - event['httpMethod']      → Método HTTP (GET, POST, PUT, DELETE, OPTIONS)
        - event['path']            → Ruta real solicitada (ej: "/api/repartidores/abc-123")
        - event['pathParameters']  → Parámetros extraídos de la URL (ej: {"id": "abc-123"})
        - event['body']            → Cuerpo de la petición como string JSON

    context : LambdaContext
        Metadatos del entorno de ejecución Lambda (nombre, memoria, timeout, etc.).

    Retorna:
    ────────
    dict : Respuesta HTTP con formato que API Gateway entiende:
        { "statusCode": int, "headers": dict, "body": str }

    Flujo de enrutamiento:
    ──────────────────────
    1. Extrae método HTTP y ruta de la petición
    2. Normaliza la ruta (quita trailing slash)
    3. OPTIONS → responde con CORS headers (preflight del navegador)
    4. Delega a la función CRUD según método + ruta
    5. Ruta no encontrada → 404 | Error inesperado → 500
    """
    # Extraer método HTTP y ruta de la petición
    metodo = event["httpMethod"]
    ruta = event.get("path", event.get("resource", ""))
    ruta_norm = ruta.rstrip("/")  # Normalizar: "/api/repartidores/" → "/api/repartidores"

    # Responder a preflight CORS (el navegador envía OPTIONS antes de POST/PUT/DELETE)
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        # ── Enrutamiento por método HTTP + ruta ──

        # GET /api/repartidores → Listar todos los repartidores
        if ruta_norm == "/api/repartidores" and metodo == "GET":
            return listar_repartidores()

        # POST /api/repartidores → Registrar un nuevo repartidor
        elif ruta_norm == "/api/repartidores" and metodo == "POST":
            return crear_repartidor(json.loads(event["body"]))

        # GET /api/repartidores/{id} → Obtener un repartidor por ID
        elif "/api/repartidores/" in ruta and metodo == "GET":
            rep_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return obtener_repartidor(rep_id)

        # PUT /api/repartidores/{id} → Actualizar datos o disponibilidad
        elif "/api/repartidores/" in ruta and metodo == "PUT":
            rep_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return actualizar_repartidor(rep_id, json.loads(event["body"]))

        # DELETE /api/repartidores/{id} → Eliminar un repartidor
        elif "/api/repartidores/" in ruta and metodo == "DELETE":
            rep_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return eliminar_repartidor(rep_id)

        # Ninguna ruta coincidió → 404 Not Found
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        # Captura errores no manejados → log en CloudWatch + respuesta 500
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ════════════════════════════════════════════════════════════════
# Funciones CRUD — Crear, Leer, Actualizar, Eliminar Repartidores
# ════════════════════════════════════════════════════════════════

def crear_repartidor(datos):
    """
    Registra un nuevo repartidor en DynamoDB.

    Parámetros:
    ───────────
    datos : dict
        Datos del repartidor enviados en el body del POST:
        - nombre   (str, requerido) → Nombre completo del repartidor
        - telefono (str, requerido) → Número de teléfono de contacto
        - vehiculo (str, requerido) → Tipo de vehículo (ej: "moto", "bicicleta", "auto")

    Retorna:
    ────────
    dict : Respuesta HTTP 201 (Created) con los datos del repartidor creado,
           o 400 (Bad Request) si faltan campos requeridos.

    Flujo:
    ──────
    1. Valida que los campos requeridos estén presentes y no vacíos
    2. Genera un UUID v4 como identificador único
    3. Establece disponibilidad inicial en 1 (disponible)
    4. Registra la fecha de creación en formato ISO 8601
    5. Guarda el item en DynamoDB con put_item()
    """
    # Validar campos requeridos
    campos_requeridos = ["nombre", "telefono", "vehiculo"]
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo]:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    # Construir el item del repartidor
    repartidor = {
        "id": str(uuid.uuid4()),                    # Clave primaria — UUID v4 aleatorio
        "nombre": datos["nombre"],                   # Nombre completo
        "telefono": datos["telefono"],               # Teléfono de contacto
        "vehiculo": datos["vehiculo"],               # Tipo de vehículo
        "disponible": 1,                             # 1 = disponible, 0 = ocupado
        "fecha_registro": datetime.now().isoformat(),  # Timestamp ISO 8601
    }

    # Guardar en DynamoDB
    tabla.put_item(Item=repartidor)
    return respuesta(201, repartidor)


def listar_repartidores():
    """
    Devuelve todos los repartidores registrados.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con lista JSON de todos los repartidores.

    Nota sobre Decimal → int:
    ─────────────────────────
    DynamoDB almacena números como tipo Decimal de Python (no int ni float).
    Esto es porque DynamoDB necesita precisión exacta para números.
    Sin embargo, json.dumps() no sabe serializar Decimal directamente,
    y el campo 'disponible' es conceptualmente un entero (0 o 1), así que
    lo convertimos explícitamente a int antes de devolver la respuesta.
    """
    resultado = tabla.scan()
    repartidores = resultado.get("Items", [])

    # Convertir Decimal → int para el campo 'disponible' de cada repartidor
    for r in repartidores:
        r["disponible"] = int(r.get("disponible", 1))

    return respuesta(200, repartidores)


def obtener_repartidor(repartidor_id):
    """
    Obtiene un repartidor por su ID (clave primaria).

    Parámetros:
    ───────────
    repartidor_id : str
        UUID del repartidor a buscar.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con los datos del repartidor,
           o 404 si no se encontró.

    Implementación:
    ───────────────
    get_item() busca por clave primaria en O(1) — la operación más
    eficiente en DynamoDB. El microservicio de Pedidos usa este endpoint
    para verificar que un repartidor existe y está disponible antes de
    asignarlo a un pedido.
    """
    resultado = tabla.get_item(Key={"id": repartidor_id})
    repartidor = resultado.get("Item")

    if not repartidor:
        return respuesta(404, {"detail": "Repartidor no encontrado"})

    # Convertir Decimal → int para serialización JSON
    repartidor["disponible"] = int(repartidor.get("disponible", 1))
    return respuesta(200, repartidor)


def actualizar_repartidor(repartidor_id, datos):
    """
    Actualiza los datos de un repartidor existente.

    Parámetros:
    ───────────
    repartidor_id : str
        UUID del repartidor a actualizar.
    datos : dict
        Campos a actualizar. Puede incluir:
        - nombre     (str)  → Nuevo nombre
        - telefono   (str)  → Nuevo teléfono
        - vehiculo   (str)  → Nuevo tipo de vehículo
        - disponible (int)  → 1 = disponible, 0 = ocupado

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con los datos actualizados,
           o 404 si el repartidor no existe.

    Caso de uso importante — Cambio de disponibilidad:
    ──────────────────────────────────────────────────
    Cuando el microservicio de Pedidos asigna un repartidor a un pedido,
    llama a este endpoint con {"disponible": 0} para marcarlo como ocupado.
    Cuando el pedido se entrega, se vuelve a llamar con {"disponible": 1}.
    Esta es la comunicación síncrona entre microservicios: Pedidos → Entregas.

    Implementación:
    ───────────────
    update_item() con UpdateExpression modifica solo los campos especificados.
    datos.get("campo", valor_actual) implementa merge parcial: si el campo
    viene en la petición se usa el nuevo valor, si no, se mantiene el actual.
    """
    # Verificar que el repartidor existe
    resultado = tabla.get_item(Key={"id": repartidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Repartidor no encontrado"})

    item_actual = resultado["Item"]

    # Actualizar con merge parcial (campos no enviados conservan su valor)
    tabla.update_item(
        Key={"id": repartidor_id},
        UpdateExpression="SET nombre = :n, telefono = :t, vehiculo = :v, disponible = :d",
        ExpressionAttributeValues={
            ":n": datos.get("nombre", item_actual["nombre"]),
            ":t": datos.get("telefono", item_actual["telefono"]),
            ":v": datos.get("vehiculo", item_actual["vehiculo"]),
            ":d": int(datos.get("disponible", item_actual.get("disponible", 1))),
        },
    )

    # Leer el registro actualizado para devolverlo
    actualizado = tabla.get_item(Key={"id": repartidor_id})
    repartidor = actualizado["Item"]
    repartidor["disponible"] = int(repartidor.get("disponible", 1))
    return respuesta(200, repartidor)


def eliminar_repartidor(repartidor_id):
    """
    Elimina un repartidor de DynamoDB.

    Parámetros:
    ───────────
    repartidor_id : str
        UUID del repartidor a eliminar.

    Retorna:
    ────────
    dict : Respuesta HTTP 204 (No Content) si se eliminó correctamente,
           o 404 si el repartidor no existe.

    Nota: En un sistema real habría que verificar que el repartidor no
    tenga pedidos activos asignados antes de eliminarlo.
    """
    # Verificar que existe antes de eliminar
    resultado = tabla.get_item(Key={"id": repartidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Repartidor no encontrado"})

    tabla.delete_item(Key={"id": repartidor_id})
    return respuesta(204, None)


# ════════════════════════════════════════════════════════════════
# Utilidad — Construcción de respuesta HTTP
# ════════════════════════════════════════════════════════════════

def respuesta(codigo_estado, cuerpo):
    """
    Construye el diccionario de respuesta HTTP que Lambda devuelve a API Gateway.

    Parámetros:
    ───────────
    codigo_estado : int
        Código de estado HTTP (200, 201, 204, 400, 404, 500).
    cuerpo : dict | list | None
        Datos a serializar como JSON en el body de la respuesta.
        None produce un body vacío (usado con 204 No Content).

    Retorna:
    ────────
    dict : { "statusCode": int, "headers": dict, "body": str }

    Notas:
    ──────
    - ensure_ascii=False → Permite caracteres UTF-8 (acentos, ñ) sin escapar
    - default=str → Convierte tipos no serializables (Decimal, datetime) a string
    """
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo is not None else "",
    }
