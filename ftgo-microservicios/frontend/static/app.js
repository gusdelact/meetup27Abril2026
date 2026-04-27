/**
 * Aplicación JavaScript — FTGO Microservicios.
 *
 * DIFERENCIA CLAVE vs. el monolito:
 * En el monolito, todas las llamadas iban a la misma URL (el mismo servidor).
 * Ahora, cada módulo llama a un API Gateway DIFERENTE (un microservicio distinto).
 *
 * Las URLs de cada microservicio se configuran en config.js
 *
 * MANEJO DE SERVICIOS NO DISPONIBLES:
 * Si un microservicio aún no está desplegado, se muestra un mensaje
 * amigable indicando que el API y microservicio aún no está implementado.
 */

// ============================================================
// Utilidades generales
// ============================================================

/**
 * Mensaje que se muestra cuando un microservicio no está desplegado.
 * Esto ocurre cuando la URL en config.js aún tiene "REEMPLAZAR"
 * o cuando el API Gateway no responde (el servicio no existe aún).
 */
const MSG_NO_IMPLEMENTADO = "⚠️ API y microservicio aún no implementado. " +
    "Despliega el servicio correspondiente y actualiza config.js con la URL del API Gateway.";

/**
 * Verifica si la URL de un microservicio está configurada.
 * Retorna false si la URL contiene "REEMPLAZAR" (valor por defecto en config.js).
 */
function apiDisponible(url) {
    return url && !url.includes("REEMPLAZAR");
}

/**
 * Wrapper para fetch que detecta si el microservicio no está disponible.
 * Si la URL no está configurada o el servicio no responde, muestra
 * un mensaje amigable en lugar de un error técnico críptico.
 *
 * @param {string} url - URL completa del endpoint
 * @param {string} nombreServicio - Nombre del microservicio (para el mensaje)
 * @param {object} opciones - Opciones de fetch (method, headers, body)
 * @returns {Response|null} - La respuesta HTTP o lanza error si no disponible
 */
async function fetchServicio(url, nombreServicio, opciones = {}) {
    if (url.includes("REEMPLAZAR")) {
        throw new Error(MSG_NO_IMPLEMENTADO + ` [Servicio: ${nombreServicio}]`);
    }
    try {
        const resp = await fetch(url, opciones);
        return resp;
    } catch (err) {
        throw new Error(
            `⚠️ API y microservicio "${nombreServicio}" aún no implementado o no disponible. ` +
            `Verifica que el servicio esté desplegado y la URL en config.js sea correcta.`
        );
    }
}

function mostrarMensaje(seccion, texto, tipo) {
    const contenedor = document.getElementById(`msg-${seccion}`);
    contenedor.innerHTML = `<div class="mensaje mensaje-${tipo}">${texto}</div>`;
    const duracion = texto.includes("no implementado") ? 8000 : 4000;
    setTimeout(() => { contenedor.innerHTML = ""; }, duracion);
}

function mostrarSeccion(nombre) {
    document.querySelectorAll(".seccion").forEach(s => s.classList.remove("visible"));
    document.getElementById(`sec-${nombre}`).classList.add("visible");
    document.querySelectorAll("nav button").forEach(b => b.classList.remove("activo"));
    event.target.classList.add("activo");
    cargarDatos(nombre);
}

function cargarDatos(seccion) {
    switch (seccion) {
        case "consumidores": cargarConsumidores(); break;
        case "restaurantes": cargarRestaurantes(); break;
        case "menu": cargarMenu(); break;
        case "repartidores": cargarRepartidores(); break;
        case "pedidos": cargarPedidos(); break;
        case "pagos": cargarPagos(); break;
    }
}

function idCorto(id) {
    if (!id) return "-";
    return id.substring(0, 8) + "...";
}

// ============================================================
// Módulo de Consumidores → API Gateway de CONSUMIDORES
// ============================================================

