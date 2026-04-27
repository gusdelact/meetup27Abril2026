#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script de Pruebas — Microservicio de Entregas/Repartidores (Célula 4)
# ═══════════════════════════════════════════════════════════════
#
# Uso:
#   chmod +x test_entregas.sh
#   ./test_entregas.sh https://<tu-api-id>.execute-api.us-east-1.amazonaws.com/Prod
#
# Valida el CRUD de repartidores y el manejo del campo 'disponible'.
# ═══════════════════════════════════════════════════════════════

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Debes proporcionar la URL del API Gateway"
    echo "Uso: ./test_entregas.sh <URL_API_GATEWAY>"
    exit 1
fi

BASE_URL="$1"
PASS=0
FAIL=0

echo "═══════════════════════════════════════════════════════════"
echo "🧪 Pruebas del Microservicio: ENTREGAS (Repartidores)"
echo "═══════════════════════════════════════════════════════════"
echo "   URL: $BASE_URL"
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

# TEST 1: Listar repartidores
echo "── Test 1: GET /api/repartidores/ ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/repartidores/")
check "Listar repartidores" 200 "$HTTP_CODE"

# TEST 2: Crear repartidor
echo "── Test 2: POST /api/repartidores/ ──"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/repartidores/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Repartidor Test '$RANDOM'",
        "telefono": "555-MOTO",
        "vehiculo": "Motocicleta"
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
check "Crear repartidor" 201 "$HTTP_CODE"

REPARTIDOR_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$REPARTIDOR_ID" ]; then
    echo "   ⚠️  No se pudo extraer el ID. Saltando tests dependientes."
    FAIL=$((FAIL + 6))
else
    echo "   📝 ID repartidor: $REPARTIDOR_ID"

    # TEST 3: Obtener repartidor por ID
    echo "── Test 3: GET /api/repartidores/{id} ──"
    RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/repartidores/$REPARTIDOR_ID")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    check "Obtener repartidor por ID" 200 "$HTTP_CODE"

    # Verificar que el repartidor se creó como disponible (1)
    DISPONIBLE=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['disponible'])" 2>/dev/null || echo "-1")
    if [ "$DISPONIBLE" -eq 1 ]; then
        echo "   ✅ PASS: Repartidor creado como disponible (disponible=1)"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Repartidor debería ser disponible=1, tiene disponible=$DISPONIBLE"
        FAIL=$((FAIL + 1))
    fi

    # TEST 4: Actualizar repartidor (cambiar disponibilidad a 0 = ocupado)
    echo "── Test 4: PUT /api/repartidores/{id} (marcar como ocupado) ──"
    RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT "$BASE_URL/api/repartidores/$REPARTIDOR_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "nombre": "Repartidor Test Actualizado",
            "telefono": "555-MOTO",
            "vehiculo": "Motocicleta",
            "disponible": 0
        }')
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    check "Marcar repartidor como ocupado" 200 "$HTTP_CODE"

    # Verificar que disponible cambió a 0
    DISPONIBLE=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['disponible'])" 2>/dev/null || echo "-1")
    if [ "$DISPONIBLE" -eq 0 ]; then
        echo "   ✅ PASS: Repartidor marcado como ocupado (disponible=0)"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Repartidor debería ser disponible=0, tiene disponible=$DISPONIBLE"
        FAIL=$((FAIL + 1))
    fi

    # TEST 5: Volver a marcar como disponible
    echo "── Test 5: PUT /api/repartidores/{id} (marcar como disponible) ──"
    RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT "$BASE_URL/api/repartidores/$REPARTIDOR_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "nombre": "Repartidor Test Actualizado",
            "telefono": "555-MOTO",
            "vehiculo": "Bicicleta",
            "disponible": 1
        }')
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    check "Marcar repartidor como disponible" 200 "$HTTP_CODE"

    # TEST 6: Eliminar repartidor
    echo "── Test 6: DELETE /api/repartidores/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/repartidores/$REPARTIDOR_ID")
    check "Eliminar repartidor" 204 "$HTTP_CODE"

    # TEST 7: Verificar que fue eliminado
    echo "── Test 7: GET /api/repartidores/{id} (eliminado) ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/repartidores/$REPARTIDOR_ID")
    check "Repartidor eliminado devuelve 404" 404 "$HTTP_CODE"
fi

# TEST 8: Crear repartidor sin campos requeridos
echo "── Test 8: POST /api/repartidores/ (datos incompletos) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/repartidores/" \
    -H "Content-Type: application/json" \
    -d '{"nombre": "Solo Nombre"}')
check "Rechazar datos incompletos" 400 "$HTTP_CODE"

# TEST 9: CORS preflight
echo "── Test 9: OPTIONS /api/repartidores/ (CORS) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE_URL/api/repartidores/")
check "CORS preflight" 200 "$HTTP_CODE"

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
