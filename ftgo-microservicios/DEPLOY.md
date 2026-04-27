# Guía de Despliegue — FTGO Microservicios Serverless

## 1. Prerrequisitos

| Herramienta | Versión mínima | Instalación |
|-------------|---------------|-------------|
| AWS CLI | 2.x | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| AWS SAM CLI | 1.100+ | [docs.aws.amazon.com/sam](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Python | 3.13+ | [python.org](https://www.python.org/downloads/) |
| uv | 0.4+ | [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Git | 2.x | [git-scm.com](https://git-scm.com/) |
| Cuenta AWS | - | Con permisos de administrador o los permisos listados abajo |
| Cuenta GitHub | - | Para repositorios y GitHub Actions |

---

## 1.1 Preparar la Instancia EC2 del Alumno

El alumno trabaja desde una instancia EC2 conectándose por SSH.
A continuación se detallan los pasos para preparar el ambiente de trabajo.

### Conectarse a la instancia EC2

```bash
# Desde tu computadora local, conectarse por SSH
ssh -i tu-clave.pem ec2-user@<IP_PUBLICA_DE_TU_EC2>
```

> Si usas Windows, puedes usar PuTTY o el terminal de Windows (WSL).
> La clave `.pem` la proporciona el profesor o se descarga al crear la instancia.

### Instalar herramientas necesarias en la EC2

```bash
# 1. Actualizar el sistema
sudo dnf update -y

# 2. Instalar Git
sudo dnf install git -y

# 3. Instalar Python 3.13 (Amazon Linux 2023)
sudo dnf install python3.13 python3.13-pip -y

# 4. Instalar uv (gestor de paquetes Python)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 5. Instalar AWS CLI v2 (si no viene preinstalado)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip

# 6. Instalar AWS SAM CLI
pip3.13 install aws-sam-cli --user
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 7. Verificar instalaciones
git --version
python3.13 --version
uv --version
aws --version
sam --version
```

### Configurar credenciales AWS en la EC2

```bash
# Configurar las credenciales temporales de IAM Identity Center
# Copiar las 3 líneas del portal de AWS Access y pegarlas aquí:
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."
export AWS_DEFAULT_REGION="us-east-1"

# Verificar que las credenciales funcionan
aws sts get-caller-identity
```

Te debe mostrar algo como:
```json
{
    "UserId": "AROA...:alumno@universidad.edu",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_.../alumno@universidad.edu"
}
```

> **¿De dónde saco las credenciales?**
> 1. Ir al portal de acceso: `https://<tu-org>.awsapps.com/start`
> 2. Seleccionar la cuenta AWS del ejercicio
> 3. Clic en **"Command line or programmatic access"**
> 4. Copiar las líneas de `export` y pegarlas en la terminal de la EC2
>
> Las credenciales son temporales (expiran en 1-12 horas).
> Si ves el error `ExpiredTokenException`, repite el proceso.

### Clonar el repositorio

```bash
# Clonar el proyecto
git clone https://github.com/<tu-org>/ftgo-microservicios.git
cd ftgo-microservicios

# Ver la estructura
ls -la
ls servicios/
```

### Desplegar un microservicio desde la EC2 (manual)

```bash
# Ejemplo: desplegar el microservicio de consumidores
cd servicios/consumidores

# Construir el paquete Lambda
sam build

# Desplegar (la primera vez usar --guided para configuración interactiva)
sam deploy --guided

# Las siguientes veces solo:
sam deploy --no-confirm-changeset --capabilities CAPABILITY_IAM --resolve-s3
```

> `sam deploy --guided` te preguntará:
> - Stack Name: `ftgo-consumidores`
> - AWS Region: `us-east-1`
> - Confirm changes before deploy: `N`
> - Allow SAM CLI IAM role creation: `Y`
> - Save arguments to samconfig.toml: `Y`

### Desplegar el frontend desde la EC2

```bash
cd ~/ftgo-microservicios/frontend

# Construir y desplegar (Lambda + API Gateway)
sam build
sam deploy --guided

# La URL del frontend se muestra en los Outputs del stack
```

### Ejecutar la migración de datos

```bash
cd ~/ftgo-microservicios/scripts

# Instalar dependencias
pip3.13 install boto3

# Copiar la base de datos del monolito (si está en la misma EC2)
# Si no, copiarla con scp desde otra máquina

# Ejecutar migración
python3.13 migrar_sqlite_a_dynamodb.py
```

---

## 2. Configuración de Credenciales AWS para GitHub Actions

En este ejercicio se usan cuentas AWS federadas con **IAM Identity Center** (antes SSO).
Esto significa que las credenciales son temporales y se componen de tres valores:
- `AWS_ACCESS_KEY_ID` — identificador de la llave temporal
- `AWS_SECRET_ACCESS_KEY` — llave secreta temporal
- `AWS_SESSION_TOKEN` — token de sesión (obligatorio en cuentas federadas)

> **¿Por qué tres valores?** Cuando usas IAM Identity Center, AWS te da credenciales
> temporales (duran entre 1 y 12 horas). El `SESSION_TOKEN` le dice a AWS que estas
> credenciales vienen de una sesión federada y cuándo expiran.

### 2.1 Obtener las credenciales temporales desde IAM Identity Center

#### Opción A: Desde el portal de AWS Access

1. Ir al portal de acceso de tu organización:
   `https://<tu-org>.awsapps.com/start`
2. Seleccionar la cuenta AWS asignada para el ejercicio
3. Clic en **"Command line or programmatic access"**
4. Copiar las tres credenciales que aparecen:

```
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."
```

#### Opción B: Usando AWS CLI con SSO

```bash
# Configurar el perfil SSO (solo la primera vez)
aws configure sso
# Te pedirá:
#   SSO session name: ftgo
#   SSO start URL: https://<tu-org>.awsapps.com/start
#   SSO region: us-east-1
#   SSO registration scopes: sso:account:access

# Iniciar sesión (abre el navegador)
aws sso login --profile ftgo

# Exportar credenciales para que SAM y boto3 las usen
eval $(aws configure export-credentials --profile ftgo --format env)
```

### 2.2 Configurar Secrets en GitHub (para GitHub Actions)

Las credenciales temporales de IAM Identity Center se configuran como
secrets en el repositorio de GitHub.

> **⚠️ Importante:** Como las credenciales son temporales (expiran),
> deberás actualizarlas en GitHub cada vez que expiren. Para un ejercicio
> de clase esto es aceptable. En producción se usaría OIDC.

#### Paso 1: Ir a la configuración de Secrets

1. Ir al repositorio en GitHub
2. Clic en **Settings** (pestaña superior)
3. En el menú lateral: **Secrets and variables → Actions**
4. Clic en **New repository secret**

#### Paso 2: Crear los tres secrets

| Nombre del Secret | Valor | Descripción |
|-------------------|-------|-------------|
| `AWS_ACCESS_KEY_ID` | `ASIA...` | Empieza con ASIA (credencial temporal) |
| `AWS_SECRET_ACCESS_KEY` | `...` | Llave secreta temporal |
| `AWS_SESSION_TOKEN` | `...` | Token de sesión (largo, ~800 caracteres) |
| `AWS_REGION` | `us-east-1` | Región donde se despliega |

> **Nota:** Las credenciales de IAM Identity Center empiezan con `ASIA`
> (no con `AKIA` como las permanentes). Si ves `ASIA`, es correcto.

#### Paso 3: Uso en el workflow de GitHub Actions

```yaml
- name: Configurar credenciales AWS (IAM Identity Center)
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-session-token: ${{ secrets.AWS_SESSION_TOKEN }}
    aws-region: ${{ secrets.AWS_REGION }}
```

### 2.3 Configurar credenciales en la instancia EC2 del alumno

Cuando trabajas directamente desde la EC2 (sin GitHub Actions), configura
las credenciales temporales así:

```bash
# Opción 1: Exportar como variables de entorno (recomendado para temporales)
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."
export AWS_DEFAULT_REGION="us-east-1"

# Verificar que funcionan
aws sts get-caller-identity
# Debe mostrar tu cuenta y rol federado

# Opción 2: Usar aws configure (NO soporta session token directamente)
# Para credenciales temporales es mejor usar variables de entorno
```

> **Tip:** Puedes pegar las tres líneas `export` directamente en la terminal
> de tu EC2. Las credenciales estarán activas mientras la sesión SSH esté abierta
> o hasta que expiren (normalmente 1-12 horas según la configuración del profesor).

#### Renovar credenciales expiradas

Cuando las credenciales expiran verás un error como:
```
An error occurred (ExpiredTokenException): The security token included in the request is expired
```

Para renovar:
1. Volver al portal de AWS Access (`https://<tu-org>.awsapps.com/start`)
2. Copiar las nuevas credenciales
3. Pegarlas en la terminal de la EC2 (o actualizar los secrets en GitHub)

---

### 2.3 Política IAM de Permisos Mínimos

Esta política otorga los permisos necesarios para desplegar con SAM:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationFullAccess",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:ValidateTemplate",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListStackResources"
      ],
      "Resource": "arn:aws:cloudformation:*:<TU_CUENTA_ID>:stack/ftgo-*/*"
    },
    {
      "Sid": "LambdaManagement",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:ListFunctions",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:TagResource",
        "lambda:PublishVersion",
        "lambda:CreateAlias"
      ],
      "Resource": "arn:aws:lambda:*:<TU_CUENTA_ID>:function:ftgo-*"
    },
    {
      "Sid": "APIGatewayManagement",
      "Effect": "Allow",
      "Action": [
        "apigateway:GET",
        "apigateway:POST",
        "apigateway:PUT",
        "apigateway:DELETE",
        "apigateway:PATCH"
      ],
      "Resource": "arn:aws:apigateway:*::*"
    },
    {
      "Sid": "DynamoDBManagement",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:DescribeTimeToLive"
      ],
      "Resource": "arn:aws:dynamodb:*:<TU_CUENTA_ID>:table/ftgo-*"
    },
    {
      "Sid": "S3Artifacts",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    },
    {
      "Sid": "IAMRolesForLambda",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PassRole",
        "iam:TagRole"
      ],
      "Resource": "arn:aws:iam::<TU_CUENTA_ID>:role/ftgo-*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy",
        "logs:TagResource"
      ],
      "Resource": "arn:aws:logs:*:<TU_CUENTA_ID>:log-group:/aws/lambda/ftgo-*"
    },
    {
      "Sid": "SAMManagedBucket",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning",
        "s3:PutBucketPolicy",
        "s3:PutLifecycleConfiguration",
        "s3:PutBucketTagging",
        "s3:PutEncryptionConfiguration",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    }
  ]
}
```

> **Reemplazar** `<TU_CUENTA_ID>` con tu ID de cuenta AWS de 12 dígitos.

---

## 3. Configuración de Secrets en GitHub (Resumen)

### 3.1 Secrets requeridos por repositorio

| Secret | Descripción | Ejemplo |
|--------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | Access Key temporal (IAM Identity Center) | `ASIA...` (empieza con ASIA) |
| `AWS_SECRET_ACCESS_KEY` | Secret Key temporal | `wJalrXUtnFEMI/...` |
| `AWS_SESSION_TOKEN` | Token de sesión (obligatorio con Identity Center) | `IQoJb3JpZ2luX2V...` (~800 chars) |
| `AWS_REGION` | Región de despliegue | `us-east-1` |

> **⚠️ Recordatorio:** Estos secrets son temporales. Cuando expiren, el pipeline
> fallará con `ExpiredTokenException`. Deberás ir al portal de AWS Access,
> obtener nuevas credenciales y actualizar los 3 secrets en GitHub.

### 3.2 Variables de entorno (opcionales, no secretas)

Ir a **Settings → Secrets and variables → Actions → Variables**:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `API_CONSUMIDORES_URL` | URL del API de consumidores (para el servicio de Pedidos) | `https://abc123.execute-api...` |
| `API_RESTAURANTES_URL` | URL del API de restaurantes (para el servicio de Pedidos) | `https://def456.execute-api...` |
| `API_ENTREGAS_URL` | URL del API de entregas (para el servicio de Pedidos) | `https://ghi789.execute-api...` |
| `API_PEDIDOS_URL` | URL del API de pedidos (para el servicio de Pagos) | `https://jkl012.execute-api...` |

