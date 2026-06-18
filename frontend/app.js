/**
 * app.js — CanchaYa v4
 *
 * Cambios principales:
 *   - Vista COMPRADOR: Turnos / Mis reservas / Mis fichas
 *   - Vista DUEÑO: solo Dashboard (tabs: Hoy / Todas / Próximos días / Pendientes)
 *   - Verificar pago MP activamente (resuelve el problema del webhook local)
 *   - Tab "Pendientes" muestra quién está pendiente con botón Verificar por reserva
 */

const API_BASE = window.API_BASE || "http://127.0.0.1:8000";
console.log("[CONFIG] API_BASE =", API_BASE);

// ── Estado global ─────────────────────────────────────────────────────────
const state = {
  token:         localStorage.getItem("canchaYaToken") || null,
  usuario:       JSON.parse(localStorage.getItem("canchaYaUsuario") || "null"),
  turnoSel:      null,
  reservaCreada: null,
  canchaCanjeId: null,
  mpAbierto:     false,   // si el usuario ya abrió el checkout de MP
};

// ── Helper HTTP ───────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  console.log(`[API] ${options.method || "GET"} ${path}`);
  try {
    const res  = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || `Error ${res.status}`;
      console.error(`[API] ❌ ${res.status} ${path}:`, data);
      throw new ApiError(msg, res.status);
    }
    console.log(`[API] ✅ ${path}`, data);
    return data;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    console.error(`[API] ❌ Red ${path}:`, e);
    throw new ApiError("Error de conexión con el servidor");
  }
}

class ApiError extends Error {
  constructor(msg, status) { super(msg); this.status = status; }
}

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  console.log("[INIT] Iniciando CanchaYa...");

  // Verificar si el token almacenado sigue válido
  if (state.token) {
    try {
      const me = await apiFetch("/auth/me");
      state.usuario = me;
      localStorage.setItem("canchaYaUsuario", JSON.stringify(me));
      console.log(`[INIT] Sesión válida: ${me.email} (${me.rol})`);
    } catch (e) {
      console.warn("[INIT] Token expirado, cerrando sesión:", e.message);
      _limpiarSesion();
    }
  }

  renderizarSegunRol();

  if (!esDuenio()) {
    const hoy = new Date().toISOString().split("T")[0];
    document.getElementById("filtro-fecha").value = hoy;
    document.getElementById("canje-fecha").value  = hoy;
    document.getElementById("filtro-cancha").addEventListener("change", cargarTurnos);
    document.getElementById("filtro-fecha").addEventListener("change",  cargarTurnos);
    await cargarCanchas();
    await cargarTurnos();
  }

  // ── Manejar redirección desde MP (pago-exitoso.html o pago-fallido.html) ──
  const urlParams = new URLSearchParams(window.location.search);
  const verificarId = urlParams.get("verificar");
  if (verificarId) {
    console.log(`[INIT] Detectada redirección de MP para reserva #${verificarId}`);
    // Esperar un poco a que todo cargue, luego intentar verificar
    setTimeout(async () => {
      try {
        const data = await apiFetch(`/pagos/verificar/${verificarId}`);
        if (data.estado_pago === "aprobado") {
          mostrarToast("✅ ¡Pago confirmado! El turno está reservado.", "success");
          if (!esDuenio()) { cargarTurnos(); cargarHistorial(); cargarFichas(); }
        } else if (data.estado_pago === "rechazado") {
          mostrarToast("❌ El pago fue rechazado. El turno quedó libre.", "error");
          if (!esDuenio()) cargarTurnos();
        } else {
          mostrarToast(`Pago en estado: ${data.estado_pago}. Verificá manualmente.`, "info");
        }
      } catch (e) {
        console.warn("[INIT] Error verificando pago post-redirección:", e.message);
      }
      // Limpiar URL
      window.history.replaceState({}, "", window.location.pathname);
    }, 1000);
  }

  console.log("[INIT] ✅ Listo");
});

// ── Rol helpers ───────────────────────────────────────────────────────────
function esDuenio() {
  return state.usuario?.rol === "duenio";
}

function renderizarSegunRol() {
  actualizarHeaderNav();
  const comprador = document.getElementById("vista-comprador");
  const duenio    = document.getElementById("vista-duenio");

  if (esDuenio()) {
    comprador.style.display = "none";
    duenio.style.display    = "block";
    document.getElementById("duenio-cancha-nombre").textContent =
      `Cancha asignada: ${state.usuario?.cancha_id ? `ID ${state.usuario.cancha_id}` : "—"}`;
    // Setear fecha de hoy en el dashboard
    const hoy = new Date().toISOString().split("T")[0];
    document.getElementById("dashboard-fecha").value = hoy;
    cargarDashboard();
  } else {
    comprador.style.display = "block";
    duenio.style.display    = "none";
  }
}

// ── Header nav ────────────────────────────────────────────────────────────
function actualizarHeaderNav() {
  const nav = document.getElementById("header-nav");
  if (state.usuario) {
    const rolLabel = esDuenio() ? "🔑 Dueño" : "👤 Comprador";
    nav.innerHTML = `
      <span class="nav-user-info">${rolLabel} — <strong>${state.usuario.nombre.split(" ")[0]}</strong></span>
      <button class="btn-nav" onclick="cerrarSesion()">Cerrar sesión</button>
    `;
  } else {
    nav.innerHTML = `<button class="btn-nav" onclick="abrirModalAuth()">Ingresar / Registrarse</button>`;
  }
}

