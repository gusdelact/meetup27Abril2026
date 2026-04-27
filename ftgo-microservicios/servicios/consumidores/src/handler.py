"""
Handler Lambda — Microservicio de Consumidores (Customer Service).

╔══════════════════════════════════════════════════════════════════════╗
║  MICROSERVICIO DE CONSUMIDORES — FTGO (Food To Go Online)          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Responsabilidad:                                                    ║
║    Gestionar el registro y administración de los consumidores        ║
║    (clientes) que realizan pedidos en la plataforma FTGO.            ║
║                                                                      ║
║  Operaciones CRUD expuestas:                                         ║
║    POST   /api/consumidores/          → Registrar nuevo consumidor   ║
║    GET    /api/consumidores/          → Listar todos                 ║
║    GET    /api/consumidores/{id}      → Obtener uno por ID           ║
║    PUT    /api/consumidores/{id}      → Actualizar datos             ║
║    DELETE /api/consumidores/{id}      → Eliminar consumidor          ║
║                                                                      ║
║  Infraestructura AWS:                                                ║
║    • AWS Lambda      → Ejecuta este código bajo demanda              ║
║    • API Gateway     → Recibe las peticiones HTTP y las enruta       ║
║    • DynamoDB        → Base de datos NoSQL donde se persisten datos  ║
║                                                                      ║
║  Comunicación:                                                       ║
║    Este servicio es consultado por el microservicio de Pedidos        ║
║    para validar que un consumidor exista antes de crear un pedido.    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

Conceptos clave para entender este archivo:
─────────────────────────────────────────────
1. Lambda recibe un diccionario 'event' con los datos de la petición HTTP
   (método, ruta, cuerpo, parámetros, headers, etc.).
2. Lambda devuelve un diccionario con statusCode, headers y body que
   API Gateway convierte en una respuesta HTTP real.
3. DynamoDB es una base de datos NoSQL de AWS — no usa SQL ni tablas
   relacionales. Los datos se almacenan como documentos JSON (items).
4. boto3 es el SDK oficial de AWS para Python; permite interactuar
   con cualquier servicio de AWS desde código Python.
5. Cada consumidor se identifica por un UUID (identificador único
   universal) generado al momento de la creación, ya que DynamoDB
   no tiene auto-increment como las bases de datos SQL.
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
NOMBRE_TABLA = os.environ.get("TABLA_CONSUMIDORES", "ftgo-consumidores")

# boto3.resource("dynamodb") crea un cliente de alto nivel para DynamoDB.
# A diferencia de boto3.client(), el resource ofrece una interfaz más
# pythónica y orientada a objetos (ej: tabla.put_item() en vez de
# client.put_item(TableName=..., Item=...)).
dynamodb = boto3.resource("dynamodb")

# Referencia a la tabla específica de consumidores.
# Todas las operaciones CRUD se hacen a través de este objeto.
tabla = dynamodb.Table(NOMBRE_TABLA)


# ════════════════════════════════════════════════════════════════
# Headers CORS (Cross-Origin Resource Sharing)
# ════════════════════════════════════════════════════════════════
# CORS es un mecanismo de seguridad del navegador que bloquea peticiones
# HTTP entre dominios diferentes (ej: frontend en dominio A llamando
# a un API en dominio B). Estos headers le dicen al navegador:
#   - Allow-Origin: "*"       → Permitir peticiones desde cualquier dominio
#   - Allow-Methods: "..."    → Métodos HTTP permitidos
#   - Allow-Headers: "..."    → Headers personalizados permitidos
# Sin estos headers, el navegador rechazaría las peticiones del frontend.
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
        - event['httpMethod']      → Método HTTP: GET, POST, PUT, DELETE, OPTIONS
        - event['path']            → Ruta real solicitada (ej: "/api/consumidores/abc-123")
        - event['resource']        → Plantilla de ruta (ej: "/api/consumidores/{id}")
        - event['pathParameters']  → Parámetros extraídos de la URL (ej: {"id": "abc-123"})
        - event['body']            → Cuerpo de la petición como string JSON
        - event['headers']         → Headers HTTP de la petición
        - event['queryStringParameters'] → Parámetros de query string (?key=value)

    context : LambdaContext
        Objeto con metadatos del entorno de ejecución Lambda:
        - context.function_name       → Nombre de la función Lambda
        - context.memory_limit_in_mb  → Memoria asignada
        - context.aws_request_id      → ID único de esta invocación
        - context.get_remaining_time_in_millis() → Tiempo restante antes del timeout

    Retorna:
    ────────
    dict : Respuesta HTTP con formato que API Gateway entiende:
        {
            "statusCode": 200,
            "headers": { ... },
            "body": "{ ... }"   ← JSON como string
        }

    Flujo de enrutamiento:
    ──────────────────────
    1. Extrae el método HTTP y la ruta de la petición
    2. Normaliza la ruta (quita trailing slash) para comparación consistente
    3. Si es OPTIONS → responde con headers CORS (preflight del navegador)
    4. Según la combinación método + ruta, delega a la función CRUD apropiada
    5. Si ninguna ruta coincide → devuelve 404
    6. Si ocurre un error → devuelve 500 con el mensaje de error
    """
    # Extraer método HTTP (GET, POST, PUT, DELETE, OPTIONS)
    metodo = event["httpMethod"]

    # Extraer la ruta; 'path' es la ruta real, 'resource' es la plantilla
    ruta = event.get("path", event.get("resource", ""))

    # Normalizar: quitar trailing slash para que "/api/consumidores" y
    # "/api/consumidores/" se traten igual
    ruta_norm = ruta.rstrip("/")

    # ── Preflight CORS ──
    # Antes de hacer un POST/PUT/DELETE, el navegador envía automáticamente
    # una petición OPTIONS para verificar que el servidor permite CORS.
    # Respondemos con 200 y los headers CORS para que el navegador proceda.
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    # ── Enrutamiento ──
    # Delegamos a la función CRUD correspondiente según método + ruta.
    # Todo dentro de try/except para capturar errores inesperados.
    try:
        # GET /api/consumidores → Listar todos los consumidores
        if ruta_norm == "/api/consumidores" and metodo == "GET":
            return listar_consumidores()

        # POST /api/consumidores → Crear un nuevo consumidor
        elif ruta_norm == "/api/consumidores" and metodo == "POST":
            # json.loads() convierte el string JSON del body a un diccionario Python
            cuerpo = json.loads(event["body"])
            return crear_consumidor(cuerpo)

        # GET /api/consumidores/{id} → Obtener un consumidor específico
        elif "/api/consumidores/" in ruta and metodo == "GET":
            # Intentar obtener el ID de pathParameters (API Gateway lo extrae
            # automáticamente si la ruta tiene {id}), o como fallback extraerlo
            # manualmente del último segmento de la URL
            consumidor_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return obtener_consumidor(consumidor_id)

        # PUT /api/consumidores/{id} → Actualizar un consumidor
        elif "/api/consumidores/" in ruta and metodo == "PUT":
            consumidor_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            cuerpo = json.loads(event["body"])
            return actualizar_consumidor(consumidor_id, cuerpo)

        # DELETE /api/consumidores/{id} → Eliminar un consumidor
        elif "/api/consumidores/" in ruta and metodo == "DELETE":
            consumidor_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return eliminar_consumidor(consumidor_id)

        # Ninguna ruta coincidió → 404 Not Found
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        # Captura cualquier error no manejado y devuelve 500 Internal Server Error.
        # print() envía el error a CloudWatch Logs para depuración.
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ════════════════════════════════════════════════════════════════
# Funciones CRUD — Crear, Leer, Actualizar, Eliminar
# ════════════════════════════════════════════════════════════════

