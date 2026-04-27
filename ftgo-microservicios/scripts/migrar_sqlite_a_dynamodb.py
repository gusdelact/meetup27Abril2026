"""
Script de Migración — SQLite3 → DynamoDB.

Este script lee los datos del monolito (ftgo.db) y los inserta
en las tablas DynamoDB de cada microservicio.

Prerrequisitos:
- Tener las tablas DynamoDB ya creadas (desplegar los stacks primero)
- Tener configuradas las credenciales AWS (aws configure)
- Tener acceso al archivo ftgo.db del monolito

Ejecución desde la instancia EC2:
    cd ftgo-microservicios/scripts
    pip install boto3 sqlalchemy
    python migrar_sqlite_a_dynamodb.py

O con uv:
    uv run python migrar_sqlite_a_dynamodb.py
"""

import sqlite3
import uuid
import sys
import os
from datetime import datetime
from decimal import Decimal

import boto3

# ============================================================
# Configuración
# ============================================================

# Ruta a la base de datos SQLite del monolito
RUTA_SQLITE = os.path.join(os.path.dirname(__file__), "..", "..", "ftgo-monolito", "ftgo.db")

# Región de AWS donde están las tablas DynamoDB
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Nombres de las tablas DynamoDB (deben coincidir con los template.yaml)
TABLA_CONSUMIDORES = "ftgo-consumidores"
TABLA_RESTAURANTES = "ftgo-restaurantes"
TABLA_PEDIDOS = "ftgo-pedidos"
TABLA_REPARTIDORES = "ftgo-repartidores"
TABLA_PAGOS = "ftgo-pagos"

# Cliente DynamoDB
dynamodb = boto3.resource("dynamodb", region_name=REGION)


# ============================================================
# Funciones de migración
# ============================================================

def conectar_sqlite():
    """Conecta a la base de datos SQLite del monolito."""
    if not os.path.exists(RUTA_SQLITE):
        print(f"❌ No se encontró la base de datos en: {RUTA_SQLITE}")
        print("   Asegúrate de que el archivo ftgo.db existe en ftgo-monolito/")
        sys.exit(1)

    conn = sqlite3.connect(RUTA_SQLITE)
    conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
    return conn


