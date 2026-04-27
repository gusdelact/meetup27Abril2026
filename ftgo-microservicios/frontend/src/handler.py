"""
Handler Lambda — Frontend FTGO (Servidor de archivos estáticos).

Sirve los archivos HTML, CSS y JS del frontend a través de API Gateway.
Alternativa a S3+CloudFront cuando esos servicios no están disponibles.
"""

import os

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
    # Obtener la ruta — usar pathParameters.proxy si existe (para {proxy+})
    path_params = event.get("pathParameters") or {}
    proxy_path = path_params.get("proxy", "")

    # Si no hay proxy path, usar el path directo
    if proxy_path:
        filename = proxy_path
    else:
        path = event.get("path", "/")
        if path == "/" or path == "" or path == "/Prod" or path == "/Prod/":
            filename = "index.html"
        else:
            filename = path.lstrip("/")

    # Si el filename está vacío, servir index.html
    if not filename or filename == "":
        filename = "index.html"

    # Construir ruta completa al archivo
    filepath = os.path.join(STATIC_DIR, filename)

    # Log para debugging
    print(f"Path solicitado: {event.get('path')} | Proxy: {proxy_path} | Archivo: {filepath}")

    # Verificar que el archivo existe
    if not os.path.isfile(filepath):
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": f"<h1>404 - No encontrado: {filename}</h1>",
        }

    # Determinar el content-type
    ext = os.path.splitext(filename)[1].lower()
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

    # Leer el archivo como texto
    with open(filepath, "r", encoding="utf-8") as f:
        body = f.read()

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=300",
        },
        "body": body,
    }
