# Diseño de Arquitectura — FTGO Microservicios (Serverless AWS)

## 1. Visión General

Se refactoriza el monolito FTGO en microservicios serverless sobre AWS, siguiendo el patrón
"Database per Service". Cada dominio de negocio se implementa como un servicio independiente
con su propia base de datos DynamoDB, expuesto a través de API Gateway, y desplegado con
AWS SAM (Serverless Application Model) + CloudFormation.

---

## 2. Dominios de Negocio Identificados

| # | Dominio | Descripción | Entidades |
|---|---------|-------------|-----------|
| 1 | **Consumidores** | Gestión de clientes | Consumidor |
| 2 | **Restaurantes** | Gestión de restaurantes y menús | Restaurante, ElementoMenu |
| 3 | **Pedidos** | Ciclo de vida de pedidos | Pedido, ElementoPedido |
| 4 | **Entregas** | Gestión de repartidores y asignación | Repartidor |
| 5 | **Pagos** | Procesamiento de pagos | Pago |

Cada dominio:
- Tiene su propio repositorio de código (estructura de directorios independiente)
- Tiene su propia tabla DynamoDB
- Se expone como un API Gateway independiente
- Se despliega de forma independiente con su propio stack CloudFormation
- Puede evolucionar a una cuenta AWS separada

---

## 3. Diagrama de Arquitectura General

```mermaid
graph TB
    subgraph "Cliente"
        NAV[Navegador Web<br/>HTML/CSS/JS]
    end

    subgraph "Hosting Frontend"
        CF[CloudFront<br/>CDN Global]
        S3[S3 Bucket<br/>Archivos Estáticos]
    end

    subgraph "Microservicio Consumidores"
        APIGW_C[API Gateway<br/>/api/consumidores]
        LAMBDA_C[Lambda<br/>consumidores_handler]
        DDB_C[(DynamoDB<br/>ftgo-consumidores)]
    end

    subgraph "Microservicio Restaurantes"
        APIGW_R[API Gateway<br/>/api/restaurantes]
        LAMBDA_R[Lambda<br/>restaurantes_handler]
        DDB_R[(DynamoDB<br/>ftgo-restaurantes)]
    end

    subgraph "Microservicio Pedidos"
        APIGW_P[API Gateway<br/>/api/pedidos]
        LAMBDA_P[Lambda<br/>pedidos_handler]
        DDB_P[(DynamoDB<br/>ftgo-pedidos)]
    end

    subgraph "Microservicio Entregas"
        APIGW_E[API Gateway<br/>/api/repartidores]
        LAMBDA_E[Lambda<br/>entregas_handler]
        DDB_E[(DynamoDB<br/>ftgo-repartidores)]
    end

    subgraph "Microservicio Pagos"
        APIGW_PAG[API Gateway<br/>/api/pagos]
        LAMBDA_PAG[Lambda<br/>pagos_handler]
        DDB_PAG[(DynamoDB<br/>ftgo-pagos)]
    end

    NAV -->|HTTPS| CF
    CF --> S3
    NAV -->|REST API| APIGW_C
    NAV -->|REST API| APIGW_R
    NAV -->|REST API| APIGW_P
    NAV -->|REST API| APIGW_E
    NAV -->|REST API| APIGW_PAG

    APIGW_C --> LAMBDA_C
    LAMBDA_C --> DDB_C

    APIGW_R --> LAMBDA_R
    LAMBDA_R --> DDB_R

    APIGW_P --> LAMBDA_P
    LAMBDA_P --> DDB_P
    LAMBDA_P -.->|Valida consumidor| APIGW_C
    LAMBDA_P -.->|Valida restaurante/menú| APIGW_R

    APIGW_E --> LAMBDA_E
    LAMBDA_E --> DDB_E

    APIGW_PAG --> LAMBDA_PAG
    LAMBDA_PAG --> DDB_PAG
    LAMBDA_PAG -.->|Consulta pedido| APIGW_P

    style CF fill:#f9a825,stroke:#f57f17
    style S3 fill:#f9e79f,stroke:#f39c12
    style DDB_C fill:#a9dfbf,stroke:#27ae60
    style DDB_R fill:#a9dfbf,stroke:#27ae60
    style DDB_P fill:#a9dfbf,stroke:#27ae60
    style DDB_E fill:#a9dfbf,stroke:#27ae60
    style DDB_PAG fill:#a9dfbf,stroke:#27ae60
```