async function cargarConsumidores() {
    if (!apiDisponible(CONFIG.API_CONSUMIDORES)) {
        mostrarMensaje("consumidores", MSG_NO_IMPLEMENTADO, "error");
        return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_CONSUMIDORES}/api/consumidores/`, "Consumidores");
        const datos = await resp.json();
        const tbody = document.getElementById("tabla-consumidores");
        tbody.innerHTML = datos.map(c => `
            <tr>
                <td title="${c.id}">${idCorto(c.id)}</td>
                <td>${c.nombre}</td>
                <td>${c.email}</td>
                <td>${c.telefono}</td>
                <td><button class="btn btn-peligro" onclick="eliminarConsumidor('${c.id}')">Eliminar</button></td>
            </tr>
        `).join("");
    } catch (err) {
        mostrarMensaje("consumidores", err.message, "error");
    }
}

async function crearConsumidor(event) {
    event.preventDefault();
    if (!apiDisponible(CONFIG.API_CONSUMIDORES)) {
        mostrarMensaje("consumidores", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    const datos = {
        nombre: document.getElementById("cons-nombre").value,
        email: document.getElementById("cons-email").value,
        telefono: document.getElementById("cons-telefono").value,
        direccion: document.getElementById("cons-direccion").value,
    };
    try {
        const resp = await fetchServicio(`${CONFIG.API_CONSUMIDORES}/api/consumidores/`, "Consumidores", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("consumidores", "Consumidor registrado correctamente", "exito");
        document.getElementById("form-consumidor").reset();
        cargarConsumidores();
    } catch (err) { mostrarMensaje("consumidores", err.message, "error"); }
}

async function eliminarConsumidor(id) {
    if (!confirm("¿Está seguro de eliminar este consumidor?")) return;
    try {
        await fetchServicio(`${CONFIG.API_CONSUMIDORES}/api/consumidores/${id}`, "Consumidores", { method: "DELETE" });
        mostrarMensaje("consumidores", "Consumidor eliminado", "exito");
        cargarConsumidores();
    } catch (err) { mostrarMensaje("consumidores", err.message, "error"); }
}

// ============================================================
// Módulo de Restaurantes → API Gateway de RESTAURANTES
// ============================================================

async function cargarRestaurantes() {
    if (!apiDisponible(CONFIG.API_RESTAURANTES)) {
        mostrarMensaje("restaurantes", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/`, "Restaurantes");
        const datos = await resp.json();
        const tbody = document.getElementById("tabla-restaurantes");
        tbody.innerHTML = datos.map(r => `
            <tr>
                <td title="${r.id}">${idCorto(r.id)}</td>
                <td>${r.nombre}</td>
                <td>${r.tipo_cocina}</td>
                <td>${r.horario_apertura} - ${r.horario_cierre}</td>
                <td><button class="btn btn-peligro" onclick="eliminarRestaurante('${r.id}')">Eliminar</button></td>
            </tr>
        `).join("");
    } catch (err) { mostrarMensaje("restaurantes", err.message, "error"); }
}

async function crearRestaurante(event) {
    event.preventDefault();
    if (!apiDisponible(CONFIG.API_RESTAURANTES)) {
        mostrarMensaje("restaurantes", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    const datos = {
        nombre: document.getElementById("rest-nombre").value,
        direccion: document.getElementById("rest-direccion").value,
        telefono: document.getElementById("rest-telefono").value,
        tipo_cocina: document.getElementById("rest-tipo").value,
        horario_apertura: document.getElementById("rest-apertura").value,
        horario_cierre: document.getElementById("rest-cierre").value,
    };
    try {
        const resp = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/`, "Restaurantes", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("restaurantes", "Restaurante registrado correctamente", "exito");
        document.getElementById("form-restaurante").reset();
        cargarRestaurantes();
    } catch (err) { mostrarMensaje("restaurantes", err.message, "error"); }
}

async function eliminarRestaurante(id) {
    if (!confirm("¿Está seguro de eliminar este restaurante?")) return;
    try {
        await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/${id}`, "Restaurantes", { method: "DELETE" });
        mostrarMensaje("restaurantes", "Restaurante eliminado", "exito");
        cargarRestaurantes();
    } catch (err) { mostrarMensaje("restaurantes", err.message, "error"); }
}

// ============================================================
// Módulo de Menú → API Gateway de RESTAURANTES
// ============================================================

async function cargarMenu() {
    if (!apiDisponible(CONFIG.API_RESTAURANTES)) {
        mostrarMensaje("menu", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/`, "Restaurantes");
        const restaurantes = await resp.json();
        document.getElementById("menu-restaurante").innerHTML =
            restaurantes.map(r => `<option value="${r.id}">${r.nombre}</option>`).join("");

        const tbody = document.getElementById("tabla-menu");
        let filas = "";
        for (const r of restaurantes) {
            const respMenu = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/${r.id}/menu/`, "Restaurantes");
            const menu = await respMenu.json();
            for (const p of menu) {
                filas += `<tr>
                    <td title="${p.id}">${idCorto(p.id)}</td>
                    <td>${r.nombre}</td><td>${p.nombre}</td>
                    <td>$${p.precio.toFixed(2)}</td>
                    <td>${p.disponible ? "Sí" : "No"}</td>
                    <td><button class="btn btn-peligro" onclick="eliminarPlatillo('${p.id}')">Eliminar</button></td>
                </tr>`;
            }
        }
        tbody.innerHTML = filas || "<tr><td colspan='6'>No hay platillos registrados</td></tr>";
    } catch (err) { mostrarMensaje("menu", err.message, "error"); }
}