def migrar_consumidores(conn):
    """Migra la tabla 'consumidores' de SQLite a DynamoDB."""
    print("\n📋 Migrando consumidores...")
    tabla = dynamodb.Table(TABLA_CONSUMIDORES)
    cursor = conn.execute("SELECT * FROM consumidores")
    filas = cursor.fetchall()

    # Mapeo de IDs viejos (int) a nuevos (UUID) para referencias
    mapa_ids = {}

    for fila in filas:
        nuevo_id = str(uuid.uuid4())
        mapa_ids[fila["id"]] = nuevo_id

        item = {
            "id": nuevo_id,
            "nombre": fila["nombre"],
            "email": fila["email"],
            "telefono": fila["telefono"],
            "direccion": fila["direccion"],
            "fecha_registro": fila["fecha_registro"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(filas)} consumidores migrados")
    return mapa_ids


def migrar_restaurantes(conn):
    """Migra restaurantes y elementos del menú a DynamoDB (single-table)."""
    print("\n📋 Migrando restaurantes y menús...")
    tabla = dynamodb.Table(TABLA_RESTAURANTES)

    # Migrar restaurantes
    cursor = conn.execute("SELECT * FROM restaurantes")
    restaurantes = cursor.fetchall()
    mapa_ids_rest = {}

    for fila in restaurantes:
        nuevo_id = str(uuid.uuid4())
        mapa_ids_rest[fila["id"]] = nuevo_id

        item = {
            "PK": f"REST#{nuevo_id}",
            "SK": "METADATA",
            "tipo_entidad": "restaurante",
            "id": nuevo_id,
            "nombre": fila["nombre"],
            "direccion": fila["direccion"],
            "telefono": fila["telefono"],
            "tipo_cocina": fila["tipo_cocina"],
            "horario_apertura": fila["horario_apertura"] or "09:00",
            "horario_cierre": fila["horario_cierre"] or "22:00",
            "fecha_registro": fila["fecha_registro"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(restaurantes)} restaurantes migrados")

    # Migrar elementos del menú
    cursor = conn.execute("SELECT * FROM elementos_menu")
    elementos = cursor.fetchall()
    mapa_ids_menu = {}

    for fila in elementos:
        nuevo_id = str(uuid.uuid4())
        mapa_ids_menu[fila["id"]] = nuevo_id
        rest_id = mapa_ids_rest.get(fila["restaurante_id"], "")

        item = {
            "PK": f"REST#{rest_id}",
            "SK": f"MENU#{nuevo_id}",
            "tipo_entidad": "elemento_menu",
            "id": nuevo_id,
            "restaurante_id": rest_id,
            "nombre": fila["nombre"],
            "descripcion": fila["descripcion"] or "",
            "precio": Decimal(str(fila["precio"])),
            "disponible": fila["disponible"],
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(elementos)} elementos del menú migrados")
    return mapa_ids_rest, mapa_ids_menu


def migrar_repartidores(conn):
    """Migra la tabla 'repartidores' de SQLite a DynamoDB."""
    print("\n📋 Migrando repartidores...")
    tabla = dynamodb.Table(TABLA_REPARTIDORES)
    cursor = conn.execute("SELECT * FROM repartidores")
    filas = cursor.fetchall()
    mapa_ids = {}

    for fila in filas:
        nuevo_id = str(uuid.uuid4())
        mapa_ids[fila["id"]] = nuevo_id

        item = {
            "id": nuevo_id,
            "nombre": fila["nombre"],
            "telefono": fila["telefono"],
            "vehiculo": fila["vehiculo"],
            "disponible": fila["disponible"],
            "fecha_registro": fila["fecha_registro"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(filas)} repartidores migrados")
    return mapa_ids


def migrar_pedidos(conn, mapa_cons, mapa_rest, mapa_menu, mapa_rep):
    """Migra pedidos y sus elementos a DynamoDB."""
    print("\n📋 Migrando pedidos...")
    tabla = dynamodb.Table(TABLA_PEDIDOS)

    cursor = conn.execute("SELECT * FROM pedidos")
    pedidos = cursor.fetchall()
    mapa_ids_ped = {}

    for fila in pedidos:
        nuevo_id = str(uuid.uuid4())
        mapa_ids_ped[fila["id"]] = nuevo_id

        item = {
            "PK": f"PED#{nuevo_id}",
            "SK": "METADATA",
            "tipo_entidad": "pedido",
            "id": nuevo_id,
            "consumidor_id": mapa_cons.get(fila["consumidor_id"], ""),
            "restaurante_id": mapa_rest.get(fila["restaurante_id"], ""),
            "repartidor_id": mapa_rep.get(fila["repartidor_id"]) if fila["repartidor_id"] else None,
            "estado": fila["estado"],
            "total": Decimal(str(fila["total"])),
            "direccion_entrega": fila["direccion_entrega"],
            "fecha_creacion": fila["fecha_creacion"] or datetime.now().isoformat(),
            "fecha_actualizacion": fila["fecha_actualizacion"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    # Migrar elementos de pedido
    cursor = conn.execute("SELECT * FROM elementos_pedido")
    elementos = cursor.fetchall()

    for fila in elementos:
        elem_id = str(uuid.uuid4())
        ped_id = mapa_ids_ped.get(fila["pedido_id"], "")

        item = {
            "PK": f"PED#{ped_id}",
            "SK": f"ELEM#{elem_id}",
            "tipo_entidad": "elemento_pedido",
            "id": elem_id,
            "pedido_id": ped_id,
            "elemento_menu_id": mapa_menu.get(fila["elemento_menu_id"], ""),
            "cantidad": fila["cantidad"],
            "precio_unitario": Decimal(str(fila["precio_unitario"])),
            "subtotal": Decimal(str(fila["subtotal"])),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(pedidos)} pedidos y {len(elementos)} elementos migrados")
    return mapa_ids_ped


def migrar_pagos(conn, mapa_ped):
    """Migra la tabla 'pagos' de SQLite a DynamoDB."""
    print("\n📋 Migrando pagos...")
    tabla = dynamodb.Table(TABLA_PAGOS)
    cursor = conn.execute("SELECT * FROM pagos")
    filas = cursor.fetchall()

    for fila in filas:
        item = {
            "id": str(uuid.uuid4()),
            "pedido_id": mapa_ped.get(fila["pedido_id"], ""),
            "monto": Decimal(str(fila["monto"])),
            "metodo_pago": fila["metodo_pago"],
            "estado": fila["estado"],
            "referencia": fila["referencia"] or "",
            "fecha_pago": fila["fecha_pago"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(filas)} pagos migrados")


# ============================================================
# Ejecución principal
# ============================================================

def main():
    print("=" * 60)
    print("🔄 Migración SQLite → DynamoDB")
    print("=" * 60)
    print(f"   Base de datos origen: {RUTA_SQLITE}")
    print(f"   Región AWS destino: {REGION}")
    print()

    # Conectar a SQLite
    conn = conectar_sqlite()

    # Migrar en orden (respetando dependencias)
    mapa_cons = migrar_consumidores(conn)
    mapa_rest, mapa_menu = migrar_restaurantes(conn)
    mapa_rep = migrar_repartidores(conn)
    mapa_ped = migrar_pedidos(conn, mapa_cons, mapa_rest, mapa_menu, mapa_rep)
    migrar_pagos(conn, mapa_ped)

    conn.close()

    print("\n" + "=" * 60)
    print("🎉 Migración completada exitosamente")
    print("=" * 60)
    print()
    print("   Resumen de mapeo de IDs (SQLite int → DynamoDB UUID):")
    print(f"   • {len(mapa_cons)} consumidores")
    print(f"   • {len(mapa_rest)} restaurantes")
    print(f"   • {len(mapa_menu)} elementos del menú")
    print(f"   • {len(mapa_rep)} repartidores")
    print(f"   • {len(mapa_ped)} pedidos")


if __name__ == "__main__":
    main()