---

## 3.1 Diagrama de Infraestructura por Dominio (Detalle de un Microservicio)

```mermaid
graph LR
    subgraph "Stack CloudFormation — Microservicio Consumidores"
        direction TB
        APIGW[API Gateway REST<br/>ConsumidoresApi]
        ROLE[IAM Role<br/>LambdaExecutionRole]
        FN[Lambda Function<br/>ConsumidoresFunction<br/>Python 3.13]
        TABLE[(DynamoDB Table<br/>ftgo-consumidores<br/>PAY_PER_REQUEST)]
        LOGS[CloudWatch Logs<br/>/aws/lambda/consumidores]
    end

    APIGW -->|Invoke| FN
    FN -->|AssumeRole| ROLE
    FN -->|Read/Write| TABLE
    FN -->|Logs| LOGS
    ROLE -.->|Permite acceso a| TABLE
    ROLE -.->|Permite escribir en| LOGS

    style TABLE fill:#a9dfbf,stroke:#27ae60
    style FN fill:#aed6f1,stroke:#2980b9
    style APIGW fill:#f5cba7,stroke:#e67e22
```

---

## 3.2 Diagrama de Despliegue (CI/CD con GitHub Actions)

```mermaid
graph LR
    subgraph "Desarrollador"
        DEV[git push]
    end

    subgraph "GitHub"
        REPO[Repositorio]
        GHA[GitHub Actions<br/>Workflow]
    end

    subgraph "AWS"
        SAM[SAM Build<br/>+ Package]
        CFN[CloudFormation<br/>Deploy Stack]
        S3D[S3 Deploy<br/>Frontend]
        CFNINV[CloudFront<br/>Invalidation]
    end

    DEV --> REPO
    REPO -->|trigger| GHA
    GHA -->|sam build & deploy| SAM
    SAM --> CFN
    GHA -->|aws s3 sync| S3D
    S3D --> CFNINV

    style GHA fill:#d5f5e3,stroke:#27ae60
    style CFN fill:#aed6f1,stroke:#2980b9
```

---

## 4. Diseño de Tablas DynamoDB

### 4.0 Diagrama Entidad-Relación (DynamoDB — Separación por Dominio)

```mermaid
erDiagram
    CONSUMIDORES_TABLE {
        string id PK "UUID"
        string nombre
        string email "GSI: email-index"
        string telefono
        string direccion
        string fecha_registro "ISO 8601"
    }

    RESTAURANTES_TABLE {
        string PK PK "REST#id"
        string SK SK "METADATA | MENU#id"
        string tipo_entidad "restaurante | elemento_menu"
        string nombre
        string direccion
        string telefono
        string tipo_cocina
        string horario_apertura
        string horario_cierre
        string descripcion
        number precio
        number disponible
        string fecha_registro
    }

    PEDIDOS_TABLE {
        string PK PK "PED#id"
        string SK SK "METADATA | ELEM#id"
        string tipo_entidad "pedido | elemento_pedido"
        string consumidor_id "GSI: consumidor-index"
        string restaurante_id
        string repartidor_id
        string estado
        number total
        string direccion_entrega
        string elemento_menu_id
        number cantidad
        number precio_unitario
        number subtotal
        string fecha_creacion
        string fecha_actualizacion
    }

    REPARTIDORES_TABLE {
        string id PK "UUID"
        string nombre
        string telefono
        string vehiculo
        number disponible "GSI: disponible-index"
        string fecha_registro "ISO 8601"
    }

    PAGOS_TABLE {
        string id PK "UUID"
        string pedido_id "GSI: pedido-index"
        number monto
        string metodo_pago
        string estado
        string referencia
        string fecha_pago "ISO 8601"
    }

    CONSUMIDORES_TABLE ||--o{ PEDIDOS_TABLE : "referenciado por consumidor_id"
    RESTAURANTES_TABLE ||--o{ PEDIDOS_TABLE : "referenciado por restaurante_id"
    REPARTIDORES_TABLE ||--o{ PEDIDOS_TABLE : "referenciado por repartidor_id"
    PEDIDOS_TABLE ||--o| PAGOS_TABLE : "referenciado por pedido_id"
```