def crear_consumidor(datos):
    """
    Crea un nuevo consumidor en DynamoDB.

    Parámetros:
    ───────────
    datos : dict
        Diccionario con los datos del consumidor enviados en el body
        de la petición POST. Campos esperados:
        - nombre    (str, requerido) → Nombre completo del consumidor
        - email     (str, requerido) → Correo electrónico (debe ser único)
        - telefono  (str, requerido) → Número de teléfono
        - direccion (str, requerido) → Dirección de entrega por defecto

    Retorna:
    ────────
    dict : Respuesta HTTP 201 (Created) con los datos del consumidor creado,
           o 400 (Bad Request) si faltan campos o el email ya existe.

    Flujo:
    ──────
    1. Valida que todos los campos requeridos estén presentes y no vacíos
    2. Verifica que el email no esté duplicado usando un GSI (Global Secondary Index)
       de DynamoDB — esto es equivalente a un UNIQUE constraint en SQL
    3. Genera un UUID v4 como identificador único del consumidor
    4. Registra la fecha de creación en formato ISO 8601
    5. Guarda el item en DynamoDB con put_item()
    6. Devuelve el consumidor creado con código 201

    Nota sobre UUID:
    ────────────────
    En bases de datos SQL se usa típicamente un auto-increment (1, 2, 3...).
    DynamoDB no soporta auto-increment, así que usamos UUID v4 que genera
    un identificador aleatorio de 128 bits con probabilidad de colisión
    prácticamente nula (ej: "550e8400-e29b-41d4-a716-446655440000").
    """
    # ── Paso 1: Validar campos requeridos ──
    campos_requeridos = ["nombre", "email", "telefono", "direccion"]
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo]:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    # ── Paso 2: Verificar unicidad del email ──
    # Usamos un GSI (Global Secondary Index) llamado "email-index" que permite
    # buscar consumidores por email de forma eficiente.
    # En DynamoDB, los GSI son como índices secundarios en SQL: permiten
    # consultas rápidas por campos que no son la clave primaria.
    # Key().eq() construye una condición de igualdad para la query.
    resultado = tabla.query(
        IndexName="email-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("email").eq(datos["email"]),
    )
    if resultado["Items"]:
        return respuesta(400, {"detail": "El email ya está registrado"})

    # ── Paso 3: Construir el item del consumidor ──
    consumidor = {
        "id": str(uuid.uuid4()),                    # Clave primaria — UUID v4 aleatorio
        "nombre": datos["nombre"],                   # Nombre completo
        "email": datos["email"],                     # Email (indexado por GSI para unicidad)
        "telefono": datos["telefono"],               # Teléfono de contacto
        "direccion": datos["direccion"],             # Dirección de entrega por defecto
        "fecha_registro": datetime.now().isoformat(),  # Timestamp ISO 8601 (ej: "2026-04-27T14:30:00")
    }

    # ── Paso 4: Guardar en DynamoDB ──
    # put_item() inserta un nuevo item o reemplaza uno existente con la misma
    # clave primaria. Como el ID es un UUID nuevo, siempre será una inserción.
    tabla.put_item(Item=consumidor)

    # ── Paso 5: Devolver respuesta 201 Created ──
    return respuesta(201, consumidor)