### 3.3 Cómo crear un Secret en GitHub

1. Ir al repositorio en GitHub
2. Clic en **Settings** (pestaña superior)
3. En el menú lateral: **Secrets and variables → Actions**
4. Clic en **New repository secret**
5. Ingresar el nombre y valor
6. Clic en **Add secret**

> **Para organizaciones:** se pueden crear secrets a nivel de organización
> y compartirlos entre repositorios. Ir a **Organization Settings →
> Secrets and variables → Actions**.

---

## 4. Estructura de los Workflows de GitHub Actions

### 4.1 Workflow para un Microservicio (ejemplo: consumidores)

```yaml
# .github/workflows/deploy-consumidores.yml
name: Deploy Microservicio Consumidores

on:
  push:
    branches: [main]
    paths:
      - 'servicios/consumidores/**'
  workflow_dispatch:  # Permite ejecución manual

permissions:
  contents: read

env:
  AWS_REGION: us-east-1
  STACK_NAME: ftgo-consumidores
  SERVICE_PATH: servicios/consumidores

jobs:
  test:
    name: Ejecutar Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout código
        uses: actions/checkout@v4

      - name: Instalar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Instalar uv
        uses: astral-sh/setup-uv@v4

      - name: Instalar dependencias
        working-directory: ${{ env.SERVICE_PATH }}
        run: |
          uv venv
          uv sync

      - name: Ejecutar tests
        working-directory: ${{ env.SERVICE_PATH }}
        run: uv run pytest tests/ -v

  deploy:
    name: Desplegar a AWS
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout código
        uses: actions/checkout@v4

      - name: Instalar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Instalar AWS SAM CLI
        uses: aws-actions/setup-sam@v2

      - name: Configurar credenciales AWS (IAM Identity Center)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-session-token: ${{ secrets.AWS_SESSION_TOKEN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Instalar uv
        uses: astral-sh/setup-uv@v4

      - name: Instalar dependencias para empaquetado
        working-directory: ${{ env.SERVICE_PATH }}
        run: |
          uv venv
          uv sync

      - name: SAM Build
        working-directory: ${{ env.SERVICE_PATH }}
        run: sam build

      - name: SAM Deploy
        working-directory: ${{ env.SERVICE_PATH }}
        run: |
          sam deploy \
            --stack-name ${{ env.STACK_NAME }} \
            --region ${{ env.AWS_REGION }} \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset \
            --capabilities CAPABILITY_IAM \
            --resolve-s3

      - name: Obtener URL del API
        working-directory: ${{ env.SERVICE_PATH }}
        run: |
          API_URL=$(aws cloudformation describe-stacks \
            --stack-name ${{ env.STACK_NAME }} \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
            --output text)
          echo "🚀 API desplegada en: $API_URL"
```