> **Nota:** En microservicios con DynamoDB, las relaciones son lógicas (no hay foreign keys).
> Cada tabla es independiente y pertenece a un servicio diferente. La integridad referencial
> se garantiza a nivel de aplicación (validación HTTP entre servicios).

### 4.1 Tabla: ftgo-consumidores

| Atributo | Tipo | Clave |
|----------|------|-------|
| id | String (UUID) | PK |
| nombre | String | - |
| email | String | GSI-PK (email-index) |
| telefono | String | - |
| direccion | String | - |
| fecha_registro | String (ISO 8601) | - |

### 4.2 Tabla: ftgo-restaurantes

Diseño de tabla única (single-table design) para restaurantes y menú:

| Atributo | Tipo | Clave |
|----------|------|-------|
| PK | String | PK |
| SK | String | SK |
| tipo_entidad | String | - |
| ...atributos | - | - |

Patrones de acceso:
- `PK=REST#<id>`, `SK=METADATA` → Datos del restaurante
- `PK=REST#<id>`, `SK=MENU#<menu_id>` → Elemento del menú

### 4.3 Tabla: ftgo-pedidos

| Atributo | Tipo | Clave |
|----------|------|-------|
| PK | String | PK |
| SK | String | SK |
| tipo_entidad | String | - |
| ...atributos | - | - |

Patrones de acceso:
- `PK=PED#<id>`, `SK=METADATA` → Datos del pedido
- `PK=PED#<id>`, `SK=ELEM#<elem_id>` → Elemento del pedido
- GSI: `consumidor_id-index` para buscar pedidos por consumidor

### 4.4 Tabla: ftgo-repartidores

| Atributo | Tipo | Clave |
|----------|------|-------|
| id | String (UUID) | PK |
| nombre | String | - |
| telefono | String | - |
| vehiculo | String | - |
| disponible | Number (0/1) | GSI-PK (disponible-index) |
| fecha_registro | String (ISO 8601) | - |

### 4.5 Tabla: ftgo-pagos

| Atributo | Tipo | Clave |
|----------|------|-------|
| id | String (UUID) | PK |
| pedido_id | String | GSI-PK (pedido-index) |
| monto | Number | - |
| metodo_pago | String | - |
| estado | String | - |
| referencia | String | - |
| fecha_pago | String (ISO 8601) | - |

---

## 5. API Endpoints (se mantienen iguales al monolito)

Cada API Gateway expone los mismos endpoints que el monolito, con CORS habilitado
para que el frontend en S3/CloudFront pueda invocarlos.

### Consumidores API (`https://<api-id>.execute-api.<region>.amazonaws.com/prod`)
| Método | Ruta | Lambda Handler |
|--------|------|----------------|
| POST | /api/consumidores/ | crear_consumidor |
| GET | /api/consumidores/ | listar_consumidores |
| GET | /api/consumidores/{id} | obtener_consumidor |
| PUT | /api/consumidores/{id} | actualizar_consumidor |
| DELETE | /api/consumidores/{id} | eliminar_consumidor |

