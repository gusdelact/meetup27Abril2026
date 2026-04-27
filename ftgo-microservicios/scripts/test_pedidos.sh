#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script de Pruebas — Microservicio de Pedidos (Célula 5)
# ═══════════════════════════════════════════════════════════════
#
# Uso:
#   chmod +x test_pedidos.sh
#   ./test_pedidos.sh <URL_PEDIDOS> <URL_CONSUMIDORES> <URL_RESTAURANTES> <URL_ENTREGAS>
#
# Este es el microservicio más complejo. Requiere que los servicios
# de Consumidores, Restaurantes y Entregas estén desplegados porque
# Pedidos los llama para validar datos al crear un pedido.
#
# El script primero crea datos de prueba en los otros servicios,
# luego prueba el flujo completo del pedido.
# ═══════════════════════════════════════════════════════════════

set -e

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
    echo "❌ Error: Se necesitan las URLs de 4 microservicios"
    echo ""
    echo "Uso: ./test_pedidos.sh <URL_PEDIDOS> <URL_CONSUMIDORES> <URL_RESTAURANTES> <URL_ENTREGAS>"
    echo ""
    echo "Ejemplo:"
    echo "  ./test_pedidos.sh \\"
    echo "    https://pedidos.execute-api.us-east-1.amazonaws.com/Prod \\"
    echo "    https://consumidores.execute-api.us-east-1.amazonaws.com/Prod \\"
    echo "    https://restaurantes.execute-api.us-east-1.amazonaws.com/Prod \\"
    echo "    https://entregas.execute-api.us-east-1.amazonaws.com/Prod"
    exit 1
fi

URL_PEDIDOS="$1"
URL_CONSUMIDORES="$2"
URL_RESTAURANTES="$3"
URL_ENTREGAS="$4"
PASS=0
FAIL=0

echo "═══════════════════════════════════════════════════════════"
echo "🧪 Pruebas del Microservicio: PEDIDOS"
echo "═══════════════════════════════════════════════════════════"
echo "   URL Pedidos:       $URL_PEDIDOS"
echo "   URL Consumidores:  $URL_CONSUMIDORES"
echo "   URL Restaurantes:  $URL_RESTAURANTES"
echo "   URL Entregas:      $URL_ENTREGAS"
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
# PREPARACIÓN: Crear datos de prueba en otros servicios
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PREPARACIÓN: Creando datos de prueba"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Crear consumidor de prueba
echo "   → Creando consumidor de prueba..."
RESPONSE=$(curl -s -X POST "$URL_CONSUMIDORES/api/consumidores/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Consumidor Pedidos Test",
        "email": "pedidos_test_'$RANDOM'@prueba.com",
        "telefono": "555-PED1",
        "direccion": "Av. Test Pedidos 100"
    }')
CONSUMIDOR_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Consumidor ID: $CONSUMIDOR_ID"

# Crear restaurante de prueba
echo "   → Creando restaurante de prueba..."
RESPONSE=$(curl -s -X POST "$URL_RESTAURANTES/api/restaurantes/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Restaurante Pedidos Test",
        "direccion": "Calle Test 200",
        "telefono": "555-REST",
        "tipo_cocina": "Test"
    }')
RESTAURANTE_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Restaurante ID: $RESTAURANTE_ID"

# Agregar platillo al menú
echo "   → Agregando platillo al menú..."
RESPONSE=$(curl -s -X POST "$URL_RESTAURANTES/api/restaurantes/$RESTAURANTE_ID/menu/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Platillo Test",
        "descripcion": "Para pruebas",
        "precio": 100.00,
        "disponible": 1
    }')
PLATILLO_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Platillo ID: $PLATILLO_ID"

# Crear repartidor de prueba
echo "   → Creando repartidor de prueba..."
RESPONSE=$(curl -s -X POST "$URL_ENTREGAS/api/repartidores/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Repartidor Pedidos Test",
        "telefono": "555-REPA",
        "vehiculo": "Moto"
    }')
REPARTIDOR_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
echo "   📝 Repartidor ID: $REPARTIDOR_ID"

if [ -z "$CONSUMIDOR_ID" ] || [ -z "$RESTAURANTE_ID" ] || [ -z "$PLATILLO_ID" ] || [ -z "$REPARTIDOR_ID" ]; then
    echo ""
    echo "   ❌ Error: No se pudieron crear los datos de prueba en los otros servicios."
    echo "   Verifica que Consumidores, Restaurantes y Entregas estén desplegados correctamente."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PRUEBAS: Microservicio de Pedidos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# TEST 1: Listar pedidos
echo "── Test 1: GET /api/pedidos/ ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL_PEDIDOS/api/pedidos/")
check "Listar pedidos" 200 "$HTTP_CODE"

# TEST 2: Crear pedido
echo "── Test 2: POST /api/pedidos/ ──"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$URL_PEDIDOS/api/pedidos/" \
    -H "Content-Type: application/json" \
    -d '{
        "consumidor_id": "'$CONSUMIDOR_ID'",
        "restaurante_id": "'$RESTAURANTE_ID'",
        "direccion_entrega": "Av. Entrega Test 300, CDMX",
        "elementos": [
            {"elemento_menu_id": "'$PLATILLO_ID'", "cantidad": 2}
        ]
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
check "Crear pedido" 201 "$HTTP_CODE"

