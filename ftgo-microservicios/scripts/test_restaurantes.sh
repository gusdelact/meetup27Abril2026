#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script de Pruebas — Microservicio de Restaurantes (Célula 3)
# ═══════════════════════════════════════════════════════════════
#
# Uso:
#   chmod +x test_restaurantes.sh
#   ./test_restaurantes.sh https://<tu-api-id>.execute-api.us-east-1.amazonaws.com/Prod
#
# Valida el CRUD de restaurantes Y el CRUD del menú (platillos).
# Este microservicio usa single-table design en DynamoDB.
# ═══════════════════════════════════════════════════════════════

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Debes proporcionar la URL del API Gateway"
    echo "Uso: ./test_restaurantes.sh <URL_API_GATEWAY>"
    exit 1
fi

BASE_URL="$1"
PASS=0
FAIL=0

echo "═══════════════════════════════════════════════════════════"
echo "🧪 Pruebas del Microservicio: RESTAURANTES + MENÚ"
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

# ═══════════════════════════════════════════════════════════════
# PARTE 1: CRUD de Restaurantes
# ═══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PARTE 1: Restaurantes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# TEST 1: Listar restaurantes
echo "── Test 1: GET /api/restaurantes/ ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/restaurantes/")
check "Listar restaurantes" 200 "$HTTP_CODE"

# TEST 2: Crear restaurante
echo "── Test 2: POST /api/restaurantes/ ──"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/restaurantes/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Tacos Test '$RANDOM'",
        "direccion": "Av. Prueba 100, CDMX",
        "telefono": "555-TEST",
        "tipo_cocina": "Mexicana",
        "horario_apertura": "10:00",
        "horario_cierre": "23:00"
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
check "Crear restaurante" 201 "$HTTP_CODE"

RESTAURANTE_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$RESTAURANTE_ID" ]; then
    echo "   ⚠️  No se pudo extraer el ID. Saltando tests dependientes."
    FAIL=$((FAIL + 10))
else
    echo "   📝 ID restaurante: $RESTAURANTE_ID"

    # TEST 3: Obtener restaurante por ID
    echo "── Test 3: GET /api/restaurantes/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/restaurantes/$RESTAURANTE_ID")
    check "Obtener restaurante por ID" 200 "$HTTP_CODE"

    # TEST 4: Actualizar restaurante
    echo "── Test 4: PUT /api/restaurantes/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$BASE_URL/api/restaurantes/$RESTAURANTE_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "nombre": "Tacos Test Actualizado",
            "direccion": "Av. Prueba 200, CDMX",
            "telefono": "555-UPDT",
            "tipo_cocina": "Mexicana Fusión",
            "horario_apertura": "09:00",
            "horario_cierre": "22:00"
        }')
    check "Actualizar restaurante" 200 "$HTTP_CODE"

    # ═══════════════════════════════════════════════════════════════
    # PARTE 2: CRUD del Menú
    # ═══════════════════════════════════════════════════════════════
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  PARTE 2: Menú del Restaurante"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # TEST 5: Agregar platillo al menú
    echo "── Test 5: POST /api/restaurantes/{id}/menu/ ──"
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/restaurantes/$RESTAURANTE_ID/menu/" \
        -H "Content-Type: application/json" \
        -d '{
            "nombre": "Tacos al Pastor",
            "descripcion": "3 tacos con piña y cilantro",
            "precio": 85.50,
            "disponible": 1
        }')
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    check "Agregar platillo al menú" 201 "$HTTP_CODE"

    PLATILLO_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
    echo "   📝 ID platillo: $PLATILLO_ID"

    # TEST 6: Agregar segundo platillo
    echo "── Test 6: POST /api/restaurantes/{id}/menu/ (segundo platillo) ──"
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/restaurantes/$RESTAURANTE_ID/menu/" \
        -H "Content-Type: application/json" \
        -d '{
            "nombre": "Quesadillas de Huitlacoche",
            "descripcion": "2 quesadillas con queso Oaxaca",
            "precio": 95.00,
            "disponible": 1
        }')
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    check "Agregar segundo platillo" 201 "$HTTP_CODE"

    # TEST 7: Obtener menú completo
    echo "── Test 7: GET /api/restaurantes/{id}/menu/ ──"
    RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/restaurantes/$RESTAURANTE_ID/menu/")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    check "Obtener menú completo" 200 "$HTTP_CODE"

    # Verificar que hay 2 platillos
    NUM_PLATILLOS=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    if [ "$NUM_PLATILLOS" -eq 2 ]; then
        echo "   ✅ PASS: Menú tiene 2 platillos"
        PASS=$((PASS + 1))
    else
        echo "   ❌ FAIL: Menú debería tener 2 platillos, tiene $NUM_PLATILLOS"
        FAIL=$((FAIL + 1))
    fi

    # TEST 8: Actualizar platillo del menú
    if [ -n "$PLATILLO_ID" ]; then
        echo "── Test 8: PUT /api/restaurantes/menu/{elemento_id} ──"
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$BASE_URL/api/restaurantes/menu/$PLATILLO_ID" \
            -H "Content-Type: application/json" \
            -d '{
                "nombre": "Tacos al Pastor (Orden Grande)",
                "descripcion": "5 tacos con piña y cilantro",
                "precio": 120.00,
                "disponible": 1
            }')
        check "Actualizar platillo" 200 "$HTTP_CODE"

        # TEST 9: Eliminar platillo del menú
        echo "── Test 9: DELETE /api/restaurantes/menu/{elemento_id} ──"
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/restaurantes/menu/$PLATILLO_ID")
        check "Eliminar platillo" 204 "$HTTP_CODE"
    fi

    # TEST 10: Eliminar restaurante (y su menú restante)
    echo "── Test 10: DELETE /api/restaurantes/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/restaurantes/$RESTAURANTE_ID")
    check "Eliminar restaurante" 204 "$HTTP_CODE"

    # TEST 11: Verificar que el restaurante fue eliminado
    echo "── Test 11: GET /api/restaurantes/{id} (eliminado) ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/restaurantes/$RESTAURANTE_ID")
    check "Restaurante eliminado devuelve 404" 404 "$HTTP_CODE"
fi

# TEST 12: Crear restaurante sin campos requeridos
echo "── Test 12: POST /api/restaurantes/ (datos incompletos) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/restaurantes/" \
    -H "Content-Type: application/json" \
    -d '{"nombre": "Solo Nombre"}')
check "Rechazar datos incompletos" 400 "$HTTP_CODE"

# TEST 13: CORS preflight
echo "── Test 13: OPTIONS /api/restaurantes/ (CORS) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE_URL/api/restaurantes/")
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