### Restaurantes API
| Método | Ruta | Lambda Handler |
|--------|------|----------------|
| POST | /api/restaurantes/ | crear_restaurante |
| GET | /api/restaurantes/ | listar_restaurantes |
| GET | /api/restaurantes/{id} | obtener_restaurante |
| PUT | /api/restaurantes/{id} | actualizar_restaurante |
| DELETE | /api/restaurantes/{id} | eliminar_restaurante |
| POST | /api/restaurantes/{id}/menu/ | agregar_elemento_menu |
| GET | /api/restaurantes/{id}/menu/ | obtener_menu |
| PUT | /api/restaurantes/menu/{id} | actualizar_elemento_menu |
| DELETE | /api/restaurantes/menu/{id} | eliminar_elemento_menu |

### Pedidos API
| Método | Ruta | Lambda Handler |
|--------|------|----------------|
| POST | /api/pedidos/ | crear_pedido |
| GET | /api/pedidos/ | listar_pedidos |
| GET | /api/pedidos/{id} | obtener_pedido |
| PUT | /api/pedidos/{id}/estado | actualizar_estado |
| PUT | /api/pedidos/{id}/repartidor | asignar_repartidor |
| DELETE | /api/pedidos/{id} | cancelar_pedido |

### Entregas API
| Método | Ruta | Lambda Handler |
|--------|------|----------------|
| POST | /api/repartidores/ | crear_repartidor |
| GET | /api/repartidores/ | listar_repartidores |
| GET | /api/repartidores/{id} | obtener_repartidor |
| PUT | /api/repartidores/{id} | actualizar_repartidor |
| DELETE | /api/repartidores/{id} | eliminar_repartidor |

### Pagos API
| Método | Ruta | Lambda Handler |
|--------|------|----------------|
| POST | /api/pagos/ | procesar_pago |
| GET | /api/pagos/ | listar_pagos |
| GET | /api/pagos/{id} | obtener_pago |

---

## 6. Estructura de Directorios

```
ftgo-microservicios/
├── DESIGN.md                          ← Este documento
├── README.md                          ← Instrucciones generales
├── DEPLOY.md                          ← Guía de despliegue
│
├── frontend/                          ← Repositorio del frontend
│   ├── template.yaml                  ← CloudFormation (S3 + CloudFront)
│   ├── static/
│   │   ├── index.html
│   │   ├── style.css
│   │   └── app.js                     ← Actualizado para invocar múltiples APIs
│   └── .github/
│       └── workflows/
│           └── deploy.yml             ← Pipeline CI/CD frontend
│
├── servicios/
│   ├── consumidores/                  ← Microservicio Consumidores
│   │   ├── template.yaml             ← SAM/CloudFormation
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── handler.py            ← Lambda handler
│   │   ├── tests/
│   │   │   └── test_handler.py
│   │   ├── pyproject.toml
│   │   └── .github/
│   │       └── workflows/
│   │           └── deploy.yml
│   │
│   ├── restaurantes/                  ← Microservicio Restaurantes
│   │   ├── template.yaml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── handler.py
│   │   ├── tests/
│   │   │   └── test_handler.py
│   │   ├── pyproject.toml
│   │   └── .github/
│   │       └── workflows/
│   │           └── deploy.yml
│   │
│   ├── pedidos/                       ← Microservicio Pedidos
│   │   ├── template.yaml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── handler.py
│   │   ├── tests/
│   │   │   └── test_handler.py
│   │   ├── pyproject.toml
│   │   └── .github/
│   │       └── workflows/
│   │           └── deploy.yml
│   │
│   ├── entregas/                      ← Microservicio Entregas (Repartidores)
│   │   ├── template.yaml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   └── handler.py
│   │   ├── tests/
│   │   │   └── test_handler.py
│   │   ├── pyproject.toml
│   │   └── .github/
│   │       └── workflows/
│   │           └── deploy.yml
│   │
│   └── pagos/                         ← Microservicio Pagos
│       ├── template.yaml
│       ├── src/
│       │   ├── __init__.py
│       │   └── handler.py
│       ├── tests/
│       │   └── test_handler.py
│       ├── pyproject.toml
│       └── .github/
│           └── workflows/
│               └── deploy.yml
│
└── scripts/
    └── migrar_sqlite_a_dynamodb.py    ← Script de migración de datos
```

