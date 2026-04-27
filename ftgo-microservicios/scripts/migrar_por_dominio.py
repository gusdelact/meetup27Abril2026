"""
Script de Migración por Dominio — SQLite3 → DynamoDB.

A diferencia de migrar_sqlite_a_dynamodb.py (que migra TODAS las tablas),
este script migra SOLO el esquema correspondiente a UN dominio específico.

Esto es útil en el meetup donde cada célula de trabajo es responsable
de desplegar y poblar únicamente su microservicio asignado.

Dominios disponibles:
  • consumidores  → Tabla: consumidores
  • restaurantes  → Tablas: restaurantes + elementos_menu (single-table)
  • entregas      → Tabla: repartidores
  • pedidos       → Tablas: pedidos + elementos_pedido (single-table)
  • pagos         → Tabla: pagos

Prerrequisitos:
  - Tener la tabla DynamoDB del dominio ya creada (sam deploy del stack)
  - Tener credenciales AWS configuradas (export AWS_ACCESS_KEY_ID, etc.)
  - Tener acceso al archivo ftgo.db del monolito
  - pip install boto3  (o uv add boto3)

Uso:
    python migrar_por_dominio.py <dominio>

Ejemplos:
    python migrar_por_dominio.py consumidores
    python migrar_por_dominio.py restaurantes
    python migrar_por_dominio.py entregas
    python migrar_por_dominio.py pedidos
    python migrar_por_dominio.py pagos

Nota sobre pedidos y pagos:
    Estos dominios tienen dependencias de IDs de otros dominios.
    El script genera UUIDs nuevos y muestra un mapeo de IDs viejos
    a nuevos para que puedas coordinar con las otras células.
    Si las otras células ya migraron sus datos, puedes pasar los
    mapeos como archivos JSON con la opción --mapeo:

    python migrar_por_dominio.py pedidos \\
        --mapeo-consumidores mapeo_consumidores.json \\
        --mapeo-restaurantes mapeo_restaurantes.json \\
        --mapeo-menu mapeo_menu.json \\
        --mapeo-repartidores mapeo_repartidores.json

    python migrar_por_dominio.py pagos \\
        --mapeo-pedidos mapeo_pedidos.json
"""

import sqlite3
import uuid
import sys
import os
import json
import argparse
from datetime import datetime
from decimal import Decimal

# boto3 se importa de forma lazy para que --help funcione sin tenerlo instalado
boto3 = None

def _importar_boto3():
    """Importa boto3 bajo demanda (permite ejecutar --help sin boto3 instalado)."""
    global boto3
    if boto3 is None:
        try:
            import boto3 as _boto3
            boto3 = _boto3
        except ImportError:
            print("❌ boto3 no está instalado. Instálalo con:")
            print("   pip install boto3")
            print("   (o: uv add boto3)")
            sys.exit(1)
    return boto3

# ============================================================
# Configuración
# ============================================================

RUTA_SQLITE = os.environ.get(
    "RUTA_SQLITE",
    os.path.join(os.path.dirname(__file__), "..", "..", "ftgo-monolito", "ftgo.db"),
)

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

# Nombres de tablas DynamoDB (pueden sobreescribirse con variables de entorno)
TABLA_CONSUMIDORES = os.environ.get("TABLA_CONSUMIDORES", "ftgo-consumidores")
TABLA_RESTAURANTES = os.environ.get("TABLA_RESTAURANTES", "ftgo-restaurantes")
TABLA_PEDIDOS = os.environ.get("TABLA_PEDIDOS", "ftgo-pedidos")
TABLA_REPARTIDORES = os.environ.get("TABLA_REPARTIDORES", "ftgo-repartidores")
TABLA_PAGOS = os.environ.get("TABLA_PAGOS", "ftgo-pagos")

DOMINIOS_VALIDOS = ["consumidores", "restaurantes", "entregas", "pedidos", "pagos"]

# ============================================================
# Conexión a SQLite
# ============================================================

