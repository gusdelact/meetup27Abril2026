/**
 * Configuración del Frontend — URLs de los API Gateway.
 *
 * Este archivo contiene las URLs de cada microservicio.
 * Después de desplegar los microservicios, reemplaza las URLs
 * con las que te da cada stack de CloudFormation.
 *
 * Para obtener las URLs, ejecuta desde tu EC2:
 *   aws cloudformation describe-stacks --stack-name ftgo-consumidores \
 *     --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text
 *
 * IMPORTANTE: No incluir "/" al final de las URLs.
 */
const CONFIG = {
    // URL del API Gateway del microservicio de Consumidores
    API_CONSUMIDORES: "https://REEMPLAZAR.execute-api.us-east-1.amazonaws.com/Prod",

    // URL del API Gateway del microservicio de Restaurantes
    API_RESTAURANTES: "https://REEMPLAZAR.execute-api.us-east-1.amazonaws.com/Prod",

    // URL del API Gateway del microservicio de Pedidos
    API_PEDIDOS: "https://REEMPLAZAR.execute-api.us-east-1.amazonaws.com/Prod",

    // URL del API Gateway del microservicio de Entregas (Repartidores)
    API_ENTREGAS: "https://REEMPLAZAR.execute-api.us-east-1.amazonaws.com/Prod",

    // URL del API Gateway del microservicio de Pagos
    API_PAGOS: "https://REEMPLAZAR.execute-api.us-east-1.amazonaws.com/Prod",
};