---

## 7. Tecnologías y Herramientas

| Componente | Tecnología |
|------------|-----------|
| Compute | AWS Lambda (Python 3.13) |
| API | API Gateway (REST) |
| Base de datos | DynamoDB (una tabla por dominio) |
| Frontend hosting | S3 + CloudFront |
| IaC | AWS SAM / CloudFormation |
| CI/CD | GitHub Actions |
| Dependencias | uv (pyproject.toml por servicio) |
| SDK AWS | boto3 |

---

## 8. Configuración del Frontend

El frontend se modifica para:
1. Usar URLs de API Gateway en lugar de rutas relativas
2. Configurar las URLs de cada microservicio via un archivo `config.js`
3. Habilitar CORS en cada API Gateway

```javascript
// config.js — URLs de los API Gateway de cada microservicio
const CONFIG = {
    API_CONSUMIDORES: "https://<api-id>.execute-api.<region>.amazonaws.com/prod",
    API_RESTAURANTES: "https://<api-id>.execute-api.<region>.amazonaws.com/prod",
    API_PEDIDOS: "https://<api-id>.execute-api.<region>.amazonaws.com/prod",
    API_ENTREGAS: "https://<api-id>.execute-api.<region>.amazonaws.com/prod",
    API_PAGOS: "https://<api-id>.execute-api.<region>.amazonaws.com/prod",
};
```

---

## 9. Pipeline de Despliegue (GitHub Actions)

Cada servicio tiene su propio pipeline que:
1. Se activa al hacer push a `main` (o al directorio del servicio)
2. Instala dependencias con `uv`
3. Ejecuta tests
4. Empaqueta con `sam build`
5. Despliega con `sam deploy`

```yaml
# Flujo simplificado
on:
  push:
    branches: [main]
    paths: ['servicios/consumidores/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/setup-sam@v2
      - uses: aws-actions/configure-aws-credentials@v4
      - run: sam build
      - run: sam deploy --no-confirm-changeset
```

---

## 10. Script de Migración SQLite → DynamoDB

El script `migrar_sqlite_a_dynamodb.py`:
1. Lee los datos de `ftgo-monolito/ftgo.db` usando SQLAlchemy
2. Transforma los registros al formato DynamoDB (con PKs/SKs apropiados)
3. Escribe en batch a cada tabla DynamoDB usando boto3

---

## 11. Consideraciones de Diseño

### 11.0 Diagrama de Estados del Pedido (sin cambios respecto al monolito)

```mermaid
stateDiagram-v2
    [*] --> CREADO : Consumidor crea pedido<br/>(Lambda Pedidos)

    CREADO --> ACEPTADO : Restaurante acepta<br/>(Lambda Pedidos)
    CREADO --> CANCELADO : Consumidor cancela<br/>(Lambda Pedidos)

    ACEPTADO --> PREPARANDO : Restaurante prepara<br/>(Lambda Pedidos)
    ACEPTADO --> CANCELADO : Cancelación

    PREPARANDO --> LISTO : Comida lista<br/>(Lambda Pedidos)
    PREPARANDO --> CANCELADO : Cancelación

    LISTO --> EN_CAMINO : Repartidor asignado<br/>(Lambda Pedidos + Lambda Entregas)

    EN_CAMINO --> ENTREGADO : Repartidor confirma<br/>(Lambda Pedidos)

    ENTREGADO --> [*]
    CANCELADO --> [*]

    note right of LISTO
        Al asignar repartidor se invoca
        el microservicio de Entregas
        para marcar disponible=0
    end note

    note right of ENTREGADO
        Después de entregar, el consumidor
        puede pagar via microservicio Pagos
    end note
```

### 11.1 Diagrama de Comunicación entre Microservicios

