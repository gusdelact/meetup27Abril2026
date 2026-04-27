"""
Handler Lambda — Microservicio de Pagos (Billing & Payments).

Procesa los pagos de los pedidos. En un sistema real, aquí se
conectaría con Stripe, PayPal u otra pasarela de pagos.
Para este ejemplo educativo, simulamos el procesamiento.

Este servicio consulta al microservicio de Pedidos para obtener
el total del pedido antes de procesar el pago.
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

NOMBRE_TABLA = os.environ.get("TABLA_PAGOS", "ftgo-pagos")
API_PEDIDOS = os.environ.get("API_PEDIDOS_URL", "")

dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# ============================================================
# Función principal
# ============================================================
def lambda_handler(event, context):
    """Enruta la petición HTTP al handler correspondiente."""
    metodo = event["httpMethod"]
    ruta = event.get("path", event.get("resource", ""))
    ruta_norm = ruta.rstrip("/")

    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        if ruta_norm == "/api/pagos" and metodo == "POST":
            return procesar_pago(json.loads(event["body"]))
        elif ruta_norm == "/api/pagos" and metodo == "GET":
            return listar_pagos()
        elif "/api/pagos/" in ruta and metodo == "GET":
            pago_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return obtener_pago(pago_id)
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ============================================================
# Lógica de Pagos
# ============================================================

def procesar_pago(datos):
    """
    Procesa el pago de un pedido.

    Flujo:
    1. Consulta el pedido en el microservicio de Pedidos para obtener el total
    2. Verifica que no exista ya un pago para ese pedido
    3. Simula el procesamiento (en producción sería Stripe/PayPal)
    4. Guarda el registro del pago en DynamoDB
    """
    if "pedido_id" not in datos or "metodo_pago" not in datos:
        return respuesta(400, {"detail": "Se requiere 'pedido_id' y 'metodo_pago'"})

    pedido_id = datos["pedido_id"]
    metodo_pago = datos["metodo_pago"]

    # Consultar el pedido para obtener el total
    monto = Decimal("0")
    if API_PEDIDOS:
        try:
            req = urllib.request.Request(f"{API_PEDIDOS}/api/pedidos/{pedido_id}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    pedido = json.loads(resp.read().decode())
                    monto = Decimal(str(pedido.get("total", 0)))
                else:
                    return respuesta(404, {"detail": "Pedido no encontrado"})
        except Exception as error:
            print(f"Error consultando pedido: {error}")
            return respuesta(404, {"detail": "Pedido no encontrado"})

    # Verificar que no exista ya un pago para este pedido
    resultado = tabla.query(
        IndexName="pedido-index",
        KeyConditionExpression=Key("pedido_id").eq(pedido_id),
    )
    if resultado.get("Items"):
        return respuesta(400, {"detail": "Este pedido ya tiene un pago registrado"})

    # Simular procesamiento del pago
    # En producción aquí se llamaría a la API de Stripe:
    # stripe.PaymentIntent.create(amount=monto, currency="mxn", ...)
    referencia = f"PAY-{uuid.uuid4().hex[:12].upper()}"

    pago = {
        "id": str(uuid.uuid4()),
        "pedido_id": pedido_id,
        "monto": monto,
        "metodo_pago": metodo_pago,
        "estado": "COMPLETADO",
        "referencia": referencia,
        "fecha_pago": datetime.now().isoformat(),
    }
    tabla.put_item(Item=pago)

    # Devolver con monto como float para JSON
    pago_respuesta = dict(pago)
    pago_respuesta["monto"] = float(monto)
    return respuesta(201, pago_respuesta)


def listar_pagos():
    """Lista todos los pagos registrados."""
    resultado = tabla.scan()
    pagos = resultado.get("Items", [])
    for p in pagos:
        p["monto"] = float(p.get("monto", 0))
    return respuesta(200, pagos)


def obtener_pago(pago_id):
    """Obtiene un pago por su ID."""
    resultado = tabla.get_item(Key={"id": pago_id})
    pago = resultado.get("Item")
    if not pago:
        return respuesta(404, {"detail": "Pago no encontrado"})
    pago["monto"] = float(pago.get("monto", 0))
    return respuesta(200, pago)


# ============================================================
# Utilidad
# ============================================================

def respuesta(codigo_estado, cuerpo):
    """Construye la respuesta HTTP para API Gateway."""
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo else "",
    }