// ── Navegación comprador ──────────────────────────────────────────────────
function mostrarVistaComprador(btn) {
  const vista = btn.dataset.vista;
  document.querySelectorAll(".vista-comp").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".tabs .tab").forEach(t => t.classList.remove("active"));
  document.getElementById(`comp-${vista}`).classList.add("active");
  btn.classList.add("active");

  if (vista === "historial") cargarHistorial();
  if (vista === "fichas")    cargarFichas();
}

// ── Navegación dashboard dueño ────────────────────────────────────────────
function mostrarTabDashboard(btn) {
  const tab = btn.dataset.dtab;
  document.querySelectorAll(".dtab").forEach(d => d.classList.remove("active"));
  document.querySelectorAll(".tabs .tab").forEach(t => t.classList.remove("active"));
  document.getElementById(`dtab-${tab}`).classList.add("active");
  btn.classList.add("active");

  if (tab === "reservas")   cargarTablaReservas();
  if (tab === "semana")     cargarTablaSemana();
  if (tab === "pendientes") cargarPendientes();
}

// ── Canchas (selector filtro) ─────────────────────────────────────────────
async function cargarCanchas() {
  console.log("[CANCHAS] Cargando lista...");
  try {
    const canchas = await apiFetch("/canchas");
    const sel = document.getElementById("filtro-cancha");
    sel.innerHTML = "";
    canchas.forEach(c => {
      const o = document.createElement("option");
      o.value = c.id;
      o.textContent = `${c.nombre} (${formatTipo(c.tipo)})`;
      sel.appendChild(o);
    });
    console.log(`[CANCHAS] ${canchas.length} canchas cargadas`);
  } catch (e) {
    console.error("[CANCHAS] Error:", e.message);
    mostrarToast("No se pudieron cargar las canchas", "error");
  }
}

// ── Turnos disponibles ────────────────────────────────────────────────────
async function cargarTurnos() {
  const loader = document.getElementById("loader");
  const grid   = document.getElementById("turnos-grid");
  const empty  = document.getElementById("empty-state");
  const cid    = document.getElementById("filtro-cancha").value;
  const fecha  = document.getElementById("filtro-fecha").value;

  loader.style.display = "block";
  grid.innerHTML = "";
  empty.style.display = "none";

  const p = new URLSearchParams({ solo_disponibles: "true" });
  if (cid)   p.append("cancha_id", cid);
  if (fecha) p.append("fecha", fecha);

  console.log(`[TURNOS] Cargando: cancha=${cid||"todas"} fecha=${fecha}`);
  try {
    const turnos = await apiFetch(`/turnos?${p}`);
    loader.style.display = "none";
    if (!turnos.length) { empty.style.display = "block"; return; }
    console.log(`[TURNOS] ${turnos.length} disponibles`);
    turnos.forEach(t => grid.appendChild(crearCardTurno(t)));
  } catch (e) {
    loader.style.display = "none";
    console.error("[TURNOS] Error:", e.message);
    mostrarToast(`Error cargando turnos: ${e.message}`, "error");
  }
}

function crearCardTurno(t) {
  const card = document.createElement("div");
  card.className = "turno-card";
  card.onclick   = () => abrirModalReserva(t);
  card.innerHTML = `
    <div class="hora">${t.hora_inicio.slice(0,5)} – ${t.hora_fin.slice(0,5)}</div>
    <div class="cancha-nombre">${t.cancha.nombre}</div>
    <span class="tipo-badge">${formatTipo(t.cancha.tipo)}</span>
    <div class="precio">${formatPrecio(t.cancha.precio_hora)} / hora</div>
    <div class="fecha-tag">📅 ${formatFecha(t.fecha)}</div>
  `;
  return card;
}

// ── Modal Reserva ─────────────────────────────────────────────────────────
function abrirModalReserva(turno) {
  console.log(`[RESERVA] Abriendo modal turno ${turno.id}`);
  state.turnoSel      = turno;
  state.reservaCreada = null;
  state.mpAbierto     = false;

  document.getElementById("info-cancha").textContent  = turno.cancha.nombre;
  document.getElementById("info-tipo").textContent    = formatTipo(turno.cancha.tipo);
  document.getElementById("info-fecha").textContent   = formatFecha(turno.fecha);
  document.getElementById("info-horario").textContent = `${turno.hora_inicio.slice(0,5)} – ${turno.hora_fin.slice(0,5)}`;
  document.getElementById("info-precio").textContent  = formatPrecio(turno.cancha.precio_hora);

  if (state.usuario) {
    document.getElementById("input-nombre").value = state.usuario.nombre;
    document.getElementById("input-email").value  = state.usuario.email;
  } else {
    document.getElementById("input-nombre").value = "";
    document.getElementById("input-email").value  = "";
  }
  document.getElementById("input-telefono").value = "";

  // Reset al estado inicial — FIX bug botón "reservando..."
  document.getElementById("form-reserva").style.display  = "block";
  document.getElementById("success-state").style.display = "none";
  const btn = document.getElementById("btn-confirmar");
  btn.disabled    = false;
  btn.textContent = "Reservar y pagar";

  document.getElementById("modal-reserva").classList.add("open");
}

function cerrarModalReserva() {
  document.getElementById("modal-reserva").classList.remove("open");
  state.turnoSel      = null;
  state.reservaCreada = null;
  state.mpAbierto     = false;
}