```mermaid
graph TD
    subgraph "Frontend (S3 + CloudFront)"
        FE[app.js<br/>Orquestador del cliente]
    end

    subgraph "Microservicios"
        MS_C[Consumidores]
        MS_R[Restaurantes]
        MS_P[Pedidos]
        MS_E[Entregas]
        MS_PAG[Pagos]
    end

    FE -->|CRUD consumidores| MS_C
    FE -->|CRUD restaurantes + menú| MS_R
    FE -->|Crear/gestionar pedidos| MS_P
    FE -->|CRUD repartidores| MS_E
    FE -->|Procesar pagos| MS_PAG

    MS_P -->|Validar consumidor existe| MS_C
    MS_P -->|Obtener menú y precios| MS_R
    MS_P -->|Marcar repartidor ocupado| MS_E
    MS_PAG -->|Obtener total del pedido| MS_P

    style FE fill:#fff3cd,stroke:#ffc107
    style MS_P fill:#d1ecf1,stroke:#0c5460
    style MS_PAG fill:#d1ecf1,stroke:#0c5460
```

### 11.1 Comunicación entre servicios
- En esta versión inicial, el frontend orquesta las llamadas (coreografía desde el cliente)
- El servicio de Pedidos necesita validar que existan el consumidor y restaurante:
  se hace una llamada HTTP interna al API Gateway de esos servicios
- En una evolución futura se podría usar EventBridge para comunicación asíncrona

### 11.2 Consistencia eventual
- Al separar las bases de datos, se pierde la transaccionalidad ACID entre dominios
- Se acepta consistencia eventual (patrón Saga simplificado)
- Si falla la validación del consumidor al crear un pedido, se retorna error inmediato

### 11.3 CORS
- Cada API Gateway configura CORS para permitir el dominio de CloudFront
- Headers: `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`

### 11.4 Evolución a multi-cuenta
- Cada stack CloudFormation es independiente
- Los API Gateway IDs se parametrizan en el frontend
- En el futuro, cada dominio puede vivir en su propia cuenta AWS con su propio pipeline

---

## 12. Diagrama de Secuencia — Crear Pedido (Microservicios)

```mermaid
sequenceDiagram
    actor Usuario
    participant FE as Frontend<br/>(S3 + CloudFront)
    participant APIGW_P as API Gateway<br/>Pedidos
    participant LBD_P as Lambda<br/>Pedidos
    participant APIGW_C as API Gateway<br/>Consumidores
    participant LBD_C as Lambda<br/>Consumidores
    participant APIGW_R as API Gateway<br/>Restaurantes
    participant LBD_R as Lambda<br/>Restaurantes
    participant DDB_P as DynamoDB<br/>ftgo-pedidos

    Usuario->>FE: Selecciona platillos y<br/>clic "Crear Pedido"
    FE->>APIGW_P: POST /api/pedidos/<br/>{consumidor_id, restaurante_id,<br/>direccion_entrega, elementos}
    APIGW_P->>LBD_P: Invoke

    Note over LBD_P: Validar consumidor
    LBD_P->>APIGW_C: GET /api/consumidores/{id}
    APIGW_C->>LBD_C: Invoke
    LBD_C-->>APIGW_C: 200 OK (consumidor)
    APIGW_C-->>LBD_P: Consumidor válido ✓

    Note over LBD_P: Validar restaurante y obtener menú
    LBD_P->>APIGW_R: GET /api/restaurantes/{id}/menu/
    APIGW_R->>LBD_R: Invoke
    LBD_R-->>APIGW_R: 200 OK (platillos)
    APIGW_R-->>LBD_P: Menú obtenido ✓

    Note over LBD_P: Calcular total y crear pedido
    LBD_P->>LBD_P: Validar platillos y calcular total

    LBD_P->>DDB_P: PutItem (pedido + elementos)
    DDB_P-->>LBD_P: OK

    LBD_P-->>APIGW_P: 201 Created {id, estado, total}
    APIGW_P-->>FE: 201 + pedido creado
    FE-->>Usuario: "Pedido creado correctamente"
```

