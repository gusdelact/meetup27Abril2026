"""
Handler Lambda — Frontend FTGO.

Sirve el frontend como un único archivo HTML con CSS y JS inline.
Esto evita problemas de routing con API Gateway para archivos estáticos.
"""

import os


def lambda_handler(event, context):
    """Sirve el index.html con todo el CSS y JS inline."""
    filepath = os.path.join(os.path.dirname(__file__), "static", "index.html")

    with open(filepath, "r", encoding="utf-8") as f:
        body = f.read()

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
        },
        "body": body,
    }