PEDIDO_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$PEDIDO_ID" ]; then
    echo "   ⚠️  No se pudo extraer el ID del pedido. Saltando tests de estado."
    FAIL=$((FAIL + 8))
else
    echo "   📝 Pedido ID: $PEDIDO_ID"

    # Verificar estado inicial = CREADO
    ESTADO=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['estado'])" 2>/dev/null || echo "")
    if [ "$ESTADO" = "CREADO" ]; then
        echo "   ✅ PASS: Estado inicial es CREADO"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Estado inicial debería ser CREADO, es $ESTADO"
        FAIL=$((FAIL + 1))
    fi

    # Verificar total calculado (2 × $100 = $200)
    TOTAL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
    if [ "$(echo "$TOTAL == 200.0" | python3 -c "import sys; print(eval(sys.stdin.read()))")" = "True" ]; then
        echo "   ✅ PASS: Total calculado correctamente ($TOTAL)"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Total debería ser 200.0, es $TOTAL"
        FAIL=$((FAIL + 1))
    fi

    # TEST 3: Obtener pedido por ID
    echo "── Test 3: GET /api/pedidos/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID")
    check "Obtener pedido por ID" 200 "$HTTP_CODE"

    # ═══════════════════════════════════════════════════════════════
    # PRUEBAS DE MÁQUINA DE ESTADOS
    # ═══════════════════════════════════════════════════════════════
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  MÁQUINA DE ESTADOS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # TEST 4: Transición inválida (CREADO → ENTREGADO)
    echo "── Test 4: PUT /estado (transición inválida CREADO→ENTREGADO) ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/estado" \
        -H "Content-Type: application/json" \
        -d '{"estado": "ENTREGADO"}')
    check "Rechazar transición inválida" 400 "$HTTP_CODE"

    # TEST 5: CREADO → ACEPTADO
    echo "── Test 5: PUT /estado {ACEPTADO} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/estado" \
        -H "Content-Type: application/json" \
        -d '{"estado": "ACEPTADO"}')
    check "Transición CREADO → ACEPTADO" 200 "$HTTP_CODE"

    # TEST 6: ACEPTADO → PREPARANDO
    echo "── Test 6: PUT /estado {PREPARANDO} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/estado" \
        -H "Content-Type: application/json" \
        -d '{"estado": "PREPARANDO"}')
    check "Transición ACEPTADO → PREPARANDO" 200 "$HTTP_CODE"

    # TEST 7: PREPARANDO → LISTO
    echo "── Test 7: PUT /estado {LISTO} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/estado" \
        -H "Content-Type: application/json" \
        -d '{"estado": "LISTO"}')
    check "Transición PREPARANDO → LISTO" 200 "$HTTP_CODE"

    # TEST 8: Asignar repartidor (solo funciona en estado LISTO)
    echo "── Test 8: PUT /repartidor ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/repartidor" \
        -H "Content-Type: application/json" \
        -d '{"repartidor_id": "'$REPARTIDOR_ID'"}')
    check "Asignar repartidor" 200 "$HTTP_CODE"

    # TEST 9: LISTO → EN_CAMINO
    echo "── Test 9: PUT /estado {EN_CAMINO} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/estado" \
        -H "Content-Type: application/json" \
        -d '{"estado": "EN_CAMINO"}')
    check "Transición LISTO → EN_CAMINO" 200 "$HTTP_CODE"

    # TEST 10: EN_CAMINO → ENTREGADO
    echo "── Test 10: PUT /estado {ENTREGADO} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID/estado" \
        -H "Content-Type: application/json" \
        -d '{"estado": "ENTREGADO"}')
    check "Transición EN_CAMINO → ENTREGADO" 200 "$HTTP_CODE"

    # TEST 11: No se puede cancelar un pedido ENTREGADO
    echo "── Test 11: DELETE /api/pedidos/{id} (ya entregado) ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$URL_PEDIDOS/api/pedidos/$PEDIDO_ID")
    check "No se puede cancelar pedido entregado" 400 "$HTTP_CODE"
fi

# TEST 12: Crear pedido sin campos requeridos
echo "── Test 12: POST /api/pedidos/ (datos incompletos) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL_PEDIDOS/api/pedidos/" \
    -H "Content-Type: application/json" \
    -d '{"consumidor_id": "abc"}')
check "Rechazar datos incompletos" 400 "$HTTP_CODE"

# TEST 13: CORS preflight
echo "── Test 13: OPTIONS /api/pedidos/ (CORS) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$URL_PEDIDOS/api/pedidos/")
check "CORS preflight" 200 "$HTTP_CODE"

# ═══════════════════════════════════════════════════════════════
# LIMPIEZA: Eliminar datos de prueba de otros servicios
# ═══════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  LIMPIEZA: Eliminando datos de prueba"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -o /dev/null -X DELETE "$URL_CONSUMIDORES/api/consumidores/$CONSUMIDOR_ID"
echo "   🗑️  Consumidor eliminado"
curl -s -o /dev/null -X DELETE "$URL_RESTAURANTES/api/restaurantes/$RESTAURANTE_ID"
echo "   🗑️  Restaurante eliminado"
curl -s -o /dev/null -X DELETE "$URL_ENTREGAS/api/repartidores/$REPARTIDOR_ID"
echo "   🗑️  Repartidor eliminado"

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