---

## 12.1 Diagrama de Secuencia — Ciclo de Vida del Pedido (Microservicios)

```mermaid
sequenceDiagram
    actor Consumidor
    actor Restaurante
    actor Repartidor
    participant APIGW_P as API Gateway<br/>Pedidos
    participant LBD_P as Lambda<br/>Pedidos
    participant DDB_P as DynamoDB<br/>Pedidos
    participant APIGW_E as API Gateway<br/>Entregas
    participant LBD_E as Lambda<br/>Entregas
    participant DDB_E as DynamoDB<br/>Repartidores

    Note over Consumidor,DDB_E: FASE 1 — Creación
    Consumidor->>APIGW_P: POST /api/pedidos/
    APIGW_P->>LBD_P: Invoke
    LBD_P->>DDB_P: PutItem (estado=CREADO)
    LBD_P-->>Consumidor: Pedido #1 creado

    Note over Consumidor,DDB_E: FASE 2 — Restaurante gestiona
    Restaurante->>APIGW_P: PUT /api/pedidos/1/estado {ACEPTADO}
    APIGW_P->>LBD_P: Invoke
    LBD_P->>DDB_P: UpdateItem estado=ACEPTADO
    LBD_P-->>Restaurante: OK ✓

    Restaurante->>APIGW_P: PUT /api/pedidos/1/estado {PREPARANDO}
    APIGW_P->>LBD_P: Invoke
    LBD_P->>DDB_P: UpdateItem estado=PREPARANDO
    LBD_P-->>Restaurante: OK ✓

    Restaurante->>APIGW_P: PUT /api/pedidos/1/estado {LISTO}
    APIGW_P->>LBD_P: Invoke
    LBD_P->>DDB_P: UpdateItem estado=LISTO
    LBD_P-->>Restaurante: OK ✓

    Note over Consumidor,DDB_E: FASE 3 — Asignación y entrega
    APIGW_P->>LBD_P: PUT /api/pedidos/1/repartidor {repartidor_id:1}
    LBD_P->>APIGW_E: PUT /api/repartidores/1 (disponible=0)
    APIGW_E->>LBD_E: Invoke
    LBD_E->>DDB_E: UpdateItem disponible=0
    LBD_E-->>APIGW_E: OK
    APIGW_E-->>LBD_P: Repartidor actualizado
    LBD_P->>DDB_P: UpdateItem repartidor_id=1

    Repartidor->>APIGW_P: PUT /api/pedidos/1/estado {EN_CAMINO}
    APIGW_P->>LBD_P: Invoke
    LBD_P->>DDB_P: UpdateItem estado=EN_CAMINO
    LBD_P-->>Repartidor: OK ✓

    Repartidor->>APIGW_P: PUT /api/pedidos/1/estado {ENTREGADO}
    APIGW_P->>LBD_P: Invoke
    LBD_P->>DDB_P: UpdateItem estado=ENTREGADO
    LBD_P-->>Repartidor: OK ✓

    Note over Consumidor,DDB_E: FASE 4 — Pago (servicio separado)
```

---

## 12.2 Diagrama de Secuencia — Procesar Pago (Microservicios)