async function agregarPlatillo(event) {
    event.preventDefault();
    if (!apiDisponible(CONFIG.API_RESTAURANTES)) {
        mostrarMensaje("menu", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    const restauranteId = document.getElementById("menu-restaurante").value;
    const datos = {
        restaurante_id: restauranteId,
        nombre: document.getElementById("menu-nombre").value,
        descripcion: document.getElementById("menu-descripcion").value,
        precio: parseFloat(document.getElementById("menu-precio").value),
        disponible: 1,
    };
    try {
        const resp = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/${restauranteId}/menu/`, "Restaurantes", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("menu", "Platillo agregado correctamente", "exito");
        document.getElementById("form-menu").reset();
        cargarMenu();
    } catch (err) { mostrarMensaje("menu", err.message, "error"); }
}

async function eliminarPlatillo(id) {
    if (!confirm("¿Eliminar este platillo del menú?")) return;
    try {
        await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/menu/${id}`, "Restaurantes", { method: "DELETE" });
        mostrarMensaje("menu", "Platillo eliminado", "exito");
        cargarMenu();
    } catch (err) { mostrarMensaje("menu", err.message, "error"); }
}

// ============================================================
// Módulo de Repartidores → API Gateway de ENTREGAS
// ============================================================

async function cargarRepartidores() {
    if (!apiDisponible(CONFIG.API_ENTREGAS)) {
        mostrarMensaje("repartidores", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_ENTREGAS}/api/repartidores/`, "Entregas");
        const datos = await resp.json();
        const tbody = document.getElementById("tabla-repartidores");
        tbody.innerHTML = datos.map(r => `
            <tr>
                <td title="${r.id}">${idCorto(r.id)}</td>
                <td>${r.nombre}</td><td>${r.telefono}</td><td>${r.vehiculo}</td>
                <td>${r.disponible ? "✅ Sí" : "❌ No"}</td>
                <td><button class="btn btn-peligro" onclick="eliminarRepartidor('${r.id}')">Eliminar</button></td>
            </tr>
        `).join("");
    } catch (err) { mostrarMensaje("repartidores", err.message, "error"); }
}

async function crearRepartidor(event) {
    event.preventDefault();
    if (!apiDisponible(CONFIG.API_ENTREGAS)) {
        mostrarMensaje("repartidores", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    const datos = {
        nombre: document.getElementById("rep-nombre").value,
        telefono: document.getElementById("rep-telefono").value,
        vehiculo: document.getElementById("rep-vehiculo").value,
    };
    try {
        const resp = await fetchServicio(`${CONFIG.API_ENTREGAS}/api/repartidores/`, "Entregas", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("repartidores", "Repartidor registrado correctamente", "exito");
        document.getElementById("form-repartidor").reset();
        cargarRepartidores();
    } catch (err) { mostrarMensaje("repartidores", err.message, "error"); }
}

async function eliminarRepartidor(id) {
    if (!confirm("¿Eliminar este repartidor?")) return;
    try {
        await fetchServicio(`${CONFIG.API_ENTREGAS}/api/repartidores/${id}`, "Entregas", { method: "DELETE" });
        mostrarMensaje("repartidores", "Repartidor eliminado", "exito");
        cargarRepartidores();
    } catch (err) { mostrarMensaje("repartidores", err.message, "error"); }
}

// ============================================================
// Módulo de Pedidos → API Gateway de PEDIDOS
// (orquesta llamadas a Consumidores, Restaurantes y Entregas)
// ============================================================

let platillosDisponibles = [];

async function cargarPedidos() {
    // Cargar selectores (consumidores y restaurantes pueden no estar disponibles)
    try {
        if (apiDisponible(CONFIG.API_CONSUMIDORES)) {
            const respCons = await fetchServicio(`${CONFIG.API_CONSUMIDORES}/api/consumidores/`, "Consumidores");
            const consumidores = await respCons.json();
            document.getElementById("ped-consumidor").innerHTML =
                consumidores.map(c => `<option value="${c.id}">${c.nombre}</option>`).join("");
        } else {
            document.getElementById("ped-consumidor").innerHTML =
                `<option value="">⚠️ Microservicio Consumidores no disponible</option>`;
        }
    } catch (err) {
        document.getElementById("ped-consumidor").innerHTML =
            `<option value="">⚠️ Microservicio Consumidores no disponible</option>`;
    }

    try {
        if (apiDisponible(CONFIG.API_RESTAURANTES)) {
            const respRest = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/`, "Restaurantes");
            const restaurantes = await respRest.json();
            document.getElementById("ped-restaurante").innerHTML =
                `<option value="">-- Seleccione --</option>` +
                restaurantes.map(r => `<option value="${r.id}">${r.nombre}</option>`).join("");
        } else {
            document.getElementById("ped-restaurante").innerHTML =
                `<option value="">⚠️ Microservicio Restaurantes no disponible</option>`;
        }
    } catch (err) {
        document.getElementById("ped-restaurante").innerHTML =
            `<option value="">⚠️ Microservicio Restaurantes no disponible</option>`;
    }

    // Cargar tabla de pedidos
    if (!apiDisponible(CONFIG.API_PEDIDOS)) {
        mostrarMensaje("pedidos", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_PEDIDOS}/api/pedidos/`, "Pedidos");
        const pedidos = await resp.json();
        const tbody = document.getElementById("tabla-pedidos");
        tbody.innerHTML = pedidos.map(p => `
            <tr>
                <td title="${p.id}">${idCorto(p.id)}</td>
                <td title="${p.consumidor_id}">${idCorto(p.consumidor_id)}</td>
                <td title="${p.restaurante_id}">${idCorto(p.restaurante_id)}</td>
                <td><span class="estado estado-${p.estado}">${p.estado}</span></td>
                <td>$${p.total.toFixed(2)}</td>
                <td>${generarBotonesEstado(p)}</td>
            </tr>
        `).join("");
    } catch (err) { mostrarMensaje("pedidos", err.message, "error"); }
}

function generarBotonesEstado(pedido) {
    const botones = [];
    switch (pedido.estado) {
        case "CREADO":
            botones.push(`<button class="btn btn-exito" onclick="cambiarEstado('${pedido.id}', 'ACEPTADO')">Aceptar</button>`);
            botones.push(`<button class="btn btn-peligro" onclick="cancelarPedido('${pedido.id}')">Cancelar</button>`);
            break;
        case "ACEPTADO":
            botones.push(`<button class="btn" onclick="cambiarEstado('${pedido.id}', 'PREPARANDO')">Preparar</button>`);
            break;
        case "PREPARANDO":
            botones.push(`<button class="btn btn-exito" onclick="cambiarEstado('${pedido.id}', 'LISTO')">Listo</button>`);
            break;
        case "LISTO":
            botones.push(`<button class="btn" onclick="asignarRepartidorUI('${pedido.id}')">Asignar Repartidor</button>`);
            break;
        case "EN_CAMINO":
            botones.push(`<button class="btn btn-exito" onclick="cambiarEstado('${pedido.id}', 'ENTREGADO')">Entregado</button>`);
            break;
    }
    return botones.join(" ");
}

async function cargarMenuPedido() {
    const restauranteId = document.getElementById("ped-restaurante").value;
    const contenedor = document.getElementById("ped-platillos");
    if (!restauranteId) {
        contenedor.innerHTML = "<p><em>Seleccione un restaurante para ver los platillos</em></p>";
        return;
    }
    if (!apiDisponible(CONFIG.API_RESTAURANTES)) {
        contenedor.innerHTML = `<p class="mensaje mensaje-error">${MSG_NO_IMPLEMENTADO}</p>`;
        return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_RESTAURANTES}/api/restaurantes/${restauranteId}/menu/`, "Restaurantes");
        platillosDisponibles = await resp.json();
        if (platillosDisponibles.length === 0) {
            contenedor.innerHTML = "<p><em>Este restaurante no tiene platillos en el menú</em></p>";
            return;
        }
        contenedor.innerHTML = platillosDisponibles.map(p => `
            <div class="elemento-linea">
                <label>
                    <input type="checkbox" class="platillo-check" value="${p.id}" data-precio="${p.precio}">
                    ${p.nombre} - $${p.precio.toFixed(2)}
                </label>
                <input type="number" class="platillo-cant" data-id="${p.id}" value="1" min="1" max="10" style="width:60px">
            </div>
        `).join("");
    } catch (err) {
        contenedor.innerHTML = `<p class="mensaje mensaje-error">${err.message}</p>`;
    }
}

