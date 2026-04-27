#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script de Pruebas — Microservicio de Consumidores (Célula 2)
# ═══════════════════════════════════════════════════════════════
#
# Uso:
#   chmod +x test_consumidores.sh
#   ./test_consumidores.sh https://<tu-api-id>.execute-api.us-east-1.amazonaws.com/Prod
#
# Este script valida que el microservicio de Consumidores funciona
# correctamente antes de integrar con el resto del sistema.
# Ejecuta un flujo CRUD completo: Crear → Leer → Actualizar → Eliminar.
# ═══════════════════════════════════════════════════════════════

set -e

# ── Validar argumento ──
if [ -z "$1" ]; then
    echo "❌ Error: Debes proporcionar la URL del API Gateway"
    echo ""
    echo "Uso: ./test_consumidores.sh <URL_API_GATEWAY>"
    echo "Ejemplo: ./test_consumidores.sh https://abc123.execute-api.us-east-1.amazonaws.com/Prod"
    exit 1
fi

BASE_URL="$1"
PASS=0
FAIL=0

echo "═══════════════════════════════════════════════════════════"
echo "🧪 Pruebas del Microservicio: CONSUMIDORES"
echo "═══════════════════════════════════════════════════════════"
echo "   URL: $BASE_URL"
echo "   Fecha: $(date)"
echo ""

# ── Función auxiliar para verificar resultado ──
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
# TEST 1: Listar consumidores (GET) — debe devolver 200
# ═══════════════════════════════════════════════════════════════
echo "── Test 1: GET /api/consumidores/ ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/consumidores/")
check "Listar consumidores" 200 "$HTTP_CODE"

# ═══════════════════════════════════════════════════════════════
# TEST 2: Crear un consumidor (POST) — debe devolver 201
# ═══════════════════════════════════════════════════════════════
echo "── Test 2: POST /api/consumidores/ ──"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/consumidores/" \
    -H "Content-Type: application/json" \
    -d '{
        "nombre": "Test Usuario",
        "email": "test_celula2_'$RANDOM'@prueba.com",
        "telefono": "555-0001",
        "direccion": "Calle de Prueba 123, CDMX"
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')
check "Crear consumidor" 201 "$HTTP_CODE"

# Extraer el ID del consumidor creado
CONSUMIDOR_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -z "$CONSUMIDOR_ID" ]; then
    echo "   ⚠️  No se pudo extraer el ID del consumidor creado. Saltando tests dependientes."
    FAIL=$((FAIL + 4))
else
    echo "   📝 ID creado: $CONSUMIDOR_ID"

    # ═══════════════════════════════════════════════════════════════
    # TEST 3: Obtener consumidor por ID (GET) — debe devolver 200
    # ═══════════════════════════════════════════════════════════════
    echo "── Test 3: GET /api/consumidores/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/consumidores/$CONSUMIDOR_ID")
    check "Obtener consumidor por ID" 200 "$HTTP_CODE"

    # ═══════════════════════════════════════════════════════════════
    # TEST 4: Actualizar consumidor (PUT) — debe devolver 200
    # ═══════════════════════════════════════════════════════════════
    echo "── Test 4: PUT /api/consumidores/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$BASE_URL/api/consumidores/$CONSUMIDOR_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "nombre": "Test Usuario Actualizado",
            "email": "test_actualizado_'$RANDOM'@prueba.com",
            "telefono": "555-9999",
            "direccion": "Calle Actualizada 456, CDMX"
        }')
    check "Actualizar consumidor" 200 "$HTTP_CODE"

    # ═══════════════════════════════════════════════════════════════
    # TEST 5: Eliminar consumidor (DELETE) — debe devolver 204
    # ═══════════════════════════════════════════════════════════════
    echo "── Test 5: DELETE /api/consumidores/{id} ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/consumidores/$CONSUMIDOR_ID")
    check "Eliminar consumidor" 204 "$HTTP_CODE"

    # ═══════════════════════════════════════════════════════════════
    # TEST 6: Obtener consumidor eliminado (GET) — debe devolver 404
    # ═══════════════════════════════════════════════════════════════
    echo "── Test 6: GET /api/consumidores/{id} (eliminado) ──"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/consumidores/$CONSUMIDOR_ID")
    check "Consumidor eliminado devuelve 404" 404 "$HTTP_CODE"
fi

# ═══════════════════════════════════════════════════════════════
# TEST 7: Crear consumidor sin campos requeridos — debe devolver 400
# ═══════════════════════════════════════════════════════════════
echo "── Test 7: POST /api/consumidores/ (datos incompletos) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/consumidores/" \
    -H "Content-Type: application/json" \
    -d '{"nombre": "Solo Nombre"}')
check "Rechazar datos incompletos" 400 "$HTTP_CODE"

# ═══════════════════════════════════════════════════════════════
# TEST 8: OPTIONS (CORS preflight) — debe devolver 200
# ═══════════════════════════════════════════════════════════════
echo "── Test 8: OPTIONS /api/consumidores/ (CORS) ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE_URL/api/consumidores/")
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