```mermaid
sequenceDiagram
    actor Consumidor
    participant FE as Frontend
    participant APIGW_PAG as API Gateway<br/>Pagos
    participant LBD_PAG as Lambda<br/>Pagos
    participant APIGW_P as API Gateway<br/>Pedidos
    participant LBD_P as Lambda<br/>Pedidos
    participant DDB_PAG as DynamoDB<br/>Pagos

    Consumidor->>FE: Selecciona pedido y método de pago
    FE->>APIGW_PAG: POST /api/pagos/<br/>{pedido_id, metodo_pago}
    APIGW_PAG->>LBD_PAG: Invoke

    Note over LBD_PAG: Validar pedido existe y obtener total
    LBD_PAG->>APIGW_P: GET /api/pedidos/{id}
    APIGW_P->>LBD_P: Invoke
    LBD_P-->>APIGW_P: 200 {id, total, estado}
    APIGW_P-->>LBD_PAG: Pedido válido (total=$250)

    Note over LBD_PAG: Simular procesamiento de pago
    LBD_PAG->>LBD_PAG: Generar referencia PAY-XXXX

    LBD_PAG->>DDB_PAG: PutItem (pago COMPLETADO)
    DDB_PAG-->>LBD_PAG: OK

    LBD_PAG-->>APIGW_PAG: 201 Created {pago}
    APIGW_PAG-->>FE: Pago procesado ✓
    FE-->>Consumidor: "Pago procesado correctamente"
```

---

## 13. Resumen de Cambios vs. Monolito

### 13.0 Diagrama Comparativo: Monolito vs. Microservicios

```mermaid
graph TB
    subgraph "ANTES — Monolito"
        direction TB
        EC2[EC2 Instance]
        subgraph "Un solo proceso FastAPI"
            R1[Router Consumidores]
            R2[Router Restaurantes]
            R3[Router Pedidos]
            R4[Router Repartidores]
            R5[Router Pagos]
            STATIC[Static Files Server]
        end
        SQLITE[(SQLite3<br/>ftgo.db<br/>TODAS las tablas)]

        EC2 --> R1
        EC2 --> R2
        EC2 --> R3
        EC2 --> R4
        EC2 --> R5
        EC2 --> STATIC
        R1 --> SQLITE
        R2 --> SQLITE
        R3 --> SQLITE
        R4 --> SQLITE
        R5 --> SQLITE
    end

    subgraph "DESPUÉS — Microservicios Serverless"
        direction TB
        CF2[CloudFront + S3]
        L1[Lambda Consumidores]
        L2[Lambda Restaurantes]
        L3[Lambda Pedidos]
        L4[Lambda Entregas]
        L5[Lambda Pagos]
        D1[(DynamoDB<br/>Consumidores)]
        D2[(DynamoDB<br/>Restaurantes)]
        D3[(DynamoDB<br/>Pedidos)]
        D4[(DynamoDB<br/>Repartidores)]
        D5[(DynamoDB<br/>Pagos)]

        L1 --> D1
        L2 --> D2
        L3 --> D3
        L4 --> D4
        L5 --> D5
    end

    style SQLITE fill:#f9e79f,stroke:#f39c12
    style D1 fill:#a9dfbf,stroke:#27ae60
    style D2 fill:#a9dfbf,stroke:#27ae60
    style D3 fill:#a9dfbf,stroke:#27ae60
    style D4 fill:#a9dfbf,stroke:#27ae60
    style D5 fill:#a9dfbf,stroke:#27ae60
    style EC2 fill:#f5b7b1,stroke:#e74c3c
    style CF2 fill:#f9a825,stroke:#f57f17
```

| Aspecto | Monolito | Microservicios |
|---------|----------|----------------|
| Compute | EC2 + uvicorn | AWS Lambda |
| Framework | FastAPI | Lambda handlers nativos |
| Base de datos | SQLite3 (un archivo) | DynamoDB (una tabla por dominio) |
| API | FastAPI routers | API Gateway REST |
| Frontend | Servido por FastAPI | S3 + CloudFront |
| Despliegue | scp + systemd | SAM + GitHub Actions |
| Escalamiento | Vertical (instancia más grande) | Automático (Lambda) |
| Costo en reposo | ~$25/mes (EC2 siempre encendida) | ~$0 (pay-per-request) |
| IaC | Manual | CloudFormation/SAM |

---

**¿Procedo con la generación del código?** Confirma y empiezo a crear los archivos de cada microservicio, el frontend actualizado, los templates SAM, los pipelines de GitHub Actions y el script de migración.