### 4.2 Workflow para el Frontend

```yaml
# .github/workflows/deploy-frontend.yml
name: Deploy Frontend (Lambda + API Gateway)

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
  workflow_dispatch:

permissions:
  contents: read

env:
  AWS_REGION: us-east-1
  STACK_NAME: ftgo-frontend

jobs:
  deploy:
    name: Desplegar Frontend
    runs-on: ubuntu-latest
    steps:
      - name: Checkout código
        uses: actions/checkout@v4

      - name: Instalar AWS SAM CLI
        uses: aws-actions/setup-sam@v2

      - name: Configurar credenciales AWS (IAM Identity Center)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-session-token: ${{ secrets.AWS_SESSION_TOKEN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: SAM Build
        working-directory: frontend
        run: sam build

      - name: SAM Deploy
        working-directory: frontend
        run: |
          sam deploy \
            --stack-name ${{ env.STACK_NAME }} \
            --region ${{ env.AWS_REGION }} \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset \
            --capabilities CAPABILITY_IAM \
            --resolve-s3

      - name: Obtener URL del frontend
        run: |
          URL=$(aws cloudformation describe-stacks \
            --stack-name ${{ env.STACK_NAME }} \
            --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
            --output text)
          echo "🚀 Frontend desplegado en: $URL"
```