async function confirmarReserva() {
  const nombre   = document.getElementById("input-nombre").value.trim();
  const email    = document.getElementById("input-email").value.trim();
  const telefono = document.getElementById("input-telefono").value.trim();

  if (!nombre)                      { mostrarToast("Ingresá tu nombre", "error");   return; }
  if (!email || !email.includes("@")) { mostrarToast("Email inválido", "error");     return; }
  if (!state.turnoSel)              { mostrarToast("Sin turno seleccionado", "error"); return; }

  const btn = document.getElementById("btn-confirmar");
  btn.disabled    = true;
  btn.textContent = "Reservando...";

  console.log(`[RESERVA] Creando: turno=${state.turnoSel.id} cliente=${nombre}`);
  try {
    const body = {
      turno_id:         state.turnoSel.id,
      nombre_cliente:   nombre,
      email_cliente:    email,
      telefono_cliente: telefono || null,
      usuario_id:       state.usuario?.id || null,
    };
    const reserva = await apiFetch("/reservas", { method: "POST", body: JSON.stringify(body) });
    state.reservaCreada = reserva;

    console.log(`[RESERVA] ✅ Creada #${reserva.id} estado=${reserva.estado_pago}`);
    document.getElementById("form-reserva").style.display  = "none";
    document.getElementById("success-state").style.display = "block";
    document.getElementById("badge-reserva-id").textContent = `#${reserva.id}`;
    document.getElementById("success-msg").textContent =
      `Reserva creada para ${nombre}. Pagá ahora para confirmar el turno.`;

    cargarTurnos();
  } catch (e) {
    console.error("[RESERVA] Error:", e.message);
    mostrarToast(e.message, "error");
    btn.disabled    = false;
    btn.textContent = "Reservar y pagar";
  }
}

// ── Modal Pago ────────────────────────────────────────────────────────────
function abrirModalPago() {
  if (!state.reservaCreada) { console.error("[PAGO] No hay reserva"); return; }
  document.getElementById("pago-subtitle").textContent =
    `Reserva #${state.reservaCreada.id} — ${formatPrecio(state.turnoSel?.cancha?.precio_hora || 0)}`;
  // Ocultar sección verificar hasta que el usuario abra MP
  document.getElementById("mp-verificar-section").style.display = "none";
  state.mpAbierto = false;
  document.getElementById("modal-pago").classList.add("open");
}

function cerrarModalPago() {
  document.getElementById("modal-pago").classList.remove("open");
}

async function pagarConMP() {
  if (!state.reservaCreada) return;
  console.log(`[PAGO-MP] Iniciando para reserva #${state.reservaCreada.id}`);
  mostrarToast("Generando link de pago...", "info");

  try {
    const data = await apiFetch(`/pagos/link/${state.reservaCreada.id}`);

    if (data.modo === "simulacion") {
      mostrarToast("Token MP no configurado. Usá 'Simular pago aprobado'.", "error");
      return;
    }

    if (!data.checkout_url) {
      throw new Error("No se recibió URL de checkout");
    }

    console.log(`[PAGO-MP] Abriendo checkout: ${data.checkout_url}`);
    window.open(data.checkout_url, "_blank");

    // Después de abrir MP, mostrar el botón de verificación
    state.mpAbierto = true;
    document.getElementById("mp-verificar-section").style.display = "block";
    mostrarToast("Checkout abierto. Después de pagar, clickeá 'Verificar pago'.", "info");

  } catch (e) {
    console.error("[PAGO-MP] Error:", e.message);
    mostrarToast(e.message, "error");
  }
}

/**
 * SOLUCIÓN AL PROBLEMA PRINCIPAL:
 * Como el webhook de MP no puede llegar a localhost, el frontend
 * consulta activamente al backend si el pago fue procesado.
 * El backend a su vez le pregunta a la API de MP usando el preference_id.
 */
async function verificarPagoMP() {
  if (!state.reservaCreada) return;
  const reservaId = state.reservaCreada.id;
  console.log(`[VERIFICAR] Consultando estado del pago reserva #${reservaId}`);

  const btn = document.querySelector("#mp-verificar-section button");
  if (btn) { btn.disabled = true; btn.textContent = "Verificando..."; }
  mostrarToast("Consultando estado del pago en Mercado Pago...", "info");

  try {
    const data = await apiFetch(`/pagos/verificar/${reservaId}`);
    console.log(`[VERIFICAR] Resultado:`, data);

    if (data.estado_pago === "aprobado" && data.cambio) {
      mostrarToast("✅ ¡Pago confirmado! El turno está reservado.", "success");
      cerrarModalPago();
      document.getElementById("btn-pagar").style.display = "none";
      document.getElementById("success-msg").textContent =
        "🎉 ¡Pago confirmado! Tu turno está asegurado." +
        (state.usuario ? " Se sumó 1 ficha a tu cuenta." : "");
      cargarTurnos();
      if (state.usuario) { cargarHistorial(); cargarFichas(); }

    } else if (data.estado_pago === "aprobado" && !data.cambio) {
      mostrarToast("✅ El pago ya estaba confirmado.", "success");
      cerrarModalPago();

    } else if (data.estado_pago === "rechazado") {
      mostrarToast("❌ El pago fue rechazado. El turno quedó libre.", "error");
      cerrarTodo();
      cargarTurnos();

    } else {
      // pendiente — MP todavía no registra el pago
      mostrarToast(data.mensaje || "El pago todavía no aparece en MP. Esperá unos segundos.", "info");
      if (btn) { btn.disabled = false; btn.textContent = "🔍 Verificar pago de MP"; }
    }

  } catch (e) {
    console.error("[VERIFICAR] Error:", e.message);
    mostrarToast(`Error verificando: ${e.message}`, "error");
    if (btn) { btn.disabled = false; btn.textContent = "🔍 Verificar pago de MP"; }
  }
}

