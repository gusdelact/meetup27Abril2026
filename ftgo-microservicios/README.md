# 🍔 FTGO Microservicios — Arquitectura Serverless en AWS

Refactorización del monolito FTGO a microservicios serverless.
Ejemplo educativo basado en el libro *"Microservice Patterns"* de Chris Richardson.

---

## ¿Qué cambió respecto al monolito?

| Antes (Monolito) | Ahora (Microservicios) |
|-------------------|------------------------|
| Un solo proceso FastAPI | 5 funciones Lambda independientes |
| Una base de datos SQLite | 5 tablas DynamoDB (una por dominio) |
| Un solo despliegue | Cada servicio se despliega por separado |
| Frontend servido por FastAPI | Frontend en S3 + CloudFront |
| Despliegue manual con scp | Automatizado con GitHub Actions |

---

## Estructura del proyecto

```
ftgo-microservicios/
├── README.md                    ← Este archivo
├── DESIGN.md                    ← Documento de diseño y diagramas
├── DEPLOY.md                    ← Guía de despliegue y configuración AWS
│
├── frontend/                    ← Frontend (HTML/CSS/JS) hospedado en S3
│   ├── template.yaml            ← IaC: S3 + CloudFront
│   ├── static/
│   │   ├── index.html
│   │   ├── style.css
│   │   ├── config.js            ← URLs de cada API Gateway
│   │   └── app.js
│   └── .github/workflows/
│       └── deploy.yml
│
├── servicios/
│   ├── consumidores/            ← Microservicio de Consumidores
│   ├── restaurantes/            ← Microservicio de Restaurantes + Menú
│   ├── pedidos/                 ← Microservicio de Pedidos
│   ├── entregas/                ← Microservicio de Repartidores
│   └── pagos/                   ← Microservicio de Pagos
│
└── scripts/
    └── migrar_sqlite_a_dynamodb.py  ← Migración de datos
```

Cada microservicio tiene:
```
servicios/<nombre>/
├── template.yaml                ← IaC (SAM/CloudFormation)
├── src/
│   └── handler.py               ← Código de la Lambda
├── pyproject.toml               ← Dependencias (uv)
└── .github/workflows/
    └── deploy.yml               ← Pipeline CI/CD propio
```

---

## Inicio rápido (desde la instancia EC2 del alumno)

```bash
# 1. Conectarse a la instancia EC2
ssh -i tu-clave.pem ec2-user@<IP_DE_TU_EC2>

# 2. Clonar el repositorio
git clone https://github.com/<tu-org>/ftgo-microservicios.git
cd ftgo-microservicios

# 3. Ver la documentación
cat README.md
cat DESIGN.md
cat DEPLOY.md
```

Para instrucciones detalladas de despliegue, ver [DEPLOY.md](./DEPLOY.md).

---

## Tecnologías utilizadas

| Tecnología | Uso |
|------------|-----|
| Python 3.13 | Lenguaje de las Lambdas |
| AWS Lambda | Compute serverless |
| API Gateway | Exposición de APIs REST |
| DynamoDB | Base de datos NoSQL por dominio |
| S3 + CloudFront | Hosting del frontend |
| AWS SAM | Infraestructura como código |
| GitHub Actions | CI/CD (un pipeline por servicio) |
| uv | Gestor de dependencias Python |
| boto3 | SDK de AWS para Python |