---

## 5. Despliegue Manual (sin GitHub Actions)

Si prefieres desplegar desde tu instancia EC2 directamente:

```bash
# 1. Configurar credenciales temporales de IAM Identity Center
#    (copiar del portal de AWS Access)
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."
export AWS_DEFAULT_REGION="us-east-1"

# 2. Verificar credenciales
aws sts get-caller-identity

# 3. Desplegar un microservicio (ejemplo: consumidores)
cd servicios/consumidores
sam build
sam deploy --guided
# La primera vez usa --guided para configurar interactivamente
# Las siguientes veces solo: sam deploy

# 4. Desplegar el frontend
cd ../../frontend
sam build
sam deploy --guided
```

> **Nota:** Si las credenciales expiran durante el despliegue, verás
> `ExpiredTokenException`. Obtén nuevas credenciales del portal y
> vuelve a exportarlas.

---

## 6. Orden de Despliegue

Los servicios deben desplegarse en este orden (por dependencias):

```
1. ftgo-consumidores    (sin dependencias)
2. ftgo-restaurantes    (sin dependencias)
3. ftgo-repartidores    (sin dependencias)
4. ftgo-pedidos         (depende de consumidores, restaurantes, repartidores)
5. ftgo-pagos           (depende de pedidos)
6. ftgo-frontend        (depende de todos los APIs — las URLs se configuran en el HTML)
```