def listar_consumidores():
    """
    Devuelve todos los consumidores registrados en la tabla.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con una lista JSON de todos los consumidores.

    Implementación:
    ───────────────
    tabla.scan() lee TODOS los registros de la tabla DynamoDB.

    ⚠️  Consideraciones de rendimiento:
    - scan() recorre toda la tabla secuencialmente — es O(n) donde n es
      el número total de items.
    - DynamoDB cobra por cada unidad de lectura consumida (RCU).
    - Para tablas con millones de registros, scan() sería costoso y lento.
    - En producción se usaría paginación con 'LastEvaluatedKey' o se
      implementaría un GSI con query() para filtrar eficientemente.
    - Para este ejemplo educativo con pocos registros, scan() es suficiente.
    """
    resultado = tabla.scan()
    consumidores = resultado.get("Items", [])
    return respuesta(200, consumidores)


def obtener_consumidor(consumidor_id):
    """
    Busca un consumidor por su ID (clave primaria).

    Parámetros:
    ───────────
    consumidor_id : str
        UUID del consumidor a buscar.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con los datos del consumidor,
           o 404 si no se encontró.

    Implementación:
    ───────────────
    tabla.get_item() busca directamente por la clave primaria (partition key).
    Esta operación es O(1) — tiempo constante — porque DynamoDB usa una
    tabla hash internamente. Es la forma más eficiente de leer un item.

    Equivalente SQL: SELECT * FROM consumidores WHERE id = ?
    """
    resultado = tabla.get_item(Key={"id": consumidor_id})
    consumidor = resultado.get("Item")

    if not consumidor:
        return respuesta(404, {"detail": "Consumidor no encontrado"})

    return respuesta(200, consumidor)