async function pagarMock(status) {
  if (!state.reservaCreada) return;
  console.log(`[MOCK] Simulando pago ${status} reserva #${state.reservaCreada.id}`);

  try {
    const data = await apiFetch("/pagos/mock-confirmar", {
      method: "POST",
      body: JSON.stringify({ reserva_id: state.reservaCreada.id, status }),
    });
    cerrarModalPago();
    if (status === "approved") {
      mostrarToast(`✅ Pago aprobado — Reserva #${data.id}`, "success");
      document.getElementById("btn-pagar").style.display = "none";
      document.getElementById("success-msg").textContent =
        "🎉 ¡Pago confirmado! " + (state.usuario ? "Se sumó 1 ficha a tu cuenta." : "");
      cargarTurnos();
      if (state.usuario) { cargarHistorial(); cargarFichas(); }
    } else {
      mostrarToast("❌ Pago rechazado — El turno quedó libre.", "error");
      cerrarTodo();
      cargarTurnos();
    }
  } catch (e) {
    console.error("[MOCK] Error:", e.message);
    mostrarToast(e.message, "error");
  }
}

function cerrarTodo() {
  document.getElementById("modal-reserva").classList.remove("open");
  document.getElementById("modal-pago").classList.remove("open");
  state.turnoSel      = null;
  state.reservaCreada = null;
  state.mpAbierto     = false;
  console.log("[STATE] Estado de reserva limpiado");
}

// ── Historial ─────────────────────────────────────────────────────────────
async function cargarHistorial() {
  const c = document.getElementById("historial-content");
  if (!state.usuario) {
    c.innerHTML = `<div class="login-prompt"><div class="icon">🔐</div>
      <p>Iniciá sesión para ver tu historial.</p>
      <button class="btn btn-primary" style="width:auto;padding:10px 24px" onclick="abrirModalAuth()">Iniciar sesión</button>
    </div>`;
    return;
  }
  c.innerHTML = `<div style="text-align:center;padding:40px"><div class="spinner"></div></div>`;
  console.log(`[HISTORIAL] Cargando usuario ${state.usuario.id}`);
  try {
    const reservas = await apiFetch("/reservas/mis-reservas");
    console.log(`[HISTORIAL] ${reservas.length} reservas`);
    if (!reservas.length) {
      c.innerHTML = `<div class="login-prompt"><div class="icon">📋</div>
        <p>Todavía no tenés reservas. ¡Reservá tu primera cancha!</p></div>`;
      return;
    }
    c.innerHTML = `<div class="historial-lista">${reservas.map(r => `
      <div class="historial-card">
        <div class="historial-hora">
          ${r.turno.hora_inicio.slice(0,5)}
          <small>${r.turno.hora_fin.slice(0,5)}</small>
        </div>
        <div class="historial-info">
          <div class="historial-cancha">${r.turno.cancha.nombre}</div>
          <div class="historial-fecha">📅 ${formatFecha(r.turno.fecha)} — ${formatTipo(r.turno.cancha.tipo)}</div>
          <div class="historial-fecha">💰 ${formatPrecio(r.turno.cancha.precio_hora)}</div>
          ${r.canje_fichas ? '<div class="historial-canje">⭐ Canjeado con fichas</div>' : ''}
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px">
          <span class="estado-badge estado-${r.estado_pago}">${formatEstado(r.estado_pago)}</span>
          ${r.estado_pago === 'pendiente' ? `
            <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">
              <button class="btn-verificar" style="font-size:.8rem;padding:7px 12px"
                onclick="pagarReservaDesdeHistorial(${r.id}, this)">
                💳 Pagar
              </button>
              <button class="btn-verificar" style="font-size:.8rem;padding:7px 12px;background:var(--red);color:#fff;border:1px solid var(--red)"
                onclick="cancelarReservaHistorial(${r.id}, this)">
                ✕ Cancelar
              </button>
              <button class="btn-verificar" style="font-size:.8rem;padding:7px 12px"
                onclick="verificarPagoDesdeHistorial(${r.id}, this)">
                🔍 Verificar
              </button>
            </div>` : ''}
        </div>
      </div>`).join("")}</div>`;
  } catch (e) {
    console.error("[HISTORIAL] Error:", e.message);
    c.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
  }
}

async function verificarPagoDesdeHistorial(reservaId, btn) {
  console.log(`[HISTORIAL] Verificando pago reserva #${reservaId}`);
  btn.disabled    = true;
  btn.textContent = "Verificando...";
  try {
    const data = await apiFetch(`/pagos/verificar/${reservaId}`);
    if (data.estado_pago === "aprobado") {
      mostrarToast("✅ ¡Pago confirmado!", "success");
      cargarHistorial();
      cargarFichas();
      cargarTurnos();
    } else if (data.estado_pago === "rechazado") {
      mostrarToast("❌ Pago rechazado. Turno liberado.", "error");
      cargarHistorial();
      cargarTurnos();
    } else {
      mostrarToast(data.mensaje || "Pago todavía pendiente en MP.", "info");
      btn.disabled    = false;
      btn.textContent = "🔍 Verificar pago";
    }
  } catch (e) {
    console.error("[HISTORIAL-VERIFICAR] Error:", e.message);
    mostrarToast(e.message, "error");
    btn.disabled    = false;
    btn.textContent = "🔍 Verificar pago";
  }
}