async function crearPedido(event) {
    event.preventDefault();
    if (!apiDisponible(CONFIG.API_PEDIDOS)) {
        mostrarMensaje("pedidos", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    const checks = document.querySelectorAll(".platillo-check:checked");
    if (checks.length === 0) {
        mostrarMensaje("pedidos", "Debe seleccionar al menos un platillo", "error"); return;
    }
    const elementos = [];
    checks.forEach(check => {
        const id = check.value;
        const cantInput = document.querySelector(`.platillo-cant[data-id="${id}"]`);
        elementos.push({ elemento_menu_id: id, cantidad: parseInt(cantInput.value) });
    });
    const datos = {
        consumidor_id: document.getElementById("ped-consumidor").value,
        restaurante_id: document.getElementById("ped-restaurante").value,
        direccion_entrega: document.getElementById("ped-direccion").value,
        elementos: elementos,
    };
    try {
        const resp = await fetchServicio(`${CONFIG.API_PEDIDOS}/api/pedidos/`, "Pedidos", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("pedidos", "Pedido creado correctamente", "exito");
        document.getElementById("form-pedido").reset();
        document.getElementById("ped-platillos").innerHTML =
            "<p><em>Seleccione un restaurante para ver los platillos</em></p>";
        cargarPedidos();
    } catch (err) { mostrarMensaje("pedidos", err.message, "error"); }
}

async function cambiarEstado(pedidoId, nuevoEstado) {
    if (!apiDisponible(CONFIG.API_PEDIDOS)) {
        mostrarMensaje("pedidos", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_PEDIDOS}/api/pedidos/${pedidoId}/estado`, "Pedidos", {
            method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ estado: nuevoEstado }),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("pedidos", `Estado cambiado a ${nuevoEstado}`, "exito");
        cargarPedidos();
    } catch (err) { mostrarMensaje("pedidos", err.message, "error"); }
}

async function asignarRepartidorUI(pedidoId) {
    if (!apiDisponible(CONFIG.API_ENTREGAS)) {
        mostrarMensaje("pedidos", "⚠️ API y microservicio de Entregas aún no implementado. No se puede asignar repartidor.", "error");
        return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_ENTREGAS}/api/repartidores/`, "Entregas");
        const repartidores = await resp.json();
        const disponibles = repartidores.filter(r => r.disponible);
        if (disponibles.length === 0) {
            mostrarMensaje("pedidos", "No hay repartidores disponibles", "error"); return;
        }
        const indice = prompt(
            `Seleccione el número del repartidor (1-${disponibles.length}):\n` +
            disponibles.map((r, i) => `${i + 1}. ${r.nombre} (${r.vehiculo})`).join("\n")
        );
        if (indice) {
            const repartidor = disponibles[parseInt(indice) - 1];
            if (!repartidor) { alert("Selección inválida"); return; }
            const resp2 = await fetchServicio(`${CONFIG.API_PEDIDOS}/api/pedidos/${pedidoId}/repartidor`, "Pedidos", {
                method: "PUT", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repartidor_id: repartidor.id }),
            });
            if (!resp2.ok) { const e = await resp2.json(); throw new Error(e.detail); }
            await cambiarEstado(pedidoId, "EN_CAMINO");
        }
    } catch (err) { mostrarMensaje("pedidos", err.message, "error"); }
}

