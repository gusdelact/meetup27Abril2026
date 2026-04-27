"""
Handler Lambda — Microservicio de Restaurantes y Menús.

Este microservicio gestiona los restaurantes y sus menús (platillos).
Usa "single-table design" en DynamoDB: tanto los restaurantes como
los elementos del menú se almacenan en la misma tabla, diferenciados
por la Sort Key (SK):

- Restaurante: PK="REST#<id>", SK="METADATA"
- Elemento del menú: PK="REST#<id>", SK="MENU#<menu_id>"

Esto permite obtener un restaurante con todo su menú en una sola
consulta (query por PK), lo cual es muy eficiente en DynamoDB.
"""

import json
import uuid
import os
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

# ============================================================
# Configuración
# ============================================================

NOMBRE_TABLA = os.environ.get("TABLA_RESTAURANTES", "ftgo-restaurantes")
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
    # Usar path (ruta real) para routing, no resource (template con {id})
    ruta = event.get("path", event.get("resource", ""))
    ruta_norm = ruta.rstrip("/")

    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    try:
        # --- Rutas de Restaurantes ---
        if ruta_norm == "/api/restaurantes" and metodo == "GET":
            return listar_restaurantes()
        elif ruta_norm == "/api/restaurantes" and metodo == "POST":
            return crear_restaurante(json.loads(event["body"]))
        elif "/api/restaurantes/menu/" in ruta and metodo == "PUT":
            elemento_id = event.get("pathParameters", {}).get("elemento_id") or ruta.split("/")[-1]
            return actualizar_elemento_menu(elemento_id, json.loads(event["body"]))
        elif "/api/restaurantes/menu/" in ruta and metodo == "DELETE":
            elemento_id = event.get("pathParameters", {}).get("elemento_id") or ruta.split("/")[-1]
            return eliminar_elemento_menu(elemento_id)
        elif "/api/restaurantes/" in ruta and "/menu" in ruta and metodo == "POST":
            rest_id = ruta.split("/api/restaurantes/")[1].split("/")[0]
            return agregar_elemento_menu(rest_id, json.loads(event["body"]))
        elif "/api/restaurantes/" in ruta and "/menu" in ruta and metodo == "GET":
            rest_id = ruta.split("/api/restaurantes/")[1].split("/")[0]
            return obtener_menu(rest_id)
        elif "/api/restaurantes/" in ruta and metodo == "GET":
            rest_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/restaurantes/")[1].split("/")[0]
            return obtener_restaurante(rest_id)
        elif "/api/restaurantes/" in ruta and metodo == "PUT":
            rest_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/restaurantes/")[1].split("/")[0]
            return actualizar_restaurante(rest_id, json.loads(event["body"]))
        elif "/api/restaurantes/" in ruta and metodo == "DELETE":
            rest_id = event.get("pathParameters", {}).get("id") or ruta.split("/api/restaurantes/")[1].split("/")[0]
            return eliminar_restaurante(rest_id)
        else:
            return respuesta(404, {"detail": f"Ruta no encontrada: {metodo} {ruta}"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ============================================================
# CRUD de Restaurantes
# ============================================================

def crear_restaurante(datos):
    """Crea un nuevo restaurante en DynamoDB."""
    campos_requeridos = ["nombre", "direccion", "telefono", "tipo_cocina"]
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo]:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    restaurante_id = str(uuid.uuid4())
    item = {
        "PK": f"REST#{restaurante_id}",
        "SK": "METADATA",
        "tipo_entidad": "restaurante",
        "id": restaurante_id,
        "nombre": datos["nombre"],
        "direccion": datos["direccion"],
        "telefono": datos["telefono"],
        "tipo_cocina": datos["tipo_cocina"],
        "horario_apertura": datos.get("horario_apertura", "09:00"),
        "horario_cierre": datos.get("horario_cierre", "22:00"),
        "fecha_registro": datetime.now().isoformat(),
    }
    tabla.put_item(Item=item)

    # Devolver sin PK/SK (datos internos de DynamoDB)
    return respuesta(201, limpiar_item_restaurante(item))


def listar_restaurantes():
    """Lista todos los restaurantes (solo los METADATA, no los menús)."""
    resultado = tabla.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("tipo_entidad").eq("restaurante")
    )
    restaurantes = [limpiar_item_restaurante(item) for item in resultado.get("Items", [])]
    return respuesta(200, restaurantes)


def obtener_restaurante(restaurante_id):
    """Obtiene un restaurante por su ID."""
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    item = resultado.get("Item")
    if not item:
        return respuesta(404, {"detail": "Restaurante no encontrado"})
    return respuesta(200, limpiar_item_restaurante(item))


def actualizar_restaurante(restaurante_id, datos):
    """Actualiza los datos de un restaurante."""
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Restaurante no encontrado"})

    item_actual = resultado["Item"]
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
    """Elimina un restaurante y todos sus elementos del menú."""
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Restaurante no encontrado"})

    # Eliminar todos los items con este PK (restaurante + menú)
    items = tabla.query(KeyConditionExpression=Key("PK").eq(f"REST#{restaurante_id}"))
    for item in items.get("Items", []):
        tabla.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    return respuesta(204, None)


# ============================================================
# CRUD del Menú
# ============================================================

def agregar_elemento_menu(restaurante_id, datos):
    """Agrega un platillo al menú de un restaurante."""
    # Verificar que el restaurante existe
    resultado = tabla.get_item(Key={"PK": f"REST#{restaurante_id}", "SK": "METADATA"})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Restaurante no encontrado"})

    if "nombre" not in datos or "precio" not in datos:
        return respuesta(400, {"detail": "Se requiere 'nombre' y 'precio'"})

    menu_id = str(uuid.uuid4())
    item = {
        "PK": f"REST#{restaurante_id}",
        "SK": f"MENU#{menu_id}",
        "tipo_entidad": "elemento_menu",
        "id": menu_id,
        "restaurante_id": restaurante_id,
        "nombre": datos["nombre"],
        "descripcion": datos.get("descripcion", ""),
        "precio": Decimal(str(datos["precio"])),
        "disponible": datos.get("disponible", 1),
    }
    tabla.put_item(Item=item)
    return respuesta(201, limpiar_item_menu(item))


def obtener_menu(restaurante_id):
    """Obtiene todos los platillos del menú de un restaurante."""
    resultado = tabla.query(
        KeyConditionExpression=Key("PK").eq(f"REST#{restaurante_id}") & Key("SK").begins_with("MENU#")
    )
    platillos = [limpiar_item_menu(item) for item in resultado.get("Items", [])]
    return respuesta(200, platillos)


def actualizar_elemento_menu(elemento_id, datos):
    """Actualiza un platillo del menú."""
    # Buscar el elemento por su ID (necesitamos el PK completo)
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
    """Elimina un platillo del menú."""
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


# ============================================================
# Utilidades
# ============================================================

def limpiar_item_restaurante(item):
    """Remueve campos internos de DynamoDB y devuelve datos limpios."""
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
    """Remueve campos internos de DynamoDB para elementos del menú."""
    return {
        "id": item["id"],
        "restaurante_id": item["restaurante_id"],
        "nombre": item["nombre"],
        "descripcion": item.get("descripcion", ""),
        "precio": float(item["precio"]),
        "disponible": int(item.get("disponible", 1)),
    }


def respuesta(codigo_estado, cuerpo):
    """Construye la respuesta HTTP para API Gateway."""
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo is not None else "",
    }