// ── Pagar desde Historial ────────────────────────────────────────────────
async function pagarReservaDesdeHistorial(reservaId, btn) {
  console.log(`[HISTORIAL] Generando link de pago reserva #${reservaId}`);
  btn.disabled    = true;
  btn.textContent = "Generando link...";
  try {
    const data = await apiFetch(`/pagos/link/${reservaId}`);
    if (data.modo === "simulacion") {
      mostrarToast("Token MP no configurado. Usá 'Simular pago' desde la reserva.", "error");
      btn.disabled    = false;
      btn.textContent = "💳 Pagar";
      return;
    }
    if (!data.checkout_url) {
      throw new Error("No se recibió URL de checkout");
    }
    window.open(data.checkout_url, "_blank");
    mostrarToast("Checkout abierto. Después de pagar, clickeá 'Verificar'.", "info");
    btn.textContent = "💳 Pagar (abierto)";
    btn.disabled    = false;
  } catch (e) {
    console.error("[HISTORIAL-PAGAR] Error:", e.message);
    mostrarToast(e.message, "error");
    btn.disabled    = false;
    btn.textContent = "💳 Pagar";
  }
}

// ── Cancelar reserva (genérico, usado desde historial y dashboard) ──────
async function _cancelarReserva(reservaId, btn, recargarFn) {
  if (!confirm("¿Estás seguro de cancelar esta reserva? El turno quedará libre.")) return;
  console.log(`[CANCELAR] Cancelando reserva #${reservaId}`);
  const original = btn.textContent;
  btn.disabled    = true;
  btn.textContent = "Cancelando...";
  try {
    await apiFetch(`/reservas/cancelar/${reservaId}`, { method: "POST" });
    mostrarToast(`✅ Reserva #${reservaId} cancelada. Turno liberado.`, "success");
    if (recargarFn) recargarFn();
  } catch (e) {
    console.error("[CANCELAR] Error:", e.message);
    mostrarToast(e.message, "error");
    btn.disabled    = false;
    btn.textContent = original;
  }
}

function cancelarReservaHistorial(reservaId, btn) {
  _cancelarReserva(reservaId, btn, () => { cargarHistorial(); cargarTurnos(); });
}

function cancelarReservaDashboard(reservaId, btn) {
  _cancelarReserva(reservaId, btn, () => { cargarDashboard(); cargarPendientes(); });
}

// ── Fichas ────────────────────────────────────────────────────────────────
async function cargarFichas() {
  const c = document.getElementById("fichas-content");
  if (!state.usuario) {
    c.innerHTML = `<div class="login-prompt"><div class="icon">⭐</div>
      <p>Iniciá sesión para ver tus fichas.</p>
      <button class="btn btn-primary" style="width:auto;padding:10px 24px" onclick="abrirModalAuth()">Iniciar sesión</button>
    </div>`;
    return;
  }
  c.innerHTML = `<div style="text-align:center;padding:40px"><div class="spinner"></div></div>`;
  console.log(`[FICHAS] Cargando usuario ${state.usuario.id}`);
  try {
    const fichas = await apiFetch("/reservas/mis-fichas");
    console.log(`[FICHAS] ${fichas.length} registros`);
    if (!fichas.length) {
      c.innerHTML = `<div class="login-prompt"><div class="icon">⭐</div>
        <p>Todavía no tenés fichas.<br>
        <small>Cada reserva pagada suma 1 ficha por cancha. Con 10 fichas canjeás un turno gratis.</small></p>
      </div>`;
      return;
    }
    c.innerHTML = `<div class="fichas-grid">${fichas.map(f => {
      const disp = f.fichas_disponibles;
      const pct  = Math.min((disp % 10) / 10 * 100, 100);
      return `
        <div class="ficha-card">
          <div class="ficha-cancha">${f.cancha_nombre}</div>
          <div class="ficha-contador">
            <span class="ficha-num">${disp}</span>
            <span class="ficha-label">fichas disponibles</span>
          </div>
          <div class="ficha-progress">
            <div class="ficha-progress-fill" style="width:${disp >= 10 ? 100 : pct}%"></div>
          </div>
          <div class="ficha-meta">
            ${disp >= 10
              ? "🎉 ¡Podés canjear un turno gratis!"
              : `${disp}/10 — te faltan ${10 - (disp % 10)} para canjear`}
            <br>Acumuladas: ${f.fichas_acumuladas} | Canjeadas: ${f.fichas_canjeadas}
          </div>
          <button class="ficha-canje-btn" onclick="abrirModalCanje(${f.cancha_id}, '${f.cancha_nombre}')"
            ${f.puede_canjear ? "" : "disabled"}>
            ${f.puede_canjear ? "⭐ Canjear turno gratis" : "Seguí acumulando..."}
          </button>
        </div>`;
    }).join("")}</div>`;
  } catch (e) {
    console.error("[FICHAS] Error:", e.message);
    c.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
  }
}

// ── Canje ─────────────────────────────────────────────────────────────────
function abrirModalCanje(canchaId, nombre) {
  state.canchaCanjeId = canchaId;
  document.getElementById("canje-subtitle").textContent =
    `Elegí un turno libre en ${nombre} — canjea 10 fichas`;
  const hoy = new Date().toISOString().split("T")[0];
  document.getElementById("canje-fecha").value = hoy;
  document.getElementById("modal-canje").classList.add("open");
  cargarTurnosCanje(hoy);
}