def conectar_sqlite(ruta):
    """Conecta a la base de datos SQLite del monolito."""
    ruta_abs = os.path.abspath(ruta)
    if not os.path.exists(ruta_abs):
        print(f"❌ No se encontró la base de datos en: {ruta_abs}")
        print("   Asegúrate de que el archivo ftgo.db existe.")
        print("   Puedes especificar otra ruta con la variable de entorno RUTA_SQLITE")
        sys.exit(1)

    conn = sqlite3.connect(ruta_abs)
    conn.row_factory = sqlite3.Row
    print(f"   📂 Base de datos SQLite: {ruta_abs}")
    return conn


# ============================================================
# Utilidades para mapeos de IDs
# ============================================================

def guardar_mapeo(mapeo, nombre_archivo):
    """Guarda un mapeo de IDs (int → UUID) como archivo JSON."""
    # Convertir claves int a string para JSON
    mapeo_str = {str(k): v for k, v in mapeo.items()}
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(mapeo_str, f, indent=2, ensure_ascii=False)
    print(f"   💾 Mapeo guardado en: {nombre_archivo}")


def cargar_mapeo(nombre_archivo):
    """Carga un mapeo de IDs desde un archivo JSON."""
    if not nombre_archivo:
        return {}
    ruta = os.path.abspath(nombre_archivo)
    if not os.path.exists(ruta):
        print(f"   ⚠️  Archivo de mapeo no encontrado: {ruta}")
        print(f"       Se usarán IDs placeholder para las referencias externas.")
        return {}
    with open(ruta, "r", encoding="utf-8") as f:
        mapeo_str = json.load(f)
    # Convertir claves string de vuelta a int
    return {int(k): v for k, v in mapeo_str.items()}


# ============================================================
# Migración: Consumidores
# ============================================================

def migrar_consumidores(conn, region):
    """Migra SOLO la tabla 'consumidores' de SQLite a DynamoDB."""
    print("\n📋 Migrando dominio: CONSUMIDORES")
    print(f"   Tabla DynamoDB destino: {TABLA_CONSUMIDORES}")

    b3 = _importar_boto3()
    dynamodb = b3.resource("dynamodb", region_name=region)
    tabla = dynamodb.Table(TABLA_CONSUMIDORES)

    cursor = conn.execute("SELECT * FROM consumidores")
    filas = cursor.fetchall()

    if not filas:
        print("   ⚠️  No hay consumidores en la base de datos SQLite.")
        return {}

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

    # Guardar mapeo para que la célula de pedidos pueda usarlo
    guardar_mapeo(mapa_ids, "mapeo_consumidores.json")
    return mapa_ids


# ============================================================
# Migración: Restaurantes (+ Menú — single-table design)
# ============================================================

def migrar_restaurantes(conn, region):
    """Migra restaurantes y elementos del menú a DynamoDB (single-table)."""
    print("\n📋 Migrando dominio: RESTAURANTES (+ menú)")
    print(f"   Tabla DynamoDB destino: {TABLA_RESTAURANTES}")

    b3 = _importar_boto3()
    dynamodb = b3.resource("dynamodb", region_name=region)
    tabla = dynamodb.Table(TABLA_RESTAURANTES)

    # --- Restaurantes ---
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

    # --- Elementos del menú ---
    cursor = conn.execute("SELECT * FROM elementos_menu")
    elementos = cursor.fetchall()
    mapa_ids_menu = {}

    for fila in elementos:
        nuevo_id = str(uuid.uuid4())
        mapa_ids_menu[fila["id"]] = nuevo_id
        rest_id = mapa_ids_rest.get(fila["restaurante_id"], "DESCONOCIDO")

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

    # Guardar mapeos para que la célula de pedidos pueda usarlos
    guardar_mapeo(mapa_ids_rest, "mapeo_restaurantes.json")
    guardar_mapeo(mapa_ids_menu, "mapeo_menu.json")
    return mapa_ids_rest, mapa_ids_menu


