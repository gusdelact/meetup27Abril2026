"""
Handler Lambda — Microservicio de Pagos (Billing & Payments Service).

╔══════════════════════════════════════════════════════════════════════╗
║  MICROSERVICIO DE PAGOS — FTGO (Food To Go Online)                 ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Responsabilidad:                                                    ║
║    Procesar y registrar los pagos de los pedidos realizados en la    ║
║    plataforma. En un sistema real, aquí se integraría con una        ║
║    pasarela de pagos como Stripe, PayPal o MercadoPago.              ║
║    Para este ejemplo educativo, el pago se simula.                   ║
║                                                                      ║
║  Operaciones expuestas:                                              ║
║    POST   /api/pagos/          → Procesar pago de un pedido         ║
║    GET    /api/pagos/          → Listar todos los pagos              ║
║    GET    /api/pagos/{id}      → Obtener un pago por ID             ║
║                                                                      ║
║  Infraestructura AWS:                                                ║
║    • AWS Lambda      → Ejecuta este código bajo demanda              ║
║    • API Gateway     → Recibe las peticiones HTTP y las enruta       ║
║    • DynamoDB        → Almacena los registros de pagos               ║
║                                                                      ║
║  Comunicación con otros microservicios:                              ║
║    • Pedidos (lectura) → Consulta el total del pedido vía HTTP GET   ║
║      antes de procesar el pago. Esta es comunicación síncrona        ║
║      entre microservicios (este servicio depende de Pedidos).        ║
║                                                                      ║
║  Flujo de un pago:                                                   ║
║    1. Frontend envía POST con {pedido_id, metodo_pago}               ║
║    2. Este servicio consulta al microservicio de Pedidos para         ║
║       obtener el monto total del pedido                              ║
║    3. Verifica que no exista ya un pago para ese pedido (idempotencia)║
║    4. Simula el procesamiento del pago                               ║
║    5. Guarda el registro del pago en DynamoDB                        ║
║    6. Devuelve la confirmación con referencia de pago                ║
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
import urllib.request                      # Cliente HTTP de la librería estándar de Python
                                           # (se usa para llamar a otros microservicios sin
                                           #  dependencias externas como requests)


# ════════════════════════════════════════════════════════════════
# Configuración
# ════════════════════════════════════════════════════════════════

# Nombre de la tabla DynamoDB para pagos (definido en template.yaml)
NOMBRE_TABLA = os.environ.get("TABLA_PAGOS", "ftgo-pagos")

# URL base del microservicio de Pedidos — necesaria para consultar
# el total del pedido antes de procesar el pago.
# Esta URL se configura como variable de entorno en template.yaml
# y apunta al API Gateway del microservicio de Pedidos.
API_PEDIDOS = os.environ.get("API_PEDIDOS_URL", "")

# Conexión a DynamoDB (se reutiliza entre invocaciones Lambda — warm start)
dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)

# Headers CORS para permitir peticiones desde el frontend
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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
    - POST /api/pagos     → Procesar un nuevo pago
    - GET  /api/pagos     → Listar todos los pagos
    - GET  /api/pagos/{id} → Obtener un pago específico
    """
    metodo = event["httpMethod"]
    ruta = event.get("path", event.get("resource", ""))
    ruta_norm = ruta.rstrip("/")

    # Responder a preflight CORS
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        # POST /api/pagos → Procesar pago de un pedido
        if ruta_norm == "/api/pagos" and metodo == "POST":
            return procesar_pago(json.loads(event["body"]))

        # GET /api/pagos → Listar todos los pagos registrados
        elif ruta_norm == "/api/pagos" and metodo == "GET":
            return listar_pagos()

        # GET /api/pagos/{id} → Obtener un pago específico por ID
        elif "/api/pagos/" in ruta and metodo == "GET":
            pago_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return obtener_pago(pago_id)

        # Ruta no encontrada
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ════════════════════════════════════════════════════════════════
# Lógica de Pagos
# ════════════════════════════════════════════════════════════════