async function cargarTurnosCanje(fecha) {
  const lista = document.getElementById("canje-turnos-lista");
  if (!state.canchaCanjeId || !fecha) return;
  lista.innerHTML = `<div style="text-align:center;padding:20px"><div class="spinner"></div></div>`;
  try {
    const p = new URLSearchParams({ cancha_id: state.canchaCanjeId, fecha, solo_disponibles: "true" });
    const turnos = await apiFetch(`/turnos?${p}`);
    if (!turnos.length) {
      lista.innerHTML = `<p style="color:var(--muted);text-align:center;padding:20px">Sin turnos disponibles para esta fecha.</p>`;
      return;
    }
    lista.innerHTML = turnos.map(t => `
      <button onclick="confirmarCanje(${t.id})" class="pago-btn" style="width:100%">
        <span class="pago-icon" style="font-size:1.3rem;color:var(--green);font-family:var(--ff-display);font-weight:700">
          ${t.hora_inicio.slice(0,5)}
        </span>
        <span>
          <span class="pago-title">hasta ${t.hora_fin.slice(0,5)}</span>
          <span class="pago-desc">⭐ Gratis con fichas</span>
        </span>
      </button>`).join("");
  } catch (e) {
    lista.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
  }
}

async function confirmarCanje(turnoId) {
  if (!state.usuario) { mostrarToast("Necesitás iniciar sesión", "error"); return; }
  console.log(`[CANJE] Turno ${turnoId} usuario ${state.usuario.id}`);
  try {
    const reserva = await apiFetch(`/reservas/canjear?turno_id=${turnoId}`, { method: "POST" });
    document.getElementById("modal-canje").classList.remove("open");
    mostrarToast(`⭐ ¡Turno canjeado! Reserva #${reserva.id}`, "success");
    cargarTurnos(); cargarFichas(); cargarHistorial();
  } catch (e) {
    mostrarToast(e.message, "error");
  }
}

// ── Dashboard dueño ───────────────────────────────────────────────────────
async function cargarDashboard() {
  if (!esDuenio()) return;
  console.log("[DASHBOARD] Cargando...");

  try {
    const fecha = document.getElementById("dashboard-fecha").value;
    const params = fecha ? `?fecha=${fecha}` : "";

    const [resumen, hoyData] = await Promise.all([
      apiFetch("/dashboard/resumen"),
      apiFetch(`/dashboard/turnos-hoy${params}`),
    ]);

    // Actualizar nombre de cancha
    document.getElementById("duenio-cancha-nombre").textContent =
      `Cancha: ${resumen.cancha_nombre}`;

    // Stats
    document.getElementById("stat-aprobadas").textContent = resumen.reservas_aprobadas;
    document.getElementById("stat-pendientes").textContent = resumen.reservas_pendientes;
    document.getElementById("stat-canjes").textContent     = resumen.reservas_canje;
    document.getElementById("stat-ingresos").textContent   =
      "$" + Number(resumen.ingresos_reales).toLocaleString("es-AR");
    document.getElementById("stat-ingresos-dia").textContent =
      "$" + Number(resumen.ingresos_dia).toLocaleString("es-AR");
    document.getElementById("stat-ingresos-mensuales").textContent =
      "$" + Number(resumen.ingresos_mensuales).toLocaleString("es-AR");
    document.getElementById("stat-libres-hoy").textContent = resumen.turnos_libres_hoy;

    // Tabla Hoy
    renderizarTablaHoy(hoyData);

    console.log("[DASHBOARD] ✅ Cargado");
  } catch (e) {
    console.error("[DASHBOARD] Error:", e.message);
    mostrarToast(`Error cargando dashboard: ${e.message}`, "error");
  }
}

function renderizarTablaHoy(hoyData) {
  const tbody = document.getElementById("tbody-hoy");
  if (!hoyData.turnos || !hoyData.turnos.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px">Sin turnos para hoy</td></tr>`;
    return;
  }

  tbody.innerHTML = hoyData.turnos.map(t => {
    const rowClass = t.estado === "pagado" ? "row-aprobado"
                   : t.estado === "pendiente_pago" ? "row-pendiente"
                   : "row-libre";

    const estadoBadge = t.estado === "libre"
      ? `<span class="libre-badge">Libre</span>`
      : `<span class="estado-badge estado-${t.estado_pago}">${formatEstado(t.estado_pago)}</span>`;

    const acciones = t.reserva_id && t.estado_pago === "pendiente" ? `
      <div style="display:flex;gap:4px;flex-wrap:wrap">
        <button class="btn-verificar" style="font-size:.78rem;padding:6px 10px"
          onclick="verificarPagoDashboard(${t.reserva_id}, this)">
          🔍 Verificar
        </button>
        <button class="btn-verificar" style="font-size:.78rem;padding:6px 10px;background:var(--red);color:#fff;border:1px solid var(--red)"
          onclick="cancelarReservaDashboard(${t.reserva_id}, this)">
          ✕ Cancelar
        </button>
      </div>` : "—";

    return `<tr class="${rowClass}">
      <td><strong>${t.hora_inicio} – ${t.hora_fin}</strong></td>
      <td>${estadoBadge}</td>
      <td>${t.cliente || "—"}</td>
      <td>${t.email || "—"}</td>
      <td>${t.telefono || "—"}</td>
      <td>${t.tipo_pago ? (t.tipo_pago === "canje" ? "⭐ Canje" : "💳 MP") : "—"}</td>
      <td>${acciones}</td>
    </tr>`;
  }).join("");
}

function cambiarFechaDashboard(delta) {
  const input = document.getElementById("dashboard-fecha");
  const fecha = new Date(input.value + "T12:00:00");
  fecha.setDate(fecha.getDate() + delta);
  input.value = fecha.toISOString().split("T")[0];
  cargarDashboard();
}

