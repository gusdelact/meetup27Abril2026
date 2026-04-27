#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script de Pruebas — Microservicio de Pagos (Célula 6)
# ═══════════════════════════════════════════════════════════════
#
# Uso:
#   chmod +x test_pagos.sh
#   ./test_pagos.sh <URL_PAGOS> <URL_PEDIDOS> <URL_CONSUMIDORES> <URL_RESTAURANTES>
#
# Este microservicio consulta a Pedidos para obtener el total.
# El script crea un pedido de prueba y luego procesa su pago.
# ═══════════════════════════════════════════════════════════════

set -e

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
    echo "❌ Error: Se necesitan las URLs de 4 microservicios"
    echo ""
    echo "Uso: ./test_pagos.sh <URL_PAGOS> <URL_PEDIDOS> <URL_CONSUMIDORES> <URL_RESTAURANTES>"
    echo ""
    echo "Ejemplo:"
    echo "  ./test_pagos.sh \\"
    echo "    https://pagos.execute-api.us-east-1.amazonaws.com/Prod \\"
    echo "    https://pedidos.execute-api.us-east-1.amazonaws.com/Prod \\"
    echo "    https://consumidores.execute-api.us-east-1.amazonaws.com/Prod \\"
    echo "    https://restaurantes.execute-api.us-east-1.amazonaws.com/Prod"
    exit 1
fi

URL_PAGOS="$1"
URL_PEDIDOS="$2"
URL_CONSUMIDORES="$3"
URL_RESTAURANTES="$4"
PASS=0
FAIL=0

echo "═══════════════════════════════════════════════════════════"
echo "🧪 Pruebas del Microservicio: PAGOS"
echo "═══════════════════════════════════════════════════════════"
echo "   URL Pagos:         $URL_PAGOS"
echo "   URL Pedidos:       $URL_PEDIDOS"
echo "   URL Consumidores:  $URL_CONSUMIDORES"
echo "   URL Restaurantes:  $URL_RESTAURANTES"
echo "   Fecha: $(date)"
echo ""

check() {
    local test_name="$1"
    local expected_code="$2"
    local actual_code="$3"
    if [ "$actual_code" -eq "$expected_code" ]; then
        echo "   ✅ PASS: $test_name (HTTP $actual_code)"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: $test_name (esperado HTTP $expected_code, recibido HTTP $actual_code)"
        FAIL=$((FAIL + 1))
    fi
}

# ═══════════════════════════════════════════════════════════════
# PREPARACIÓN: Crear un pedido para poder pagarlo
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PREPARACIÓN: Creando pedido de prueba"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Crear consumidor
echo "   → Creando consumidor..."
RESPONSE=$(curl -s -X POST "$URL_CONSUMIDORES/api/consumidores/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Consumidor Pagos Test",
        "email": "pagos_test_'$RANDOM'@prueba.com",
        "telefono": "555-PAG1",
        "direccion": "Av. Pagos 100"
    }')
CONSUMIDOR_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Consumidor ID: $CONSUMIDOR_ID"

# Crear restaurante + platillo
echo "   → Creando restaurante..."
RESPONSE=$(curl -s -X POST "$URL_RESTAURANTES/api/restaurantes/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Restaurante Pagos Test",
        "direccion": "Calle Pagos 200",
        "telefono": "555-RPAG",
        "tipo_cocina": "Test"
    }')
RESTAURANTE_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Restaurante ID: $RESTAURANTE_ID"

echo "   → Agregando platillo..."
RESPONSE=$(curl -s -X POST "$URL_RESTAURANTES/api/restaurantes/$RESTAURANTE_ID/menu/" \
    -H "Content-Type: application/json" \
    -d '{"nombre": "Platillo Pagos", "precio": 150.00, "disponible": 1}')
PLATILLO_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Platillo ID: $PLATILLO_ID"

# Crear pedido
echo "   → Creando pedido..."
RESPONSE=$(curl -s -X POST "$URL_PEDIDOS/api/pedidos/" \
    -H "Content-Type: application/json" \
    -d '{
        "consumidor_id": "'$CONSUMIDOR_ID'",
        "restaurante_id": "'$RESTAURANTE_ID'",
        "direccion_entrega": "Av. Pago Test 300",
        "elementos": [{"elemento_menu_id": "'$PLATILLO_ID'", "cantidad": 2}]
    }')