# ============================================================
# Migración: Entregas (Repartidores)
# ============================================================

def migrar_entregas(conn, region):
    """Migra SOLO la tabla 'repartidores' de SQLite a DynamoDB."""
    print("\n📋 Migrando dominio: ENTREGAS (repartidores)")
    print(f"   Tabla DynamoDB destino: {TABLA_REPARTIDORES}")

    b3 = _importar_boto3()
    dynamodb = b3.resource("dynamodb", region_name=region)
    tabla = dynamodb.Table(TABLA_REPARTIDORES)

    cursor = conn.execute("SELECT * FROM repartidores")
    filas = cursor.fetchall()

    if not filas:
        print("   ⚠️  No hay repartidores en la base de datos SQLite.")
        return {}

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

    # Guardar mapeo para que la célula de pedidos pueda usarlo
    guardar_mapeo(mapa_ids, "mapeo_repartidores.json")
    return mapa_ids


# ============================================================
# Migración: Pedidos (+ Elementos de pedido — single-table)
# ============================================================

def migrar_pedidos(conn, region, mapa_cons, mapa_rest, mapa_menu, mapa_rep):
    """
    Migra pedidos y sus elementos a DynamoDB.

    Los mapeos de IDs de otros dominios son necesarios para mantener
    las referencias lógicas entre microservicios. Si no se proporcionan,
    se usan los IDs originales (int) como placeholder.
    """
    print("\n📋 Migrando dominio: PEDIDOS (+ elementos)")
    print(f"   Tabla DynamoDB destino: {TABLA_PEDIDOS}")

    if not mapa_cons:
        print("   ⚠️  Sin mapeo de consumidores — se usarán IDs originales como placeholder")
    if not mapa_rest:
        print("   ⚠️  Sin mapeo de restaurantes — se usarán IDs originales como placeholder")
    if not mapa_rep:
        print("   ⚠️  Sin mapeo de repartidores — se usarán IDs originales como placeholder")

    b3 = _importar_boto3()
    dynamodb = b3.resource("dynamodb", region_name=region)
    tabla = dynamodb.Table(TABLA_PEDIDOS)

    # --- Pedidos ---
    cursor = conn.execute("SELECT * FROM pedidos")
    pedidos = cursor.fetchall()
    mapa_ids_ped = {}

    for fila in pedidos:
        nuevo_id = str(uuid.uuid4())
        mapa_ids_ped[fila["id"]] = nuevo_id

        # Resolver referencias a otros dominios
        cons_id = mapa_cons.get(fila["consumidor_id"], str(fila["consumidor_id"]))
        rest_id = mapa_rest.get(fila["restaurante_id"], str(fila["restaurante_id"]))
        rep_id = None
        if fila["repartidor_id"]:
            rep_id = mapa_rep.get(fila["repartidor_id"], str(fila["repartidor_id"]))

        item = {
            "PK": f"PED#{nuevo_id}",
            "SK": "METADATA",
            "tipo_entidad": "pedido",
            "id": nuevo_id,
            "consumidor_id": cons_id,
            "restaurante_id": rest_id,
            "repartidor_id": rep_id,
            "estado": fila["estado"],
            "total": Decimal(str(fila["total"])),
            "direccion_entrega": fila["direccion_entrega"],
            "fecha_creacion": fila["fecha_creacion"] or datetime.now().isoformat(),
            "fecha_actualizacion": fila["fecha_actualizacion"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(pedidos)} pedidos migrados")

    # --- Elementos de pedido ---
    cursor = conn.execute("SELECT * FROM elementos_pedido")
    elementos = cursor.fetchall()

    for fila in elementos:
        elem_id = str(uuid.uuid4())
        ped_id = mapa_ids_ped.get(fila["pedido_id"], str(fila["pedido_id"]))
        menu_id = mapa_menu.get(fila["elemento_menu_id"], str(fila["elemento_menu_id"]))

        item = {
            "PK": f"PED#{ped_id}",
            "SK": f"ELEM#{elem_id}",
            "tipo_entidad": "elemento_pedido",
            "id": elem_id,
            "pedido_id": ped_id,
            "elemento_menu_id": menu_id,
            "cantidad": fila["cantidad"],
            "precio_unitario": Decimal(str(fila["precio_unitario"])),
            "subtotal": Decimal(str(fila["subtotal"])),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(elementos)} elementos de pedido migrados")

    # Guardar mapeo para que la célula de pagos pueda usarlo
    guardar_mapeo(mapa_ids_ped, "mapeo_pedidos.json")
    return mapa_ids_ped


# ============================================================
# Migración: Pagos
# ============================================================

def migrar_pagos(conn, region, mapa_ped):
    """
    Migra SOLO la tabla 'pagos' de SQLite a DynamoDB.

    Necesita el mapeo de IDs de pedidos para mantener la referencia
    lógica al microservicio de pedidos.
    """
    print("\n📋 Migrando dominio: PAGOS")
    print(f"   Tabla DynamoDB destino: {TABLA_PAGOS}")

    if not mapa_ped:
        print("   ⚠️  Sin mapeo de pedidos — se usarán IDs originales como placeholder")

    b3 = _importar_boto3()
    dynamodb = b3.resource("dynamodb", region_name=region)
    tabla = dynamodb.Table(TABLA_PAGOS)

    cursor = conn.execute("SELECT * FROM pagos")
    filas = cursor.fetchall()

    if not filas:
        print("   ⚠️  No hay pagos en la base de datos SQLite.")
        return

    for fila in filas:
        ped_id = mapa_ped.get(fila["pedido_id"], str(fila["pedido_id"]))

        item = {
            "id": str(uuid.uuid4()),
            "pedido_id": ped_id,
            "monto": Decimal(str(fila["monto"])),
            "metodo_pago": fila["metodo_pago"],
            "estado": fila["estado"],
            "referencia": fila["referencia"] or "",
            "fecha_pago": fila["fecha_pago"] or datetime.now().isoformat(),
        }
        tabla.put_item(Item=item)

    print(f"   ✅ {len(filas)} pagos migrados")


# ============================================================
# CLI — Argumentos de línea de comandos
# ============================================================

def crear_parser():
    parser = argparse.ArgumentParser(
        description="Migra un dominio específico de SQLite (monolito) a DynamoDB (microservicio).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python migrar_por_dominio.py consumidores
  python migrar_por_dominio.py restaurantes
  python migrar_por_dominio.py entregas
  python migrar_por_dominio.py pedidos --mapeo-consumidores mapeo_consumidores.json --mapeo-restaurantes mapeo_restaurantes.json --mapeo-menu mapeo_menu.json --mapeo-repartidores mapeo_repartidores.json
  python migrar_por_dominio.py pagos --mapeo-pedidos mapeo_pedidos.json

Variables de entorno opcionales:
  RUTA_SQLITE          Ruta al archivo ftgo.db (default: ../../ftgo-monolito/ftgo.db)
  AWS_REGION           Región de AWS (default: us-east-1)
  TABLA_CONSUMIDORES   Nombre de la tabla DynamoDB de consumidores
  TABLA_RESTAURANTES   Nombre de la tabla DynamoDB de restaurantes
  TABLA_PEDIDOS        Nombre de la tabla DynamoDB de pedidos
  TABLA_REPARTIDORES   Nombre de la tabla DynamoDB de repartidores
  TABLA_PAGOS          Nombre de la tabla DynamoDB de pagos
        """,
    )

    parser.add_argument(
        "dominio",
        choices=DOMINIOS_VALIDOS,
        help="Dominio a migrar: consumidores, restaurantes, entregas, pedidos, pagos",
    )

    parser.add_argument(
        "--sqlite",
        default=RUTA_SQLITE,
        help="Ruta al archivo ftgo.db del monolito (default: auto-detecta)",
    )

    # Mapeos de IDs para dominios con dependencias
    parser.add_argument(
        "--mapeo-consumidores",
        default=None,
        help="Archivo JSON con mapeo de IDs de consumidores (para dominio pedidos)",
    )
    parser.add_argument(
        "--mapeo-restaurantes",
        default=None,
        help="Archivo JSON con mapeo de IDs de restaurantes (para dominio pedidos)",
    )
    parser.add_argument(
        "--mapeo-menu",
        default=None,
        help="Archivo JSON con mapeo de IDs de elementos del menú (para dominio pedidos)",
    )
    parser.add_argument(
        "--mapeo-repartidores",
        default=None,
        help="Archivo JSON con mapeo de IDs de repartidores (para dominio pedidos)",
    )
    parser.add_argument(
        "--mapeo-pedidos",
        default=None,
        help="Archivo JSON con mapeo de IDs de pedidos (para dominio pagos)",
    )

    return parser


# ============================================================
# Ejecución principal
# ============================================================

def main():
    parser = crear_parser()
    args = parser.parse_args()

    dominio = args.dominio

    print("=" * 60)
    print(f"🔄 Migración por Dominio: {dominio.upper()}")
    print("=" * 60)
    print(f"   Región AWS: {REGION}")

    conn = conectar_sqlite(args.sqlite)

    if dominio == "consumidores":
        migrar_consumidores(conn, REGION)

    elif dominio == "restaurantes":
        migrar_restaurantes(conn, REGION)

    elif dominio == "entregas":
        migrar_entregas(conn, REGION)

    elif dominio == "pedidos":
        # Cargar mapeos de otros dominios si se proporcionaron
        mapa_cons = cargar_mapeo(args.mapeo_consumidores)
        mapa_rest = cargar_mapeo(args.mapeo_restaurantes)
        mapa_menu = cargar_mapeo(args.mapeo_menu)
        mapa_rep = cargar_mapeo(args.mapeo_repartidores)

        # Si no se pasaron archivos, intentar cargar automáticamente
        # desde el directorio actual (por si las otras células ya los generaron)
        if not mapa_cons and os.path.exists("mapeo_consumidores.json"):
            print("   📂 Auto-detectado: mapeo_consumidores.json")
            mapa_cons = cargar_mapeo("mapeo_consumidores.json")
        if not mapa_rest and os.path.exists("mapeo_restaurantes.json"):
            print("   📂 Auto-detectado: mapeo_restaurantes.json")
            mapa_rest = cargar_mapeo("mapeo_restaurantes.json")
        if not mapa_menu and os.path.exists("mapeo_menu.json"):
            print("   📂 Auto-detectado: mapeo_menu.json")
            mapa_menu = cargar_mapeo("mapeo_menu.json")
        if not mapa_rep and os.path.exists("mapeo_repartidores.json"):
            print("   📂 Auto-detectado: mapeo_repartidores.json")
            mapa_rep = cargar_mapeo("mapeo_repartidores.json")

        migrar_pedidos(conn, REGION, mapa_cons, mapa_rest, mapa_menu, mapa_rep)

    elif dominio == "pagos":
        mapa_ped = cargar_mapeo(args.mapeo_pedidos)

        if not mapa_ped and os.path.exists("mapeo_pedidos.json"):
            print("   📂 Auto-detectado: mapeo_pedidos.json")
            mapa_ped = cargar_mapeo("mapeo_pedidos.json")

        migrar_pagos(conn, REGION, mapa_ped)

    conn.close()

    print("\n" + "=" * 60)
    print(f"🎉 Migración del dominio '{dominio}' completada")
    print("=" * 60)
    print()
    print("   Archivos de mapeo generados (comparte con las otras células):")
    for f in ["mapeo_consumidores.json", "mapeo_restaurantes.json",
              "mapeo_menu.json", "mapeo_repartidores.json", "mapeo_pedidos.json"]:
        if os.path.exists(f):
            print(f"   • {f}")


if __name__ == "__main__":
    main()