async function cargarTablaReservas() {
  const fecha  = document.getElementById("reservas-filtro-fecha").value;
  const estado = document.getElementById("reservas-filtro-estado").value;
  const tbody  = document.getElementById("tbody-reservas");

  tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:20px"><div class="spinner" style="margin:auto"></div></td></tr>`;

  const p = new URLSearchParams();
  if (fecha)  p.append("fecha", fecha);
  if (estado) p.append("estado", estado);

  console.log(`[DASHBOARD] Cargando reservas filtro: fecha=${fecha} estado=${estado}`);
  try {
    const reservas = await apiFetch(`/dashboard/reservas?${p}`);
    console.log(`[DASHBOARD] ${reservas.length} reservas`);

    if (!reservas.length) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:20px">Sin reservas con esos filtros</td></tr>`;
      return;
    }

    tbody.innerHTML = reservas.map(r => `
      <tr class="${r.estado_pago === 'aprobado' ? 'row-aprobado' : 'row-pendiente'}">
        <td>#${r.reserva_id}</td>
        <td>${r.fecha}</td>
        <td>${r.hora_inicio} – ${r.hora_fin}</td>
        <td><strong>${r.cliente}</strong></td>
        <td>${r.email}</td>
        <td>${r.telefono}</td>
        <td><span class="estado-badge estado-${r.estado_pago}">${formatEstado(r.estado_pago)}</span></td>
        <td>${r.tipo_pago === "canje" ? "⭐ Canje" : "💳 MP"}</td>
        <td style="font-size:.78rem;color:var(--muted)">${r.reservado_el}</td>
        <td>${r.estado_pago === 'pendiente' ? `
          <button class="btn-verificar" style="font-size:.78rem;padding:6px 10px"
            onclick="verificarPagoDashboard(${r.reserva_id}, this)">
            🔍 Verificar
          </button>` : "—"}
        </td>
      </tr>`).join("");
  } catch (e) {
    console.error("[DASHBOARD] Error reservas:", e.message);
    tbody.innerHTML = `<tr><td colspan="10" style="color:var(--red);padding:16px">Error: ${e.message}</td></tr>`;
  }
}

async function cargarTablaSemana() {
  const tbody = document.getElementById("tbody-semana");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px"><div class="spinner" style="margin:auto"></div></td></tr>`;

  console.log("[DASHBOARD] Cargando próximos días");
  try {
    const dias = await apiFetch("/dashboard/proximos-dias?dias=7");
    const diasES = { Monday:"Lunes", Tuesday:"Martes", Wednesday:"Miércoles",
                     Thursday:"Jueves", Friday:"Viernes", Saturday:"Sábado", Sunday:"Domingo" };

    tbody.innerHTML = dias.map(d => `
      <tr>
        <td>${d.fecha}</td>
        <td>${diasES[d.dia_semana] || d.dia_semana}</td>
        <td>${d.total}</td>
        <td><strong style="color:var(--green)">${d.libres}</strong></td>
        <td>${d.pagados}</td>
        <td>${d.pendientes}</td>
        <td>
          <div class="ocupacion-bar">
            <div class="ocupacion-bg">
              <div class="ocupacion-fill" style="width:${d.ocupacion_pct}%"></div>
            </div>
            <span style="font-size:.8rem;color:var(--muted)">${d.ocupacion_pct}%</span>
          </div>
        </td>
      </tr>`).join("");
  } catch (e) {
    console.error("[DASHBOARD] Error semana:", e.message);
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--red);padding:16px">Error: ${e.message}</td></tr>`;
  }
}

async function cargarPendientes() {
  const c = document.getElementById("lista-pendientes");
  c.innerHTML = `<div style="text-align:center;padding:40px"><div class="spinner"></div></div>`;
  console.log("[DASHBOARD] Cargando pendientes...");

  try {
    const reservas = await apiFetch("/dashboard/reservas?estado=pendiente");
    console.log(`[DASHBOARD] ${reservas.length} pendientes`);

    if (!reservas.length) {
      c.innerHTML = `<div class="login-prompt"><div class="icon">✅</div>
        <p>No hay reservas pendientes de pago. ¡Todo al día!</p></div>`;
      return;
    }

    c.innerHTML = reservas.map(r => `
      <div class="pendiente-card">
        <div class="pendiente-hora">
          ${r.hora_inicio}
          <small>${r.hora_fin}</small>
        </div>
        <div class="pendiente-info">
          <div class="pendiente-cliente">${r.cliente}</div>
          <div class="pendiente-detalle">📧 ${r.email} · 📱 ${r.telefono}</div>
          <div class="pendiente-detalle">📅 ${r.fecha} · ${r.tipo_pago === 'canje' ? '⭐ Canje' : '💳 MP'}</div>
          <div class="pendiente-reserva-id">Reserva #${r.reserva_id} — creada ${r.reservado_el}</div>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn-verificar" id="btn-ver-${r.reserva_id}"
            onclick="verificarPagoDashboard(${r.reserva_id}, this)">
            🔍 Verificar pago
          </button>
          <button class="btn-verificar" style="background:var(--red);color:#fff;border:1px solid var(--red)"
            onclick="cancelarReservaDashboard(${r.reserva_id}, this)">
            ✕ Cancelar
          </button>
        </div>
      </div>`).join("");
  } catch (e) {
    console.error("[DASHBOARD] Error pendientes:", e.message);
    c.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
  }
}

