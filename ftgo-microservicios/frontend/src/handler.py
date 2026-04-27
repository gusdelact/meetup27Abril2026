"""
Handler Lambda — Frontend FTGO (Servidor de archivos estáticos).

Esta Lambda sirve los archivos HTML, CSS y JS del frontend.
Actúa como un servidor web simple que devuelve el archivo
correspondiente según la ruta solicitada.

Se usa como alternativa a S3+CloudFront cuando esos servicios
no están disponibles en la cuenta.
"""

import os
import mimetypes

# Directorio donde están los archivos estáticos
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Mapeo de extensiones a content-types
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def lambda_handler(event, context):
    """Sirve archivos estáticos según la ruta solicitada."""
    # Obtener la ruta del request
    path = event.get("path", "/")

    # Si es la raíz, servir index.html
    if path == "/" or path == "":
        path = "/index.html"

    # Quitar el slash inicial para construir la ruta del archivo
    filename = path.lstrip("/")

    # Construir ruta completa al archivo
    filepath = os.path.join(STATIC_DIR, filename)

    # Verificar que el archivo existe
    if not os.path.isfile(filepath):
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": "<h1>404 - Archivo no encontrado</h1>",
        }

    # Determinar el content-type
    ext = os.path.splitext(filename)[1].lower()
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

    # Leer el archivo
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            body = f.read()
        is_base64 = False
    except UnicodeDecodeError:
        # Archivo binario (imágenes, etc.)
        import base64
        with open(filepath, "rb") as f:
            body = base64.b64encode(f.read()).decode("utf-8")
        is_base64 = True

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
        },
        "body": body,
        "isBase64Encoded": is_base64,
    }
