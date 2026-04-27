"""
Handler Lambda — Microservicio de Consumidores.

Este archivo contiene toda la lógica del microservicio de consumidores.
AWS Lambda ejecuta la función 'lambda_handler' cada vez que llega una
petición HTTP a través del API Gateway.

Conceptos clave:
- Lambda recibe un 'event' con los datos de la petición HTTP
- Lambda devuelve un diccionario con statusCode, headers y body
- Usamos DynamoDB (NoSQL) en lugar de SQLite (SQL relacional)
- boto3 es el SDK de AWS para Python
"""

import json
import uuid
import os
from datetime import datetime

import boto3

# ============================================================
# Configuración
# ============================================================

# Nombre de la tabla DynamoDB (viene de la variable de entorno del template.yaml)
NOMBRE_TABLA = os.environ.get("TABLA_CONSUMIDORES", "ftgo-consumidores")

# Cliente de DynamoDB — nos permite leer y escribir en la tabla
dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(NOMBRE_TABLA)


# ============================================================
# Headers CORS — necesarios para que el frontend pueda llamar al API
# ============================================================
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# ============================================================
# Función principal — punto de entrada de la Lambda
# ============================================================
def lambda_handler(event, context):
    """
    Punto de entrada de la función Lambda.

    AWS Lambda llama a esta función cada vez que llega una petición.
    El parámetro 'event' contiene toda la información de la petición HTTP:
    - event['httpMethod'] → GET, POST, PUT, DELETE
    - event['path'] → la ruta solicitada (ej: /api/consumidores/)
    - event['pathParameters'] → parámetros de la URL (ej: {id: "123"})
    - event['body'] → cuerpo de la petición (JSON como string)
    """
    metodo = event["httpMethod"]
    ruta = event.get("resource", "")

    # Responder a preflight CORS (el navegador envía OPTIONS antes de POST/PUT)
    if metodo == "OPTIONS":
        return respuesta(200, {"mensaje": "OK"})

    # Enrutar la petición según el método HTTP y la ruta
    try:
        if ruta == "/api/consumidores/" and metodo == "GET":
            return listar_consumidores()

        elif ruta == "/api/consumidores/" and metodo == "POST":
            cuerpo = json.loads(event["body"])
            return crear_consumidor(cuerpo)

        elif ruta == "/api/consumidores/{id}" and metodo == "GET":
            consumidor_id = event["pathParameters"]["id"]
            return obtener_consumidor(consumidor_id)

        elif ruta == "/api/consumidores/{id}" and metodo == "PUT":
            consumidor_id = event["pathParameters"]["id"]
            cuerpo = json.loads(event["body"])
            return actualizar_consumidor(consumidor_id, cuerpo)

        elif ruta == "/api/consumidores/{id}" and metodo == "DELETE":
            consumidor_id = event["pathParameters"]["id"]
            return eliminar_consumidor(consumidor_id)

        else:
            return respuesta(404, {"detail": "Ruta no encontrada"})

    except Exception as error:
        print(f"Error: {error}")
        return respuesta(500, {"detail": str(error)})


# ============================================================
# Funciones CRUD — Crear, Leer, Actualizar, Eliminar
# ============================================================

def crear_consumidor(datos):
    """
    Crea un nuevo consumidor en DynamoDB.

    En DynamoDB no hay auto-increment como en SQL, así que generamos
    un UUID (identificador único universal) como ID.
    """
    # Validar que vengan todos los campos requeridos
    campos_requeridos = ["nombre", "email", "telefono", "direccion"]
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo]:
            return respuesta(400, {"detail": f"El campo '{campo}' es requerido"})

    # Verificar que el email no esté duplicado usando el índice secundario
    resultado = tabla.query(
        IndexName="email-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("email").eq(datos["email"]),
    )
    if resultado["Items"]:
        return respuesta(400, {"detail": "El email ya está registrado"})

    # Crear el registro del consumidor
    consumidor = {
        "id": str(uuid.uuid4()),
        "nombre": datos["nombre"],
        "email": datos["email"],
        "telefono": datos["telefono"],
        "direccion": datos["direccion"],
        "fecha_registro": datetime.now().isoformat(),
    }

    # Guardar en DynamoDB
    tabla.put_item(Item=consumidor)

    return respuesta(201, consumidor)


def listar_consumidores():
    """
    Devuelve todos los consumidores.

    tabla.scan() lee TODOS los registros de la tabla.
    En producción con muchos datos se usaría paginación,
    pero para este ejemplo educativo es suficiente.
    """
    resultado = tabla.scan()
    consumidores = resultado.get("Items", [])
    return respuesta(200, consumidores)


def obtener_consumidor(consumidor_id):
    """
    Busca un consumidor por su ID (clave primaria).

    tabla.get_item() es muy eficiente porque busca directamente
    por la clave primaria (O(1) — tiempo constante).
    """
    resultado = tabla.get_item(Key={"id": consumidor_id})
    consumidor = resultado.get("Item")

    if not consumidor:
        return respuesta(404, {"detail": "Consumidor no encontrado"})

    return respuesta(200, consumidor)


def actualizar_consumidor(consumidor_id, datos):
    """
    Actualiza los datos de un consumidor existente.

    Usamos update_item con UpdateExpression para modificar
    solo los campos que cambian, sin reescribir todo el registro.
    """
    # Verificar que el consumidor existe
    resultado = tabla.get_item(Key={"id": consumidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Consumidor no encontrado"})

    # Construir la expresión de actualización
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

    # Obtener el registro actualizado
    actualizado = tabla.get_item(Key={"id": consumidor_id})
    return respuesta(200, actualizado["Item"])


def eliminar_consumidor(consumidor_id):
    """
    Elimina un consumidor de DynamoDB.

    delete_item elimina el registro por su clave primaria.
    """
    # Verificar que existe antes de eliminar
    resultado = tabla.get_item(Key={"id": consumidor_id})
    if "Item" not in resultado:
        return respuesta(404, {"detail": "Consumidor no encontrado"})

    tabla.delete_item(Key={"id": consumidor_id})
    return respuesta(204, None)


# ============================================================
# Utilidad — construir la respuesta HTTP
# ============================================================

def respuesta(codigo_estado, cuerpo):
    """
    Construye el objeto de respuesta que Lambda devuelve al API Gateway.

    API Gateway espera un diccionario con:
    - statusCode: código HTTP (200, 201, 404, etc.)
    - headers: cabeceras HTTP (incluye CORS)
    - body: cuerpo de la respuesta como string JSON
    """
    return {
        "statusCode": codigo_estado,
        "headers": CORS_HEADERS,
        "body": json.dumps(cuerpo, ensure_ascii=False, default=str) if cuerpo else "",
    }