def actualizar_consumidor(consumidor_id, datos):
    """
    Actualiza los datos de un consumidor existente.

    Parámetros:
    ───────────
    consumidor_id : str
        UUID del consumidor a actualizar.
    datos : dict
        Diccionario con los campos a actualizar. Los campos no incluidos
        conservan su valor actual (merge parcial).

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con los datos actualizados,
           o 404 si el consumidor no existe.

    Implementación:
    ───────────────
    Usamos update_item() con UpdateExpression en vez de put_item() porque:
    1. update_item() modifica solo los campos especificados sin reescribir
       todo el item (más eficiente en red y costo).
    2. UpdateExpression usa una sintaxis similar a SQL SET:
       "SET nombre = :n, email = :e, ..."
    3. ExpressionAttributeValues mapea los placeholders (:n, :e, etc.)
       a los valores reales — esto previene inyección de datos.
    4. datos.get("campo", valor_actual) implementa un merge: si el campo
       viene en la petición se usa el nuevo valor, si no, se mantiene el actual.

    Equivalente SQL: UPDATE consumidores SET nombre=?, email=?, ... WHERE id=?
    """
    # Primero verificar que el consumidor existe
    resultado = tabla.get_item(Key={"id": consumidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Consumidor no encontrado"})

    # Construir y ejecutar la expresión de actualización
    tabla.update_item(
        Key={"id": consumidor_id},
        UpdateExpression="SET nombre = :n, email = :e, telefono = :t, direccion = :d",
        ExpressionAttributeValues={
            ":n": datos.get("nombre", resultado["Item"]["nombre"]),
            ":e": datos.get("email", resultado["Item"]["email"]),
            ":t": datos.get("telefono", resultado["Item"]["telefono"]),
            ":d": datos.get("direccion", resultado["Item"]["direccion"]),
        },
    )

    # Leer el registro actualizado para devolverlo en la respuesta
    actualizado = tabla.get_item(Key={"id": consumidor_id})
    return respuesta(200, actualizado["Item"])


def eliminar_consumidor(consumidor_id):
    """
    Elimina un consumidor de DynamoDB.

    Parámetros:
    ───────────
    consumidor_id : str
        UUID del consumidor a eliminar.

    Retorna:
    ────────
    dict : Respuesta HTTP 204 (No Content) si se eliminó correctamente,
           o 404 si el consumidor no existe.

    Implementación:
    ───────────────
    delete_item() elimina el item por su clave primaria.
    Primero verificamos que exista para devolver un 404 apropiado
    en vez de un 204 silencioso (mejor experiencia para el cliente del API).

    Nota: En un sistema real habría que considerar si el consumidor tiene
    pedidos activos antes de eliminarlo (integridad referencial), pero
    DynamoDB no tiene foreign keys como SQL — esa lógica se maneja en
    la capa de aplicación.

    Equivalente SQL: DELETE FROM consumidores WHERE id = ?
    """
    # Verificar que existe antes de eliminar
    resultado = tabla.get_item(Key={"id": consumidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Consumidor no encontrado"})

    tabla.delete_item(Key={"id": consumidor_id})

    # 204 No Content — la eliminación fue exitosa, no hay cuerpo en la respuesta
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
        Código de estado HTTP. Códigos usados en este servicio:
        - 200 → OK (lectura exitosa)
        - 201 → Created (recurso creado exitosamente)
        - 204 → No Content (eliminación exitosa, sin cuerpo)
        - 400 → Bad Request (datos inválidos o faltantes)
        - 404 → Not Found (recurso no encontrado)
        - 500 → Internal Server Error (error inesperado)

    cuerpo : dict | list | None
        Datos a incluir en el body de la respuesta.
        - dict/list → se serializa a JSON string
        - None      → body vacío (usado con 204)

    Retorna:
    ────────
    dict : Diccionario con el formato que API Gateway espera:
        {
            "statusCode": int,
            "headers": dict,    ← Incluye CORS headers
            "body": str         ← JSON serializado o string vacío
        }

    Notas sobre json.dumps():
    ─────────────────────────
    - ensure_ascii=False → Permite caracteres UTF-8 (acentos, ñ, etc.)
      sin escaparlos como \\uXXXX. Importante para nombres en español.
    - default=str → Si json.dumps() encuentra un tipo que no sabe
      serializar (como Decimal de DynamoDB o datetime), lo convierte
      a string automáticamente en vez de lanzar un TypeError.
    """
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo is not None else "",
    }