PEDIDO_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Pedido ID: $PEDIDO_ID"

if [ -z "$PEDIDO_ID" ]; then
    echo ""
    echo "   ❌ Error: No se pudo crear el pedido de prueba."
    echo "   Verifica que Consumidores, Restaurantes y Pedidos estén desplegados."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PRUEBAS: Microservicio de Pagos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# TEST 1: Listar pagos
echo "── Test 1: GET /api/pagos/ ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL_PAGOS/api/pagos/")
check "Listar pagos" 200 "$HTTP_CODE"

# TEST 2: Procesar pago
echo "── Test 2: POST /api/pagos/ (procesar pago) ──"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$URL_PAGOS/api/pagos/" \
    -H "Content-Type: application/json" \
    -d '{
        "pedido_id": "'$PEDIDO_ID'",
        "metodo_pago": "tarjeta"
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
check "Procesar pago" 201 "$HTTP_CODE"

PAGO_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -n "$PAGO_ID" ]; then
    echo "   📝 Pago ID: $PAGO_ID"

    # Verificar que el estado es COMPLETADO
    ESTADO=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['estado'])" 2>/dev/null || echo "")
    if [ "$ESTADO" = "COMPLETADO" ]; then
        echo "   ✅ PASS: Estado del pago es COMPLETADO"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Estado debería ser COMPLETADO, es $ESTADO"
        FAIL=$((FAIL + 1))
    fi

    # Verificar que tiene referencia PAY-XXXX
    REFERENCIA=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['referencia'])" 2>/dev/null || echo "")
    if [[ "$REFERENCIA" == PAY-* ]]; then
        echo "   ✅ PASS: Referencia generada correctamente ($REFERENCIA)"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Referencia debería empezar con PAY-, es $REFERENCIA"
        FAIL=$((FAIL + 1))
    fi

    # Verificar monto (2 × $150 = $300)
    MONTO=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['monto'])" 2>/dev/null || echo "0")
    if [ "$(echo "$MONTO == 300.0" | python3 -c "import sys; print(eval(sys.stdin.read()))")" = "True" ]; then
        echo "   ✅ PASS: Monto correcto ($MONTO)"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Monto debería ser 300.0, es $MONTO"
        FAIL=$((FAIL + 1))
    fi

    # TEST 3: Obtener pago por ID
    echo "── Test 3: GET /api/pagos/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL_PAGOS/api/pagos/$PAGO_ID")
    check "Obtener pago por ID" 200 "$HTTP_CODE"
fi

# TEST 4: Intentar pagar el mismo pedido otra vez (idempotencia)
echo "── Test 4: POST /api/pagos/ (pago duplicado) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL_PAGOS/api/pagos/" \
    -H "Content-Type: application/json" \
    -d '{
        "pedido_id": "'$PEDIDO_ID'",
        "metodo_pago": "efectivo"
    }')
check "Rechazar pago duplicado" 400 "$HTTP_CODE"

# TEST 5: Pagar sin campos requeridos
echo "── Test 5: POST /api/pagos/ (datos incompletos) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL_PAGOS/api/pagos/" \
    -H "Content-Type: application/json" \
    -d '{"pedido_id": "abc"}')
check "Rechazar datos incompletos" 400 "$HTTP_CODE"

# TEST 6: CORS preflight
echo "── Test 6: OPTIONS /api/pagos/ (CORS) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$URL_PAGOS/api/pagos/")
check "CORS preflight" 200 "$HTTP_CODE"

# ═══════════════════════════════════════════════════════════════
# LIMPIEZA
# ═══════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  LIMPIEZA: Eliminando datos de prueba"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -o /dev/null -X DELETE "$URL_CONSUMIDORES/api/consumidores/$CONSUMIDOR_ID"
echo "   🗑️  Consumidor eliminado"
curl -s -o /dev/null -X DELETE "$URL_RESTAURANTES/api/restaurantes/$RESTAURANTE_ID"
echo "   🗑️  Restaurante eliminado"

# ═══════════════════════════════════════════════════════════════
# Resumen
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "📊 Resumen: $PASS passed, $FAIL failed (total: $((PASS + FAIL)))"
echo "═══════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    echo "⚠️  Hay pruebas fallidas. Revisa los errores antes de integrar."
    exit 1
else
    echo "🎉 ¡Todos los tests pasaron! El microservicio está listo para integrar."
    exit 0
fi
