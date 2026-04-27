# Permisos del Permission Set — IAM Identity Center

## Contexto

Este documento detalla los permisos que debe tener el **Permission Set** de
AWS IAM Identity Center (antes SSO) para que los alumnos puedan desplegar
el proyecto FTGO Microservicios desde una instancia EC2.

El Permission Set se asigna a los usuarios/grupos en IAM Identity Center
y determina qué acciones pueden realizar en las cuentas AWS del ejercicio.

> **Multi-cuenta:** Este Permission Set se asigna a múltiples cuentas AWS
> (una por alumno o equipo). Los ARNs usan `*` en lugar de un Account ID
> fijo para que la misma política funcione en cualquier cuenta donde se asigne.

---

## Resumen de Servicios AWS Requeridos

| Servicio | Por qué se necesita |
|----------|---------------------|
| CloudFormation | SAM usa CloudFormation para crear/actualizar stacks |
| Lambda | Crear y actualizar las funciones de cada microservicio + frontend |
| API Gateway | SAM crea un API Gateway REST por cada servicio + frontend |
| DynamoDB | Crear tablas (deploy) + escribir datos (migración) |
| IAM | SAM crea roles de ejecución para cada Lambda |
| S3 | Bucket de artefactos SAM |
| CloudWatch Logs | Log groups de las Lambdas |
| EC2 | Instancia del monolito + security groups |
| Elastic Load Balancing | Network Load Balancer del monolito |
| STS | Verificar que las credenciales funcionan |

---

## Opción A: Política Granular (Mínimo Privilegio)

Recomendada para enseñar buenas prácticas de seguridad.
Los ARNs usan `*` en el campo de Account ID para que la misma política
funcione en cualquier cuenta donde se asigne el Permission Set.

### 1. Permisos para desplegar microservicios (`sam deploy`)

Cubre: CloudFormation, Lambda, API Gateway, DynamoDB, IAM Roles, CloudWatch Logs
y el bucket de artefactos que SAM crea automáticamente.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationDeploy",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:ListStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:GetTemplateSummary",
        "cloudformation:ValidateTemplate",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListChangeSets"
      ],
      "Resource": [
        "arn:aws:cloudformation:*:*:stack/ftgo-*/*",
        "arn:aws:cloudformation:*:*:stack/aws-sam-cli-managed-default/*"
      ]
    },
    {
      "Sid": "CloudFormationTransform",
      "Effect": "Allow",
      "Action": "cloudformation:CreateChangeSet",
      "Resource": "arn:aws:cloudformation:*:aws:transform/Serverless-2016-10-31"
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
        "lambda:ListVersionsByFunction",
        "lambda:PublishVersion",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:TagResource",
        "lambda:UntagResource"
      ],
      "Resource": "arn:aws:lambda:*:*:function:ftgo-*"
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
      "Resource": [
        "arn:aws:apigateway:*::/restapis",
        "arn:aws:apigateway:*::/restapis/*"
      ]
    },
    {
      "Sid": "DynamoDBTableManagement",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:ListTagsOfResource"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/ftgo-*"
    },
    {
      "Sid": "IAMRolesForLambda",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": "arn:aws:iam::*:role/ftgo-*"
    },
    {
      "Sid": "IAMPassRoleToLambda",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/ftgo-*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "lambda.amazonaws.com"
        }
      }
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
        "logs:TagResource",
        "logs:TagLogGroup"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/ftgo-*"
    },
    {
      "Sid": "SAMManagedArtifactBucket",
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
        "s3:GetBucketPolicy",
        "s3:PutLifecycleConfiguration",
        "s3:PutBucketTagging",
        "s3:GetBucketTagging",
        "s3:PutEncryptionConfiguration",
        "s3:GetEncryptionConfiguration",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    }
  ]
}
```

---

### 2. Permisos para el bucket de artefactos SAM (adicional)

El bucket de artefactos SAM ya está cubierto en la sección 1 (`SAMManagedArtifactBucket`).
No se requieren permisos adicionales de S3 o CloudFront ya que el frontend se despliega
como Lambda + API Gateway (mismo patrón que los microservicios).

---

### 3. Permisos para la migración de datos (script `migrar_sqlite_a_dynamodb.py`)

Cubre: escribir datos en las tablas DynamoDB ya creadas.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBDataWrite",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:GetItem",
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/ftgo-*",
        "arn:aws:dynamodb:*:*:table/ftgo-*/index/*"
      ]
    }
  ]
}
```