> Después del primer despliegue, cada servicio se puede actualizar
> de forma independiente sin afectar a los demás.

---

## 7. Configuración del Frontend Post-Despliegue

Después de desplegar todos los microservicios, actualizar `frontend/static/config.js`
con las URLs reales de cada API Gateway:

```bash
# Obtener las URLs de cada stack
aws cloudformation describe-stacks --stack-name ftgo-consumidores \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text

aws cloudformation describe-stacks --stack-name ftgo-restaurantes \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text

aws cloudformation describe-stacks --stack-name ftgo-pedidos \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text

aws cloudformation describe-stacks --stack-name ftgo-repartidores \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text

aws cloudformation describe-stacks --stack-name ftgo-pagos \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text
```

Actualizar `config.js` y redesplegar el frontend.

---

## 8. Verificación del Despliegue

```bash
# Verificar que cada API responde
curl https://<API_CONSUMIDORES>/api/consumidores/
curl https://<API_RESTAURANTES>/api/restaurantes/
curl https://<API_PEDIDOS>/api/pedidos/
curl https://<API_REPARTIDORES>/api/repartidores/
curl https://<API_PAGOS>/api/pagos/

# Verificar el frontend
curl https://<FRONTEND_API_URL>/
```

---

## 9. Limpieza de Recursos

Para eliminar todos los recursos y evitar costos:

```bash
# Eliminar en orden inverso
sam delete --stack-name ftgo-frontend --no-prompts
sam delete --stack-name ftgo-pagos --no-prompts
sam delete --stack-name ftgo-pedidos --no-prompts
sam delete --stack-name ftgo-repartidores --no-prompts
sam delete --stack-name ftgo-restaurantes --no-prompts
sam delete --stack-name ftgo-consumidores --no-prompts
```

---

## 10. Costos Estimados (Serverless)

| Recurso | Costo |
|---------|-------|
| Lambda | Gratis hasta 1M requests/mes (Free Tier) |
| API Gateway | Gratis hasta 1M requests/mes (Free Tier, 12 meses) |
| DynamoDB | Gratis hasta 25 GB + 25 WCU/RCU (Free Tier) |
| S3 (artefactos SAM) | Gratis hasta 5 GB (Free Tier, 12 meses) |
| **Total (uso educativo)** | **~$0 USD/mes** con Free Tier |

> Para un ejercicio educativo con poco tráfico, el costo es prácticamente
> cero mientras se esté dentro del Free Tier de AWS.