async function cancelarPedido(pedidoId) {
    if (!confirm("¿Está seguro de cancelar este pedido?")) return;
    if (!apiDisponible(CONFIG.API_PEDIDOS)) {
        mostrarMensaje("pedidos", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        await fetchServicio(`${CONFIG.API_PEDIDOS}/api/pedidos/${pedidoId}`, "Pedidos", { method: "DELETE" });
        mostrarMensaje("pedidos", "Pedido cancelado", "exito");
        cargarPedidos();
    } catch (err) { mostrarMensaje("pedidos", err.message, "error"); }
}

// ============================================================
// Módulo de Pagos → API Gateway de PAGOS
// ============================================================

async function cargarPagos() {
    // Cargar selector de pedidos (depende del microservicio de Pedidos)
    try {
        if (apiDisponible(CONFIG.API_PEDIDOS)) {
            const resp = await fetchServicio(`${CONFIG.API_PEDIDOS}/api/pedidos/`, "Pedidos");
            const pedidos = await resp.json();
            const pedidosSinCancelar = pedidos.filter(p => p.estado !== "CANCELADO");
            document.getElementById("pago-pedido").innerHTML =
                pedidosSinCancelar.map(p =>
                    `<option value="${p.id}">Pedido ${idCorto(p.id)} - $${p.total.toFixed(2)}</option>`
                ).join("");
        } else {
            document.getElementById("pago-pedido").innerHTML =
                `<option value="">⚠️ Microservicio Pedidos no disponible</option>`;
        }
    } catch (err) {
        document.getElementById("pago-pedido").innerHTML =
            `<option value="">⚠️ Microservicio Pedidos no disponible</option>`;
    }

    // Cargar tabla de pagos
    if (!apiDisponible(CONFIG.API_PAGOS)) {
        mostrarMensaje("pagos", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    try {
        const resp = await fetchServicio(`${CONFIG.API_PAGOS}/api/pagos/`, "Pagos");
        const pagos = await resp.json();
        const tbody = document.getElementById("tabla-pagos");
        tbody.innerHTML = pagos.map(p => `
            <tr>
                <td title="${p.id}">${idCorto(p.id)}</td>
                <td title="${p.pedido_id}">${idCorto(p.pedido_id)}</td>
                <td>$${p.monto.toFixed(2)}</td>
                <td>${p.metodo_pago}</td>
                <td><span class="estado estado-ENTREGADO">${p.estado}</span></td>
                <td>${p.referencia}</td>
            </tr>
        `).join("");
    } catch (err) { mostrarMensaje("pagos", err.message, "error"); }
}

async function procesarPago(event) {
    event.preventDefault();
    if (!apiDisponible(CONFIG.API_PAGOS)) {
        mostrarMensaje("pagos", MSG_NO_IMPLEMENTADO, "error"); return;
    }
    const datos = {
        pedido_id: document.getElementById("pago-pedido").value,
        metodo_pago: document.getElementById("pago-metodo").value,
    };
    try {
        const resp = await fetchServicio(`${CONFIG.API_PAGOS}/api/pagos/`, "Pagos", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        mostrarMensaje("pagos", "Pago procesado correctamente", "exito");
        cargarPagos();
    } catch (err) { mostrarMensaje("pagos", err.message, "error"); }
}

// ============================================================
// Inicialización
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    cargarConsumidores();
});