---

### 4. Permisos para crear y gestionar la instancia EC2

Cubre: lanzar la instancia EC2 del monolito, gestionar security groups,
key pairs y el Network Load Balancer.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2DescribeResources",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeImages",
        "ec2:DescribeKeyPairs",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeTags",
        "ec2:DescribeNetworkInterfaces"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2InstanceManagement",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:RebootInstances",
        "ec2:CreateTags",
        "ec2:CreateKeyPair",
        "ec2:DeleteKeyPair",
        "ec2:ImportKeyPair",
        "ec2:AllocateAddress",
        "ec2:AssociateAddress",
        "ec2:DisassociateAddress",
        "ec2:ReleaseAddress"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "EC2SecurityGroups",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "EC2NetworkLoadBalancer",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:CreateLoadBalancer",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:RegisterTargets",
        "elasticloadbalancing:DeregisterTargets",
        "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:AddTags",
        "elasticloadbalancing:DescribeTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
```

---

### 5. Permisos auxiliares (verificación y limpieza)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "STSIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    },
    {
      "Sid": "S3ListBuckets",
      "Effect": "Allow",
      "Action": "s3:ListAllMyBuckets",
      "Resource": "*"
    }
  ]
}
```

---

## Opción B: Política Simplificada (para ejercicio de clase)

Si no se requiere mínimo privilegio y se prioriza la simplicidad,
usar estas dos AWS Managed Policies en el Permission Set:

| Managed Policy | ARN |
|----------------|-----|
| PowerUserAccess | `arn:aws:iam::aws:policy/PowerUserAccess` |
| IAMFullAccess | `arn:aws:iam::aws:policy/IAMFullAccess` |

`PowerUserAccess` da acceso completo a todos los servicios excepto IAM y Organizations.
`IAMFullAccess` complementa con los permisos de IAM que SAM necesita para crear roles.

> ⚠️ **Nota:** Esta opción da más permisos de los necesarios. Úsala solo
> en cuentas de sandbox/laboratorio donde no hay recursos de producción.

---

## Cómo Crear el Permission Set en IAM Identity Center

### Paso 1: Acceder a IAM Identity Center

1. Ir a la consola de AWS → buscar **IAM Identity Center**
2. En el menú lateral: **Permission sets**
3. Clic en **Create permission set**

### Paso 2: Configurar el Permission Set

| Campo | Valor |
|-------|-------|
| Tipo | Custom permission set |
| Nombre | `FTGO-Microservicios-Deploy` |
| Descripción | Permisos para desplegar el proyecto FTGO Microservicios |
| Duración de sesión | 4 horas (recomendado para ejercicios largos) |

### Paso 3: Agregar la política

- Seleccionar **Inline policy**
- Pegar la política consolidada (combinar los 4 bloques de la Opción A)
- O seleccionar **AWS managed policies** y agregar `PowerUserAccess` + `IAMFullAccess` (Opción B)

### Paso 4: Asignar a usuarios/grupos

1. Ir a **AWS accounts** en IAM Identity Center
2. Seleccionar la cuenta del ejercicio
3. Clic en **Assign users or groups**
4. Seleccionar el grupo de alumnos
5. Seleccionar el Permission Set `FTGO-Microservicios-Deploy`
6. Confirmar

---

## Política Consolidada (Opción A — Un Solo JSON)