async function verificarPagoDashboard(reservaId, btn) {
  console.log(`[DASHBOARD] Verificando pago reserva #${reservaId}`);
  const original = btn.textContent;
  btn.disabled    = true;
  btn.textContent = "Verificando...";

  try {
    const data = await apiFetch(`/pagos/verificar/${reservaId}`);
    console.log(`[DASHBOARD-VERIFICAR] Resultado:`, data);

    if (data.estado_pago === "aprobado") {
      mostrarToast(`✅ Reserva #${reservaId} — Pago confirmado`, "success");
      // Recargar dashboard completo
      cargarDashboard();
      cargarPendientes();
    } else if (data.estado_pago === "rechazado") {
      mostrarToast(`❌ Reserva #${reservaId} — Pago rechazado, turno liberado`, "error");
      cargarDashboard();
      cargarPendientes();
    } else {
      mostrarToast(data.mensaje || "Pago todavía pendiente en MP.", "info");
      btn.disabled    = false;
      btn.textContent = original;
    }
  } catch (e) {
    console.error("[DASHBOARD-VERIFICAR] Error:", e.message);
    mostrarToast(e.message, "error");
    btn.disabled    = false;
    btn.textContent = original;
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────
function abrirModalAuth() {
  document.getElementById("modal-auth").classList.add("open");
  cambiarAuthTab("login");
}
function cerrarModalAuth() {
  document.getElementById("modal-auth").classList.remove("open");
}
function cambiarAuthTab(tab) {
  const esLogin = tab === "login";
  document.getElementById("auth-form-login").style.display    = esLogin ? "block" : "none";
  document.getElementById("auth-form-registro").style.display  = esLogin ? "none"  : "block";
  document.getElementById("auth-tab-login").classList.toggle("active", esLogin);
  document.getElementById("auth-tab-registro").classList.toggle("active", !esLogin);
  document.getElementById("auth-titulo").textContent = esLogin ? "Iniciar sesión" : "Crear cuenta";
}

async function hacerLogin() {
  const email = document.getElementById("login-email").value.trim();
  const pass  = document.getElementById("login-password").value;
  if (!email || !pass) { mostrarToast("Completá email y contraseña", "error"); return; }

  const btn = document.getElementById("btn-login");
  btn.disabled = true; btn.textContent = "Ingresando...";
  console.log(`[AUTH] Login: ${email}`);
  try {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password: pass }),
    });
    _guardarSesion(data);
    cerrarModalAuth();
    mostrarToast(`¡Bienvenido, ${data.usuario.nombre.split(" ")[0]}!`, "success");
    renderizarSegunRol();

    // Si no es dueño, recargar turnos con el usuario ya cargado
    if (!esDuenio()) {
      await cargarCanchas();
      await cargarTurnos();
    }
  } catch (e) {
    console.error("[AUTH] Login error:", e.message);
    mostrarToast(e.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Ingresar";
  }
}

async function hacerRegistro() {
  const nombre = document.getElementById("reg-nombre").value.trim();
  const email  = document.getElementById("reg-email").value.trim();
  const pass   = document.getElementById("reg-password").value;
  if (!nombre || !email || !pass) { mostrarToast("Completá todos los campos", "error"); return; }
  if (pass.length < 6) { mostrarToast("Contraseña muy corta (mín. 6)", "error"); return; }

  const btn = document.getElementById("btn-registro");
  btn.disabled = true; btn.textContent = "Creando...";
  console.log(`[AUTH] Registro: ${email}`);
  try {
    const data = await apiFetch("/auth/registro", {
      method: "POST",
      body: JSON.stringify({ nombre, email, password: pass }),
    });
    _guardarSesion(data);
    cerrarModalAuth();
    mostrarToast(`¡Bienvenido, ${data.usuario.nombre.split(" ")[0]}!`, "success");
    renderizarSegunRol();
  } catch (e) {
    console.error("[AUTH] Registro error:", e.message);
    mostrarToast(e.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Crear cuenta";
  }
}

function _guardarSesion(data) {
  state.token   = data.access_token;
  state.usuario = data.usuario;
  localStorage.setItem("canchaYaToken",   data.access_token);
  localStorage.setItem("canchaYaUsuario", JSON.stringify(data.usuario));
  console.log(`[AUTH] Sesión guardada: ${data.usuario.email} (${data.usuario.rol})`);
}

function _limpiarSesion() {
  state.token   = null;
  state.usuario = null;
  localStorage.removeItem("canchaYaToken");
  localStorage.removeItem("canchaYaUsuario");
}

function cerrarSesion() {
  console.log(`[AUTH] Cerrando sesión de ${state.usuario?.email}`);
  _limpiarSesion();
  // Volver a la vista de comprador anónimo
  document.getElementById("vista-comprador").style.display = "block";
  document.getElementById("vista-duenio").style.display    = "none";
  actualizarHeaderNav();
  // Resetear tabs comprador al primero
  document.querySelectorAll(".vista-comp").forEach(v => v.classList.remove("active"));
  document.getElementById("comp-turnos").classList.add("active");
  cargarTurnos();
  mostrarToast("Sesión cerrada", "info");
}

// ── Toast ─────────────────────────────────────────────────────────────────
function mostrarToast(msg, tipo = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className   = `show ${tipo}`;
  console.log(`[TOAST][${tipo.toUpperCase()}] ${msg}`);
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => { t.className = ""; }, 4500);
}

// ── Formato helpers ───────────────────────────────────────────────────────
function formatTipo(tipo) {
  return { futbol_5: "Fútbol 5", futbol_7: "Fútbol 7" }[tipo] || tipo;
}
function formatEstado(e) {
  return { aprobado: "Pagado", pendiente: "Pendiente", rechazado: "Rechazado" }[e] || e;
}
function formatFecha(s) {
  const [y,m,d] = s.split("-").map(Number);
  const dias  = ["Dom","Lun","Mar","Mié","Jue","Vie","Sáb"];
  const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
  const f = new Date(y, m-1, d);
  return `${dias[f.getDay()]} ${d} ${meses[m-1]}`;
}
function formatPrecio(n) {
  return new Intl.NumberFormat("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  }).format(n);
}
