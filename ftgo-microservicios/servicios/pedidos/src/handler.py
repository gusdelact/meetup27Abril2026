"""
Handler Lambda — Microservicio de Pedidos (Order Management).

Este es el microservicio más complejo del sistema FTGO.
Gestiona todo el ciclo de vida de un pedido:
- Creación (validando consumidor y restaurante en otros servicios)
- Cambio de estado (máquina de estados)
- Asignación de repartidor
- Cancelación

Comunicación entre microservicios:
- Para crear un pedido, este servicio llama al API de Consumidores
  y al API de Restaurantes para validar que existan.
- Para asignar repartidor, llama al API de Entregas.
- Estas llamadas HTTP entre servicios son la forma más simple
  de comunicación en microservicios (comunicación síncrona).
"""

import json
import uuid
import os
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
import urllib.request

# ============================================================
# Configuración
# ============================================================

NOMBRE_TABLA = os.environ.get("TABLA_PEDIDOS", "ftgo-pedidos")
API_CONSUMIDORES = os.environ.get("API_CONSUMIDORES_URL", "")
API_RESTAURANTES = os.environ.get("API_RESTAURANTES_URL", "")
API_ENTREGAS = os.environ.get("API_ENTREGAS_URL", "")

dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

# Transiciones de estado válidas (misma lógica que el monolito)
TRANSICIONES_VALIDAS = {
    "CREADO": ["ACEPTADO", "CANCELADO"],
    "ACEPTADO": ["PREPARANDO", "CANCELADO"],
    "PREPARANDO": ["LISTO", "CANCELADO"],
    "LISTO": ["EN_CAMINO"],
    "EN_CAMINO": ["ENTREGADO"],
    "ENTREGADO": [],
    "CANCELADO": [],
}


