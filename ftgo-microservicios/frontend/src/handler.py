"""
Handler Lambda — Frontend FTGO (Static Site Server).

╔══════════════════════════════════════════════════════════════════════╗
║  FRONTEND — FTGO (Food To Go Online)                               ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Responsabilidad:                                                    ║
║    Servir el frontend de la aplicación como un único archivo HTML    ║
║    con CSS y JavaScript inline (embebidos dentro del HTML).          ║
║                                                                      ║
║  ¿Por qué una Lambda para servir HTML?                               ║
║    En una arquitectura serverless con API Gateway, servir archivos   ║
║    estáticos (CSS, JS, imágenes) desde múltiples rutas es complejo   ║
║    porque API Gateway está diseñado para APIs, no para hosting       ║
║    estático. Al empaquetar todo en un solo HTML con CSS/JS inline,   ║
║    evitamos problemas de routing para archivos estáticos.            ║
║                                                                      ║
║  Alternativas en producción:                                         ║
║    • Amazon S3 + CloudFront → Hosting estático más eficiente         ║
║    • AWS Amplify → Hosting con CI/CD integrado                       ║
║    • La Lambda es una solución simple para este ejemplo educativo    ║
║                                                                      ║
║  Operación expuesta:                                                 ║
║    GET / → Devuelve el archivo index.html completo                   ║
║                                                                      ║
║  Infraestructura AWS:                                                ║
║    • AWS Lambda      → Ejecuta este código y lee el archivo HTML     ║
║    • API Gateway     → Recibe la petición GET y la enruta            ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os  # Módulo para manipulación de rutas del sistema de archivos


def lambda_handler(event, context):
    """
    Sirve el archivo index.html con todo el CSS y JS inline.

    Parámetros:
    ───────────
    event : dict
        Información de la petición HTTP desde API Gateway.
        Para este handler, no se usa ningún campo del event porque
        siempre devuelve el mismo archivo HTML sin importar la ruta.

    context : LambdaContext
        Metadatos del entorno de ejecución Lambda (no se usa aquí).

    Retorna:
    ────────
    dict : Respuesta HTTP con:
        - statusCode: 200
        - headers: Content-Type text/html + CORS
        - body: Contenido completo del archivo index.html

    Implementación:
    ───────────────
    1. Construye la ruta absoluta al archivo index.html:
       - __file__ → ruta de este archivo handler.py
       - os.path.dirname(__file__) → directorio donde está handler.py (src/)
       - os.path.join(..., "static", "index.html") → src/static/index.html

       Se usa os.path en vez de una ruta hardcodeada porque Lambda puede
       desplegar el código en diferentes directorios del sistema de archivos
       según la versión y la región.

    2. Lee el archivo HTML completo como string UTF-8.

    3. Devuelve la respuesta con Content-Type "text/html" (no "application/json"
       como los otros servicios) para que el navegador lo renderice como página web.

    Nota sobre CORS:
    ────────────────
    Access-Control-Allow-Origin: "*" permite que cualquier dominio cargue
    este HTML. En producción se restringiría al dominio específico.
    """
    # Construir la ruta absoluta al archivo index.html
    # __file__ = /var/task/src/handler.py (en Lambda)
    # dirname  = /var/task/src/
    # filepath = /var/task/src/static/index.html
    filepath = os.path.join(os.path.dirname(__file__), "static", "index.html")

    # Leer el contenido completo del archivo HTML
    with open(filepath, "r", encoding="utf-8") as f:
        body = f.read()

    # Devolver como respuesta HTTP con Content-Type text/html
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",  # Indica al navegador que es HTML
            "Access-Control-Allow-Origin": "*",           # Permite CORS
        },
        "body": body,  # El HTML completo como string (no JSON)
    }