def procesar_pago(datos):
    """
    Procesa el pago de un pedido — operación principal de este microservicio.

    Parámetros:
    ───────────
    datos : dict
        Datos del pago enviados en el body del POST:
        - pedido_id   (str, requerido) → UUID del pedido a pagar
        - metodo_pago (str, requerido) → Método de pago (ej: "tarjeta", "efectivo")

    Retorna:
    ────────
    dict : Respuesta HTTP 201 con los datos del pago procesado,
           o 400/404 si hay errores de validación.

    Flujo detallado:
    ────────────────
    1. VALIDACIÓN DE ENTRADA
       Verifica que vengan los campos requeridos (pedido_id y metodo_pago).

    2. COMUNICACIÓN INTER-SERVICIO (Pedidos → Pagos)
       Hace una petición HTTP GET al microservicio de Pedidos para obtener
       el total del pedido. Esto es un ejemplo de comunicación síncrona
       entre microservicios:
       - Este servicio (Pagos) DEPENDE del servicio de Pedidos
       - Si Pedidos está caído, este servicio no puede procesar pagos
       - En arquitecturas más avanzadas se usarían colas (SQS) o eventos
         (EventBridge) para desacoplar esta dependencia

       Se usa urllib.request (librería estándar de Python) en vez de
       'requests' para evitar dependencias externas en la Lambda.

    3. VERIFICACIÓN DE IDEMPOTENCIA
       Consulta un GSI (Global Secondary Index) llamado "pedido-index"
       para verificar que no exista ya un pago para este pedido.
       Esto previene cobros duplicados — un principio fundamental en
       sistemas de pagos.

    4. SIMULACIÓN DEL PAGO
       En un sistema real, aquí se llamaría a la API de una pasarela:
         stripe.PaymentIntent.create(amount=monto, currency="mxn", ...)
       Para este ejemplo educativo, simplemente generamos una referencia
       de pago simulada con formato "PAY-XXXXXXXXXXXX".

    5. PERSISTENCIA
       Guarda el registro del pago en DynamoDB con todos los datos:
       ID, pedido_id, monto, método, estado, referencia y fecha.

    6. RESPUESTA
       Devuelve el pago creado con código 201 (Created).
       El monto se convierte de Decimal a float para serialización JSON.
    """
    # ── Paso 1: Validar campos requeridos ──
    if "pedido_id" not in datos or "metodo_pago" not in datos:
        return respuesta(400, {"detail": "Se requiere 'pedido_id' y 'metodo_pago'"})

    pedido_id = datos["pedido_id"]
    metodo_pago = datos["metodo_pago"]

    # ── Paso 2: Consultar el pedido para obtener el monto total ──
    # Comunicación síncrona: Pagos → Pedidos (HTTP GET)
    # Se usa urllib.request.Request para construir la petición HTTP
    # y urllib.request.urlopen para ejecutarla con un timeout de 10 segundos.
    monto = Decimal("0")
    if API_PEDIDOS:
        try:
            req = urllib.request.Request(f"{API_PEDIDOS}/api/pedidos/{pedido_id}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    # Decodificar la respuesta JSON del microservicio de Pedidos
                    pedido = json.loads(resp.read().decode())
                    # Convertir el total a Decimal para precisión exacta en DynamoDB
                    # (float puede tener errores de redondeo: 0.1 + 0.2 ≠ 0.3)
                    monto = Decimal(str(pedido.get("total", 0)))
                else:
                    return respuesta(404, {"detail": "Pedido no encontrado"})
        except Exception as error:
            print(f"Error consultando pedido: {error}")
            return respuesta(404, {"detail": "Pedido no encontrado"})

    # ── Paso 3: Verificar que no exista ya un pago para este pedido ──
    # Usamos un GSI (Global Secondary Index) "pedido-index" que permite
    # buscar pagos por pedido_id de forma eficiente.
    # Key().eq() construye la condición: pedido_id = <valor>
    resultado = tabla.query(
        IndexName="pedido-index",
        KeyConditionExpression=Key("pedido_id").eq(pedido_id),
    )
    if resultado.get("Items"):
        return respuesta(400, {"detail": "Este pedido ya tiene un pago registrado"})

    # ── Paso 4: Simular procesamiento del pago ──
    # Generar una referencia de pago única con formato legible.
    # uuid.uuid4().hex genera 32 caracteres hexadecimales; tomamos los
    # primeros 12 y los convertimos a mayúsculas para la referencia.
    # Ejemplo: "PAY-A1B2C3D4E5F6"
    #
    # En producción, aquí se llamaría a la API de Stripe:
    #   stripe.PaymentIntent.create(
    #       amount=int(monto * 100),  # Stripe usa centavos
    #       currency="mxn",
    #       payment_method=metodo_pago,
    #       confirm=True
    #   )
    referencia = f"PAY-{uuid.uuid4().hex[:12].upper()}"

    # ── Paso 5: Guardar el registro del pago en DynamoDB ──
    pago = {
        "id": str(uuid.uuid4()),                    # Clave primaria — UUID v4
        "pedido_id": pedido_id,                      # Referencia al pedido (indexado por GSI)
        "monto": monto,                              # Monto total como Decimal (precisión exacta)
        "metodo_pago": metodo_pago,                  # "tarjeta", "efectivo", etc.
        "estado": "COMPLETADO",                      # Estado del pago (simulado como exitoso)
        "referencia": referencia,                    # Referencia única del pago (PAY-XXXX)
        "fecha_pago": datetime.now().isoformat(),    # Timestamp ISO 8601
    }
    tabla.put_item(Item=pago)

    # ── Paso 6: Devolver respuesta con monto como float ──
    # DynamoDB almacena Decimal, pero JSON no soporta Decimal nativo,
    # así que convertimos a float para la respuesta al cliente.
    pago_respuesta = dict(pago)
    pago_respuesta["monto"] = float(monto)
    return respuesta(201, pago_respuesta)


def listar_pagos():
    """
    Lista todos los pagos registrados en la tabla.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con lista JSON de todos los pagos.

    Nota: El campo 'monto' se convierte de Decimal a float para cada
    pago, ya que json.dumps() no serializa Decimal directamente.
    """
    resultado = tabla.scan()
    pagos = resultado.get("Items", [])

    # Convertir Decimal → float para serialización JSON
    for p in pagos:
        p["monto"] = float(p.get("monto", 0))

    return respuesta(200, pagos)


def obtener_pago(pago_id):
    """
    Obtiene un pago por su ID (clave primaria).

    Parámetros:
    ───────────
    pago_id : str
        UUID del pago a buscar.

    Retorna:
    ────────
    dict : Respuesta HTTP 200 con los datos del pago,
           o 404 si no se encontró.
    """
    resultado = tabla.get_item(Key={"id": pago_id})
    pago = resultado.get("Item")

    if not pago:
        return respuesta(404, {"detail": "Pago no encontrado"})

    # Convertir Decimal → float para serialización JSON
    pago["monto"] = float(pago.get("monto", 0))
    return respuesta(200, pago)


# ════════════════════════════════════════════════════════════════
# Utilidad — Construcción de respuesta HTTP
# ════════════════════════════════════════════════════════════════

def respuesta(codigo_estado, cuerpo):
    """
    Construye el diccionario de respuesta HTTP que Lambda devuelve a API Gateway.

    Parámetros:
    ───────────
    codigo_estado : int
        Código HTTP (200, 201, 400, 404, 500).
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