# ============================================================
# Función principal
# ============================================================
def lambda_handler(event, context):
    """Enruta la petición HTTP al handler correspondiente."""
    metodo = event["httpMethod"]
    ruta = event.get("resource", "")

    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        if ruta == "/api/pedidos/" and metodo == "GET":
            return listar_pedidos()
        elif ruta == "/api/pedidos/" and metodo == "POST":
            return crear_pedido(json.loads(event["body"]))
        elif ruta == "/api/pedidos/{id}" and metodo == "GET":
            return obtener_pedido(event["pathParameters"]["id"])
        elif ruta == "/api/pedidos/{id}/estado" and metodo == "PUT":
            return actualizar_estado(
                event["pathParameters"]["id"], json.loads(event["body"])
            )
        elif ruta == "/api/pedidos/{id}/repartidor" and metodo == "PUT":
            return asignar_repartidor(
                event["pathParameters"]["id"], json.loads(event["body"])
            )
        elif ruta == "/api/pedidos/{id}" and metodo == "DELETE":
            return cancelar_pedido(event["pathParameters"]["id"])
        else:
            return respuesta(404, {"detail": "Ruta no encontrada"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ============================================================
# Comunicación con otros microservicios
# ============================================================

def llamar_servicio(url):
    """
    Hace una petición GET a otro microservicio.

    En microservicios, los servicios se comunican entre sí por HTTP.
    Esta función usa urllib (librería estándar de Python) para hacer
    la llamada sin dependencias externas.

    Retorna el JSON de respuesta o None si falla.
    """
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except Exception as error:
        print(f"Error llamando a {url}: {error}")
    return None


# ============================================================
# CRUD de Pedidos
# ============================================================

def crear_pedido(datos):
    """
    Crea un nuevo pedido.

    Flujo:
    1. Valida que el consumidor exista (llama al microservicio de consumidores)
    2. Obtiene el menú del restaurante (llama al microservicio de restaurantes)
    3. Valida los platillos y calcula el total
    4. Guarda el pedido en DynamoDB
    """
    campos_requeridos = ["consumidor_id", "restaurante_id", "direccion_entrega", "elementos"]
    for campo in campos_requeridos:
        if campo not in datos:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    if not datos["elementos"]:
        return respuesta(400, {"detail": "El pedido debe tener al menos un elemento"})

    # Validar consumidor (llamada al microservicio de consumidores)
    if API_CONSUMIDORES:
        consumidor = llamar_servicio(
            f"{API_CONSUMIDORES}/api/consumidores/{datos['consumidor_id']}"
        )
        if not consumidor:
            return respuesta(404, {"detail": "Consumidor no encontrado"})

    # Obtener menú del restaurante (llamada al microservicio de restaurantes)
    menu = []
    if API_RESTAURANTES:
        menu = llamar_servicio(
            f"{API_RESTAURANTES}/api/restaurantes/{datos['restaurante_id']}/menu/"
        )
        if menu is None:
            return respuesta(404, {"detail": "Restaurante no encontrado"})

    # Calcular total del pedido
    pedido_id = str(uuid.uuid4())
    total = Decimal("0")
    elementos_guardados = []

    for elem in datos["elementos"]:
        elemento_menu_id = elem["elemento_menu_id"]
        cantidad = elem.get("cantidad", 1)

        # Buscar el precio del platillo en el menú
        platillo = next((p for p in menu if p["id"] == elemento_menu_id), None)
        if platillo:
            precio = Decimal(str(platillo["precio"]))
        else:
            # Si no se puede validar el menú, usar precio 0
            precio = Decimal("0")

        subtotal = precio * cantidad
        total += subtotal

        elem_id = str(uuid.uuid4())
        elemento_item = {
            "PK": f"PED#{pedido_id}",
            "SK": f"ELEM#{elem_id}",
            "tipo_entidad": "elemento_pedido",
            "id": elem_id,
            "pedido_id": pedido_id,
            "elemento_menu_id": elemento_menu_id,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "subtotal": subtotal,
        }
        tabla.put_item(Item=elemento_item)
        elementos_guardados.append({
            "id": elem_id,
            "elemento_menu_id": elemento_menu_id,
            "cantidad": cantidad,
            "precio_unitario": float(precio),
            "subtotal": float(subtotal),
        })

    # Guardar el pedido principal
    ahora = datetime.now().isoformat()
    pedido_item = {
        "PK": f"PED#{pedido_id}",
        "SK": "METADATA",
        "tipo_entidad": "pedido",
        "id": pedido_id,
        "consumidor_id": datos["consumidor_id"],
        "restaurante_id": datos["restaurante_id"],
        "repartidor_id": None,
        "estado": "CREADO",
        "total": total,
        "direccion_entrega": datos["direccion_entrega"],
        "fecha_creacion": ahora,
        "fecha_actualizacion": ahora,
    }
    tabla.put_item(Item=pedido_item)

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
    """Lista todos los pedidos (solo metadata, sin elementos)."""
    resultado = tabla.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("tipo_entidad").eq("pedido")
    )
    pedidos = []
    for item in resultado.get("Items", []):
        pedidos.append(limpiar_pedido(item))
    return respuesta(200, pedidos)


def obtener_pedido(pedido_id):
    """Obtiene un pedido con sus elementos."""
    # Obtener el pedido y sus elementos con una sola query
    resultado = tabla.query(
        KeyConditionExpression=Key("PK").eq(f"PED#{pedido_id}")
    )
    items = resultado.get("Items", [])
    if not items:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = None
    elementos = []
    for item in items:
        if item["SK"] == "METADATA":
            pedido = limpiar_pedido(item)
        elif item["SK"].startswith("ELEM#"):
            elementos.append({
                "id": item["id"],
                "elemento_menu_id": item["elemento_menu_id"],
                "cantidad": int(item["cantidad"]),
                "precio_unitario": float(item["precio_unitario"]),
                "subtotal": float(item["subtotal"]),
            })

    if not pedido:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido["elementos"] = elementos
    return respuesta(200, pedido)


def actualizar_estado(pedido_id, datos):
    """
    Cambia el estado de un pedido.
    Valida que la transición sea permitida según la máquina de estados.
    """
    if "estado" not in datos:
        return respuesta(400, {"detail": "El campo 'estado' es requerido"})

    resultado = tabla.get_item(Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = resultado["Item"]
    estado_actual = pedido["estado"]
    nuevo_estado = datos["estado"].upper()

    # Validar transición de estado
    estados_permitidos = TRANSICIONES_VALIDAS.get(estado_actual, [])
    if nuevo_estado not in estados_permitidos:
        return respuesta(400, {
            "detail": f"No se puede cambiar de '{estado_actual}' a '{nuevo_estado}'. "
                      f"Estados permitidos: {estados_permitidos}"
        })

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
    Asigna un repartidor a un pedido.
    El pedido debe estar en estado LISTO.
    Llama al microservicio de entregas para marcar al repartidor como ocupado.
    """
    if "repartidor_id" not in datos:
        return respuesta(400, {"detail": "El campo 'repartidor_id' es requerido"})

    resultado = tabla.get_item(Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = resultado["Item"]
    if pedido["estado"] != "LISTO":
        return respuesta(400, {
            "detail": "Solo se puede asignar repartidor a pedidos en estado LISTO"
        })

    repartidor_id = datos["repartidor_id"]

    # Verificar repartidor en el microservicio de entregas
    if API_ENTREGAS:
        repartidor = llamar_servicio(
            f"{API_ENTREGAS}/api/repartidores/{repartidor_id}"
        )
        if not repartidor:
            return respuesta(404, {"detail": "Repartidor no encontrado"})
        if not repartidor.get("disponible"):
            return respuesta(400, {"detail": "El repartidor no está disponible"})

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
    """Cancela un pedido (cambia estado a CANCELADO)."""
    resultado = tabla.get_item(Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Pedido no encontrado"})

    pedido = resultado["Item"]
    if pedido["estado"] in ["EN_CAMINO", "ENTREGADO"]:
        return respuesta(400, {
            "detail": "No se puede cancelar un pedido en camino o ya entregado"
        })

    ahora = datetime.now().isoformat()
    tabla.update_item(
        Key={"PK": f"PED#{pedido_id}", "SK": "METADATA"},
        UpdateExpression="SET estado = :e, fecha_actualizacion = :f",
        ExpressionAttributeValues={":e": "CANCELADO", ":f": ahora},
    )
    return respuesta(204, None)


# ============================================================
# Utilidades
# ============================================================

def limpiar_pedido(item):
    """Convierte un item de DynamoDB a formato de respuesta limpio."""
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
    """Construye la respuesta HTTP para API Gateway."""
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo else "",
    }
