"""
Handler Lambda — Microservicio de Entregas (Repartidores).

Gestiona los repartidores que entregan los pedidos.
Cada repartidor tiene un estado de disponibilidad que se actualiza
cuando se le asigna un pedido (desde el microservicio de Pedidos).
"""

import json
import uuid
import os
from datetime import datetime

import boto3

# ============================================================
# Configuración
# ============================================================

NOMBRE_TABLA = os.environ.get("TABLA_REPARTIDORES", "ftgo-repartidores")
dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# ============================================================
# Función principal
# ============================================================
def lambda_handler(event, context):
    """Enruta la petición HTTP al handler correspondiente."""
    metodo = event["httpMethod"]
    ruta = event.get("resource", event.get("path", ""))
    ruta_norm = ruta.rstrip("/")

    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        if ruta_norm == "/api/repartidores" and metodo == "GET":
            return listar_repartidores()
        elif ruta_norm == "/api/repartidores" and metodo == "POST":
            return crear_repartidor(json.loads(event["body"]))
        elif "/api/repartidores/" in ruta and metodo == "GET":
            rep_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return obtener_repartidor(rep_id)
        elif "/api/repartidores/" in ruta and metodo == "PUT":
            rep_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return actualizar_repartidor(rep_id, json.loads(event["body"]))
        elif "/api/repartidores/" in ruta and metodo == "DELETE":
            rep_id = event.get("pathParameters", {}).get("id") or ruta.split("/")[-1]
            return eliminar_repartidor(rep_id)
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ============================================================
# CRUD de Repartidores
# ============================================================

def crear_repartidor(datos):
    """Registra un nuevo repartidor."""
    campos_requeridos = ["nombre", "telefono", "vehiculo"]
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo]:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    repartidor = {
        "id": str(uuid.uuid4()),
        "nombre": datos["nombre"],
        "telefono": datos["telefono"],
        "vehiculo": datos["vehiculo"],
        "disponible": 1,  # 1 = disponible, 0 = ocupado
        "fecha_registro": datetime.now().isoformat(),
    }
    tabla.put_item(Item=repartidor)
    return respuesta(201, repartidor)


def listar_repartidores():
    """Lista todos los repartidores."""
    resultado = tabla.scan()
    repartidores = resultado.get("Items", [])
    # Convertir Decimal a int para el campo 'disponible'
    for r in repartidores:
        r["disponible"] = int(r.get("disponible", 1))
    return respuesta(200, repartidores)


def obtener_repartidor(repartidor_id):
    """Obtiene un repartidor por su ID."""
    resultado = tabla.get_item(Key={"id": repartidor_id})
    repartidor = resultado.get("Item")
    if not repartidor:
        return respuesta(404, {"detail": "Repartidor no encontrado"})
    repartidor["disponible"] = int(repartidor.get("disponible", 1))
    return respuesta(200, repartidor)


def actualizar_repartidor(repartidor_id, datos):
    """
    Actualiza los datos de un repartidor.
    También se usa para cambiar su disponibilidad (cuando se le asigna un pedido).
    """
    resultado = tabla.get_item(Key={"id": repartidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Repartidor no encontrado"})

    item_actual = resultado["Item"]

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

    actualizado = tabla.get_item(Key={"id": repartidor_id})
    repartidor = actualizado["Item"]
    repartidor["disponible"] = int(repartidor.get("disponible", 1))
    return respuesta(200, repartidor)


def eliminar_repartidor(repartidor_id):
    """Elimina un repartidor."""
    resultado = tabla.get_item(Key={"id": repartidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Repartidor no encontrado"})

    tabla.delete_item(Key={"id": repartidor_id})
    return respuesta(204, None)


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