Para copiar y pegar directamente como inline policy del Permission Set:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationDeploy",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:ListStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:GetTemplateSummary",
        "cloudformation:ValidateTemplate",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListChangeSets"
      ],
      "Resource": [
        "arn:aws:cloudformation:*:*:stack/ftgo-*/*",
        "arn:aws:cloudformation:*:*:stack/aws-sam-cli-managed-default/*"
      ]
    },
    {
      "Sid": "CloudFormationTransform",
      "Effect": "Allow",
      "Action": "cloudformation:CreateChangeSet",
      "Resource": "arn:aws:cloudformation:*:aws:transform/Serverless-2016-10-31"
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
        "lambda:ListVersionsByFunction",
        "lambda:PublishVersion",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:TagResource",
        "lambda:UntagResource"
      ],
      "Resource": "arn:aws:lambda:*:*:function:ftgo-*"
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
      "Resource": [
        "arn:aws:apigateway:*::/restapis",
        "arn:aws:apigateway:*::/restapis/*"
      ]
    },
    {
      "Sid": "DynamoDBManagement",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:ListTagsOfResource",
        "dynamodb:PutItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:GetItem",
        "dynamodb:Scan",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/ftgo-*",
        "arn:aws:dynamodb:*:*:table/ftgo-*/index/*"
      ]
    },
    {
      "Sid": "IAMRolesForLambda",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": "arn:aws:iam::*:role/ftgo-*"
    },
    {
      "Sid": "IAMPassRoleToLambda",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/ftgo-*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "lambda.amazonaws.com"
        }
      }
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
        "logs:TagResource",
        "logs:TagLogGroup"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/ftgo-*"
    },
    {
      "Sid": "S3ArtifactsAndFrontend",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:PutBucketPolicy",
        "s3:GetBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning",
        "s3:PutLifecycleConfiguration",
        "s3:PutBucketTagging",
        "s3:GetBucketTagging",
        "s3:PutEncryptionConfiguration",
        "s3:GetEncryptionConfiguration",
        "s3:ListAllMyBuckets"
      ],
      "Resource": [
        "arn:aws:s3:::ftgo-frontend-*",
        "arn:aws:s3:::ftgo-frontend-*/*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    },
    {
      "Sid": "S3ListAll",
      "Effect": "Allow",
      "Action": "s3:ListAllMyBuckets",
      "Resource": "*"
    },
    {
      "Sid": "CloudFrontManagement",
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateDistribution",
        "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution",
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig",
        "cloudfront:ListDistributions",
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation",
        "cloudfront:TagResource",
        "cloudfront:UntagResource",
        "cloudfront:CreateOriginAccessControl",
        "cloudfront:GetOriginAccessControl",
        "cloudfront:UpdateOriginAccessControl",
        "cloudfront:DeleteOriginAccessControl",
        "cloudfront:ListOriginAccessControls"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2DescribeResources",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeImages",
        "ec2:DescribeKeyPairs",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeTags",
        "ec2:DescribeNetworkInterfaces"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2InstanceManagement",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:RebootInstances",
        "ec2:CreateTags",
        "ec2:CreateKeyPair",
        "ec2:DeleteKeyPair",
        "ec2:ImportKeyPair",
        "ec2:AllocateAddress",
        "ec2:AssociateAddress",
        "ec2:DisassociateAddress",
        "ec2:ReleaseAddress"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "EC2SecurityGroups",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "EC2NetworkLoadBalancer",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:CreateLoadBalancer",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:RegisterTargets",
        "elasticloadbalancing:DeregisterTargets",
        "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:AddTags",
        "elasticloadbalancing:DescribeTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "STSIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
```

> **Multi-cuenta:** Los ARNs usan `*` en el campo de Account ID. Esto permite
> que el mismo Permission Set funcione en todas las cuentas AWS donde se asigne,
> sin necesidad de modificar la política por cada cuenta de alumno.

---

## Notas Importantes

1. **Multi-cuenta con wildcard `*`**: Los ARNs usan `*` en el campo de Account ID
   (ej: `arn:aws:lambda:*:*:function:ftgo-*`). Esto es válido en IAM y permite
   que un solo Permission Set funcione en todas las cuentas donde se asigne.
   Como cada cuenta es independiente, los permisos solo aplican a los recursos
   de la cuenta donde el alumno tiene sesión activa — no hay acceso cross-account.

2. **Prefijo `ftgo-`**: Todos los recursos del proyecto usan el prefijo `ftgo-`.
   La política restringe permisos solo a recursos con ese prefijo, evitando que
   los alumnos afecten otros recursos de la cuenta.

3. **CloudFront y API Gateway**: Estos servicios no soportan restricción por ARN
   en todas sus acciones, por eso usan `Resource: "*"`. El prefijo `ftgo-` en los
   nombres de los recursos proporciona aislamiento lógico.

4. **Duración de sesión**: Se recomienda configurar 4 horas en el Permission Set
   para que los alumnos no tengan que renovar credenciales durante una clase.

5. **SAM Managed Bucket**: La primera vez que se ejecuta `sam deploy` en una región,
   SAM crea un bucket con prefijo `aws-sam-cli-managed-default-` para almacenar
   artefactos. La política incluye permisos para crearlo.

6. **Migración de datos**: Los permisos de DynamoDB incluyen `PutItem`, `Scan` y
   `Query` para que el script de migración pueda escribir y verificar datos.
