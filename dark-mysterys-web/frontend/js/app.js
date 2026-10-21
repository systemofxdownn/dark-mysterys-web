/* ==========================================================================
   Dark Mystery's — Aplicación SPA (router + vistas)
   Estética: fantasía oscura / dark academia.
   ========================================================================== */
(function () {
  "use strict";

  const api = window.DM.api;
  const store = window.DM.store;

  /* ======================================================================
     1. Utilidades
     ====================================================================== */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function num(n) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString("es-AR");
  }
  function lun(n) { return num(n) + " ₤"; }
  function pts(n) { return num(n) + " pts"; }

  function currentUser() { return (store.user && store.user.user) || null; }
  function permissions() { return (store.user && store.user.permissions) || []; }
  function hasPerm(p) { return permissions().includes(p); }
  function hasAny(...ps) { return ps.some((p) => hasPerm(p)); }
  function userTz() { const u = currentUser(); return (u && u.timezone) || "America/Argentina/Buenos_Aires"; }

  function parseDT(iso) {
    if (!iso) return null;
    // El backend almacena en UTC (naive). Tratamos como UTC.
    let s = String(iso);
    if (!/[zZ]|[+\-]\d\d:?\d\d$/.test(s)) s += "Z";
    const d = new Date(s);
    return isNaN(d) ? null : d;
  }
  function fmtDate(iso) {
    const d = parseDT(iso);
    if (!d) return "—";
    return new Intl.DateTimeFormat("es-AR", { timeZone: userTz(), day: "2-digit", month: "short", year: "numeric" }).format(d);
  }
  function fmtDateTime(iso) {
    const d = parseDT(iso);
    if (!d) return "—";
    return new Intl.DateTimeFormat("es-AR", { timeZone: userTz(), day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
  }
  function fmtTime(iso) {
    const d = parseDT(iso);
    if (!d) return "—";
    return new Intl.DateTimeFormat("es-AR", { timeZone: userTz(), hour: "2-digit", minute: "2-digit" }).format(d);
  }
  function tzLabel() {
    try { return new Intl.DateTimeFormat("es-AR", { timeZone: userTz(), timeZoneName: "short" }).format(new Date()).split(" ").pop(); }
    catch { return ""; }
  }

  function initials(name) {
    if (!name) return "?";
    return name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  }
  function uid() {
    return "k-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
  }

  /* ======================================================================
     2. Iconos (SVG inline)
     ====================================================================== */
  const ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    trophy: '<path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0z"/><path d="M7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3"/>',
    calendar: '<rect x="3" y="4.5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v3M16 3v3"/>',
    wallet: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M16 14h2"/>',
    users: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 6.2a3 3 0 0 1 0 5.6M21 20a6 6 0 0 0-4-5.6"/>',
    check: '<path d="M4 12.5 9 17.5 20 6.5"/>',
    bag: '<path d="M6 8h12l1 12H5z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    receipt: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 14.6a1.6 1.6 0 0 0-1.5-1H1a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 3 8a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 8 3a1.6 1.6 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1A1.6 1.6 0 0 0 14.6 3a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.6 1.6 0 0 0 21 8a1.6 1.6 0 0 0 1.5 1H23a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    rotate: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    star: '<path d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6L3.3 9.3l6.1-.7z"/>',
    flag: '<path d="M5 21V4M5 5h11l-2 3 2 3H5"/>',
    award: '<circle cx="12" cy="9" r="5"/><path d="M8.5 13 7 22l5-3 5 3-1.5-9"/>',
    message: '<path d="M4 5h16v11H8l-4 4z"/>',
    download: '<path d="M12 3v12M7 11l5 5 5-5"/><path d="M4 20h16"/>',
    shield: '<path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z"/>',
    bell: '<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    logout: '<path d="M15 4h4v16h-4M10 12H3M7 8l-4 4 4 4"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    edit: '<path d="M4 20h4L20 8l-4-4L4 16z"/><path d="M14 6l4 4"/>',
    trash: '<path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2 5.5L20 14"/><path d="M20 20v-6h-6"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 3l3 3M14 6l3 3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
    coins: '<ellipse cx="9" cy="7" rx="6" ry="3"/><path d="M3 7v5c0 1.7 2.7 3 6 3s6-1.3 6-3V7"/><path d="M15 12v5c0 1.7-2.7 3-6 3s-6-1.3-6-3"/>',
    sparkles: '<path d="M12 3v6M12 15v6M3 12h6M15 12h6"/><path d="m6 6 3 3M15 15l3 3M18 6l-3 3M9 15l-3 3"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v5M12 18h.01"/>',
    chart: '<path d="M4 20V4M4 20h16"/><path d="M8 16v-5M12 16V8M16 16v-3"/>',
    crown: '<path d="M4 18h16l-1-9-4 3-3-5-3 5-4-3z"/>',
    book: '<path d="M5 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H5z"/><path d="M19 4h-3a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h4z"/>',
    send: '<path d="M4 12 20 4l-7 16-2-6z"/>',
    filter: '<path d="M3 5h18l-7 8v6l-4-2v-4z"/>',
  };
  function icon(name, cls = "ic") {
    const p = ICONS[name] || ICONS.info;
    return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;
  }

  /* ======================================================================
     3. Toasts y Modales
     ====================================================================== */
  function toast(type, title, msg = "") {
    let stack = $(".toast-stack");
    if (!stack) { stack = document.createElement("div"); stack.className = "toast-stack"; document.body.appendChild(stack); }
    const el = document.createElement("div");
    el.className = "toast " + (type === "error" ? "err" : type);
    el.innerHTML = `<div style="flex:1"><div class="t-title">${esc(title)}</div>${msg ? `<div class="t-msg">${esc(msg)}</div>` : ""}</div>`;
    stack.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(8px)"; el.style.transition = ".25s"; setTimeout(() => el.remove(), 260); }, 4200);
  }
  const ok = (t, m) => toast("ok", t, m);
  const err = (t, m) => toast("error", t, m);
  const info = (t, m) => toast("info", t, m);

  function openModal({ title, body, footer, wide }) {
    closeModal();
    const ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.innerHTML = `
      <div class="modal ${wide ? "wide" : ""}">
        <div class="modal-head"><h3>${esc(title || "")}</h3><button class="btn btn-ghost btn-sm" data-close>${icon("x")}</button></div>
        <div class="modal-body">${body || ""}</div>
        ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
      </div>`;
    ov.addEventListener("click", (e) => { if (e.target === ov) closeModal(); });
    ov.querySelector("[data-close]").addEventListener("click", closeModal);
    document.body.appendChild(ov);
    return ov;
  }
  function closeModal() { const m = $(".modal-overlay"); if (m) m.remove(); }

  function confirmDialog(title, message, confirmLabel = "Confirmar", danger = false) {
    return new Promise((resolve) => {
      const ov = openModal({
        title,
        body: `<p class="muted">${esc(message)}</p>`,
        footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-ok>${esc(confirmLabel)}</button>`,
      });
      ov.querySelector("[data-cancel]").addEventListener("click", () => { closeModal(); resolve(false); });
      ov.querySelector("[data-ok]").addEventListener("click", () => { closeModal(); resolve(true); });
    });
  }

  /* ======================================================================
     4. Caché de metadatos
     ====================================================================== */
  const cache = { houses: null, roles: null, timezones: null };
  async function getHouses() { if (!cache.houses) cache.houses = await api.get("/meta/houses"); return cache.houses; }
  async function getRoles() { if (!cache.roles) cache.roles = await api.get("/meta/roles"); return cache.roles; }
  async function getTimezones() { if (!cache.timezones) cache.timezones = await api.get("/meta/timezones"); return cache.timezones; }
  function houseByCode(code) { return (cache.houses || []).find((h) => h.code === code) || null; }
  function houseById(id) { return (cache.houses || []).find((h) => h.id === id) || null; }

  function houseDot(house) {
    const hex = (house && house.heart_hex) || "#9CA3AF";
    const code = (house && house.code) || "";
    return `<span class="house-tag house-${code}"><span class="dot" style="background:${hex};color:${hex}"></span>${esc(house ? house.name : "—")}</span>`;
  }
  function statusBadge(status) {
    const map = {
      ACTIVA: ["ok", "Activa"], PENDIENTE_DE_ACTIVACION: ["warn", "Pendiente"],
      CONGELADA: ["info", "Congelada"], DADA_DE_BAJA: ["danger", "Dada de baja"],
    };
    const [c, l] = map[status] || ["muted", status];
    return `<span class="badge ${c}">${esc(l)}</span>`;
  }
  function roleLabel(role) {
    const r = (cache.roles || []).find((x) => x.code === role);
    return r ? r.name : role;
  }

  /* ======================================================================
     5. Layout (sidebar + topbar)
     ====================================================================== */
  const NAV = [
    { group: "Principal", items: [
      { label: "Panel", icon: "home", hash: "#/" },
      { label: "Copa", icon: "trophy", hash: "#/scoreboard", perm: ["points:view_all"] },
      { label: "Calendario", icon: "calendar", hash: "#/calendar" },
    ]},
    { group: "Banco de Lunarias", items: [
      { label: "Mi billetera", icon: "wallet", hash: "#/bank" },
      { label: "Cuentas", icon: "coins", hash: "#/bank/accounts", perm: ["wallet:view_all"] },
      { label: "Aprobaciones", icon: "check", hash: "#/bank/approvals", perm: ["wallet:approve_large"] },
    ]},
    { group: "Tienda", items: [
      { label: "Tienda", icon: "bag", hash: "#/shop" },
      { label: "Mis compras", icon: "receipt", hash: "#/shop/purchases" },
      { label: "Catálogo", icon: "settings", hash: "#/shop/manage", perm: ["shop:manage"] },
      { label: "Activaciones", icon: "zap", hash: "#/shop/activations", perm: ["shop:activations_manage"] },
      { label: "Reembolsos", icon: "rotate", hash: "#/shop/refunds", perm: ["shop:refund_approve"] },
    ]},
    { group: "Competencia", items: [
      { label: "Puntos", icon: "star", hash: "#/points", perm: ["points:view_all"] },
      { label: "Eventos", icon: "flag", hash: "#/events" },
      { label: "Partis", icon: "award", hash: "#/partis" },
    ]},
    { group: "Administración", items: [
      { label: "Usuarios", icon: "users", hash: "#/users", perm: ["users:view_all", "users:view_own_house"] },
      { label: "Reclamaciones", icon: "message", hash: "#/complaints" },
      { label: "Reportes", icon: "download", hash: "#/reports", perm: ["stats:view", "reports:export_own_house"] },
      { label: "Auditoría", icon: "shield", hash: "#/audit", perm: ["audit:view"] },
      { label: "Configuración", icon: "settings", hash: "#/config", perm: ["config:manage"] },
    ]},
  ];

  function brandMark() {
    return `<span class="brand-mark"><svg viewBox="0 0 24 24" fill="none" stroke="#e6c766" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.5 4.5 6v5.5c0 5 3.2 8.6 7.5 10.5 4.3-1.9 7.5-5.5 7.5-10.5V6z"/><path d="M9.5 12.5c1.6-1.6 3.4-1.6 5 0"/><circle cx="10.4" cy="10.3" r=".9" fill="#e6c766"/><circle cx="13.6" cy="10.3" r=".9" fill="#e6c766"/></svg></span>`;
  }

  function renderSidebar() {
    const u = currentUser();
    const groups = NAV.map((g) => {
      const items = g.items.filter((it) => !it.perm || hasAny(...it.perm));
      if (!items.length) return "";
      return `<div class="nav-group-label">${esc(g.group)}</div>` + items.map((it) => `
        <a class="nav-item" href="${it.hash}" data-nav="${it.hash}">${icon(it.icon)}<span>${esc(it.label)}</span></a>`).join("");
    }).join("");
    return `
      <aside class="sidebar">
        <div class="brand">${brandMark()}<div class="brand-name">Dark Mystery's<small>Casa Nocturna</small></div></div>
        <nav class="grow">${groups}</nav>
        <div class="sidebar-foot">
          <div class="row" style="gap:10px;margin-bottom:12px">
            <div class="avatar">${esc(initials(u && u.display_name))}</div>
            <div style="min-width:0">
              <div style="color:var(--text-strong);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(u ? u.display_name : "")}</div>
              <div class="tiny muted mono">${esc(u ? u.identifier : "")} · ${esc(roleLabel(u && u.role))}</div>
            </div>
          </div>
          <div class="powered">POWERED BY: <b>ZETA LESTRANGE</b></div>
        </div>
      </aside>`;
  }

  function renderTopbar(title) {
    return `
      <header class="topbar">
        <button class="btn btn-ghost btn-sm menu-toggle" data-menu>${icon("menu")}</button>
        <div class="page-title">${esc(title || "")}</div>
        <div class="spacer"></div>
        <button class="btn btn-ghost btn-sm" data-notif title="Notificaciones" style="position:relative">${icon("bell")}<span class="badge-dot hidden" data-notif-dot style="position:absolute;top:4px;right:4px"></span></button>
        <a class="btn btn-ghost btn-sm" href="#/profile" title="Perfil">${icon("user")}</a>
        <button class="btn btn-ghost btn-sm" data-logout title="Salir">${icon("logout")}</button>
      </header>`;
  }

  function bindShell() {
    $$("[data-nav]").forEach((a) => a.addEventListener("click", () => closeNav()));
    const mt = $("[data-menu]"); if (mt) mt.addEventListener("click", toggleNav);
    const lo = $("[data-logout]"); if (lo) lo.addEventListener("click", doLogout);
    const nt = $("[data-notif]"); if (nt) nt.addEventListener("click", openNotifications);
    refreshNotifCount();
  }
  function toggleNav() { const s = $(".app-shell"); s.classList.toggle("nav-open"); let sc = $(".scrim"); if (s.classList.contains("nav-open") && !sc) { sc = document.createElement("div"); sc.className = "scrim"; sc.addEventListener("click", closeNav); document.body.appendChild(sc); } else if (!s.classList.contains("nav-open") && sc) sc.remove(); }
  function closeNav() { const s = $(".app-shell"); if (s) s.classList.remove("nav-open"); const sc = $(".scrim"); if (sc) sc.remove(); }

  async function doLogout() {
    if (await confirmDialog("Cerrar sesión", "¿Deseás salir de Dark Mystery's?")) {
      api.logout(); cache.houses = null; cache.roles = null; cache.timezones = null;
      location.hash = "#/login"; render();
    }
  }

  async function refreshNotifCount() {
    try {
      const c = await api.get("/notifications/count");
      const n = c.count ?? c.unread ?? c;
      const dot = $("[data-notif-dot]");
      if (dot) dot.classList.toggle("hidden", !n);
    } catch { /* ignore */ }
  }

  async function openNotifications() {
    const list = await api.get("/notifications").catch(() => []);
    const body = list.length ? list.map((n) => `
      <div class="ledger-row" style="grid-template-columns:1fr">
        <div><div style="color:var(--text-strong)">${esc(n.title || n.subject || "Notificación")}</div>
        <div class="small muted">${esc(n.body || n.message || "")}</div>
        <div class="tiny faint">${fmtDateTime(n.created_at)}</div></div>
      </div>`).join("") : `<div class="empty">${icon("bell")}<h3>Sin notificaciones</h3></div>`;
    const ov = openModal({
      title: "Notificaciones",
      body: `<div>${body}</div>`,
      footer: `<button class="btn btn-ghost" data-readall>Marcar todas como leídas</button><button class="btn btn-primary" data-close2>Cerrar</button>`,
    });
    ov.querySelector("[data-close2]").addEventListener("click", closeModal);
    ov.querySelector("[data-readall]").addEventListener("click", async () => {
      await api.post("/notifications/read-all").catch(() => {});
      closeModal(); refreshNotifCount(); info("Listo", "Notificaciones marcadas como leídas.");
    });
  }

  /* ======================================================================
     6. Router
     ====================================================================== */
  function parseHash() {
    const raw = location.hash.replace(/^#/, "") || "/";
    const [path, qs] = raw.split("?");
    const query = {};
    if (qs) new URLSearchParams(qs).forEach((v, k) => (query[k] = v));
    return { path: path || "/", query };
  }

  const ROUTES = {
    "/login": viewLogin,
    "/first-access": viewFirstAccess,
    "/forgot-password": viewForgot,
    "/reset-password": viewReset,
    "/verify-email": viewVerify,
    "/": viewDashboard,
    "/scoreboard": viewScoreboard,
    "/calendar": viewCalendar,
    "/bank": viewBank,
    "/bank/accounts": viewAccounts,
    "/bank/approvals": viewApprovals,
    "/shop": viewShop,
    "/shop/purchases": viewPurchases,
    "/shop/manage": viewShopManage,
    "/shop/activations": viewActivations,
    "/shop/refunds": viewRefunds,
    "/points": viewPoints,
    "/events": viewEvents,
    "/partis": viewPartis,
    "/users": viewUsers,
    "/complaints": viewComplaints,
    "/reports": viewReports,
    "/audit": viewAudit,
    "/config": viewConfig,
    "/profile": viewProfile,
  };

  const AUTH_ROUTES = ["/login", "/first-access", "/forgot-password", "/reset-password", "/verify-email"];

  async function render() {
    const { path, query } = parseHash();
    const isAuthRoute = AUTH_ROUTES.includes(path);
    const authed = !!store.token && !!store.user;

    // Guardas
    if (!isAuthRoute && !authed) { location.hash = "#/login"; return; }
    if (isAuthRoute && authed && path === "/login") { location.hash = "#/"; return; }

    // Asegurar metadatos
    if (authed) { try { await Promise.all([getHouses(), getRoles()]); } catch { /* ignore */ } }

    const view = ROUTES[path] || viewNotFound;
    let result;
    try {
      result = await view(query);
    } catch (e) {
      result = { title: "Error", html: `<div class="banner danger">${icon("alert")}<div>${esc(e.detail || e.message || "Error al cargar la vista.")}</div></div>` };
    }
    if (!result) return;

    const root = $("#app");
    if (isAuthRoute) {
      root.innerHTML = `<div class="auth-wrap fade-in">${result.html}</div>`;
    } else {
      root.innerHTML = `<div class="app-shell">${renderSidebar()}<div class="main">${renderTopbar(result.title)}<div class="content fade-in">${result.html}</div></div></div>`;
      bindShell();
    }
    // Marcar nav activo
    $$("[data-nav]").forEach((a) => a.classList.toggle("active", a.getAttribute("data-nav") === "#" + path || (path === "/" && a.getAttribute("data-nav") === "#/")));
    if (result.after) { try { await result.after(); } catch (e) { console.error(e); } }
  }

  window.addEventListener("hashchange", render);

  /* ======================================================================
     7. Vistas de autenticación
     ====================================================================== */
  function authHeader(title, sub) {
    return `${brandMark()}<h1>${esc(title)}</h1><div class="sub">${esc(sub || "")}</div>`;
  }

  function viewLogin() {
    return {
      html: `<div class="auth-card">
        ${authHeader("Dark Mystery's", "Ingresá al círculo nocturno")}
        <form data-form="login">
          <div class="field"><label>Identificador <span class="req">*</span></label>
            <input name="identifier" placeholder="Ej.: DU01" autocomplete="username" required></div>
          <div class="field"><label>Contraseña <span class="req">*</span></label>
            <input name="password" type="password" placeholder="••••••••" autocomplete="current-password" required></div>
          <button class="btn btn-primary btn-block mt-1" type="submit">Ingresar</button>
        </form>
        <div class="divider"></div>
        <div class="center-text small"><a href="#/forgot-password">¿Olvidaste tu contraseña?</a></div>
        <div class="center-text tiny faint mt-2">El acceso es por invitación. Si no tenés cuenta, contactá a Dirección.</div>
        <div class="center-text powered mt-3" style="text-align:center">POWERED BY: <b>ZETA LESTRANGE</b></div>
      </div>`,
      after() {
        $("[data-form=login]").addEventListener("submit", async (e) => {
          e.preventDefault();
          const f = e.target;
          const btn = f.querySelector("button"); btn.disabled = true;
          try {
            await api.login(f.identifier.value.trim().toUpperCase(), f.password.value);
            await api.me();
            ok("Bienvenido/a", "Sesión iniciada.");
            location.hash = "#/";
            render();
          } catch (ex) {
            err("No se pudo ingresar", ex.detail || ex.message);
            btn.disabled = false;
          }
        });
      },
    };
  }

  function viewFirstAccess(query) {
    const token = query.token || "";
    return {
      html: `<div class="auth-card">
        ${authHeader("Primer acceso", "Activá tu cuenta y definí tu contraseña")}
        ${token ? "" : `<div class="banner warn mb-2">${icon("alert")}<div>Falta el token de invitación. Abrí el enlace que recibiste por correo.</div></div>`}
        <form data-form="first">
          <div class="field"><label>Token de invitación <span class="req">*</span></label>
            <input name="token" value="${esc(token)}" required></div>
          <div class="field"><label>Nombre visible</label>
            <input name="display_name" placeholder="Opcional"></div>
          <div class="field"><label>Correo electrónico <span class="req">*</span></label>
            <input name="email" type="email" placeholder="tu@correo.com" required>
            <div class="help">Obligatorio y verificado. Se usa para recuperar tu cuenta.</div></div>
          <div class="field"><label>Nueva contraseña <span class="req">*</span></label>
            <input name="password" type="password" placeholder="Mínimo 8 caracteres" required></div>
          <div class="field"><label>Zona horaria</label>
            <select name="timezone" data-tz></select></div>
          <button class="btn btn-primary btn-block mt-1" type="submit">Activar cuenta</button>
        </form>
        <div class="center-text small mt-2"><a href="#/login">Volver al ingreso</a></div>
      </div>`,
      async after() {
        await fillTimezoneSelect($("[data-tz]"));
        $("[data-form=first]").addEventListener("submit", async (e) => {
          e.preventDefault();
          const f = e.target; const btn = f.querySelector("button"); btn.disabled = true;
          try {
            await api.post("/auth/first-access", {
              token: f.token.value.trim(), password: f.password.value, email: f.email.value.trim(),
              display_name: f.display_name.value.trim() || null, timezone: f.timezone.value || null,
            }, { noAuth: true, noRedirect: true });
            ok("Cuenta activada", "Ya podés iniciar sesión.");
            location.hash = "#/login";
          } catch (ex) {
            err("No se pudo activar", ex.detail || ex.message); btn.disabled = false;
          }
        });
      },
    };
  }

  function viewForgot() {
    return {
      html: `<div class="auth-card">
        ${authHeader("Recuperar contraseña", "Te enviaremos un enlace de restablecimiento")}
        <form data-form="forgot">
          <div class="field"><label>Correo electrónico <span class="req">*</span></label>
            <input name="email" type="email" placeholder="tu@correo.com" required></div>
          <button class="btn btn-primary btn-block mt-1" type="submit">Enviar enlace</button>
        </form>
        <div class="center-text small mt-2"><a href="#/login">Volver al ingreso</a></div>
      </div>`,
      after() {
        $("[data-form=forgot]").addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            await api.post("/auth/forgot-password", { email: e.target.email.value.trim() }, { noAuth: true, noRedirect: true });
            ok("Enviado", "Si el correo existe, recibirás un enlace.");
            location.hash = "#/login";
          } catch (ex) { err("Error", ex.detail || ex.message); }
        });
      },
    };
  }

  function viewReset(query) {
    const token = query.token || "";
    return {
      html: `<div class="auth-card">
        ${authHeader("Nueva contraseña", "Definí una contraseña segura")}
        <form data-form="reset">
          <div class="field"><label>Token <span class="req">*</span></label><input name="token" value="${esc(token)}" required></div>
          <div class="field"><label>Nueva contraseña <span class="req">*</span></label><input name="new_password" type="password" required></div>
          <button class="btn btn-primary btn-block mt-1" type="submit">Restablecer</button>
        </form>
        <div class="center-text small mt-2"><a href="#/login">Volver al ingreso</a></div>
      </div>`,
      after() {
        $("[data-form=reset]").addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            await api.post("/auth/reset-password", { token: e.target.token.value.trim(), new_password: e.target.new_password.value }, { noAuth: true, noRedirect: true });
            ok("Contraseña actualizada", "Ya podés ingresar.");
            location.hash = "#/login";
          } catch (ex) { err("Error", ex.detail || ex.message); }
        });
      },
    };
  }

  function viewVerify(query) {
    const token = query.token || "";
    return {
      html: `<div class="auth-card">
        ${authHeader("Verificar correo", "Confirmá tu dirección de correo")}
        ${token ? `<div class="banner info mb-2">${icon("mail")}<div>Presioná el botón para verificar tu correo.</div></div>` : `<div class="banner warn mb-2">${icon("alert")}<div>Falta el token de verificación.</div></div>`}
        <button class="btn btn-primary btn-block" data-verify ${token ? "" : "disabled"}>Verificar correo</button>
        <div class="center-text small mt-2"><a href="#/login">Ir al ingreso</a></div>
      </div>`,
      after() {
        const b = $("[data-verify]");
        b.addEventListener("click", async () => {
          try { await api.post("/auth/verify-email", { token }, { noAuth: true, noRedirect: true }); ok("Verificado", "Tu correo fue verificado."); location.hash = "#/login"; }
          catch (ex) { err("Error", ex.detail || ex.message); }
        });
      },
    };
  }

  async function fillTimezoneSelect(sel, selected) {
    if (!sel) return;
    try {
      const tz = await getTimezones();
      sel.innerHTML = (tz.groups || []).map((g) =>
        `<optgroup label="${esc(g.group)}">${g.options.map((o) => `<option value="${esc(o.value)}" ${o.value === (selected || tz.default) ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</optgroup>`
      ).join("");
    } catch { sel.innerHTML = `<option>America/Argentina/Buenos_Aires</option>`; }
  }

  /* ======================================================================
     8. Panel principal (dashboard)
     ====================================================================== */
  async function viewDashboard() {
    const u = currentUser();
    const [wallet, scoreboard, limits, notifs] = await Promise.all([
      api.get("/wallet/me").catch(() => ({ balance: 0, debt: 0 })),
      api.get("/points/scoreboard").catch(() => ({ houses: [] })),
      api.get("/shop/limits").catch(() => null),
      api.get("/notifications").catch(() => []),
    ]);
    const house = u.house;
    const ranked = [...(scoreboard.houses || [])].sort((a, b) => b.points - a.points);
    const myRank = ranked.findIndex((h) => h.code === (house && house.code)) + 1;

    const quick = [];
    if (hasPerm("shop:buy")) quick.push({ label: "Ir a la tienda", icon: "bag", hash: "#/shop" });
    if (hasPerm("wallet:transfer")) quick.push({ label: "Transferir Lunarias", icon: "send", hash: "#/bank" });
    if (hasPerm("points:view_all")) quick.push({ label: "Ver la Copa", icon: "trophy", hash: "#/scoreboard" });
    if (hasPerm("users:create")) quick.push({ label: "Crear cuenta", icon: "plus", hash: "#/users" });
    if (hasPerm("events:manage")) quick.push({ label: "Gestionar eventos", icon: "flag", hash: "#/events" });

    const html = `
      <div class="grid cols-4 mb-3">
        <div class="stat accent-gold">
          <div class="label">Billetera (Lunarias)</div>
          <div class="value">${lun(wallet.balance)}</div>
          <div class="hint">${wallet.debt > 0 ? `Deuda pendiente: ${lun(wallet.debt)}` : "Sin deudas"}</div>
        </div>
        <div class="stat">
          <div class="label">Mi Casa</div>
          <div class="value" style="font-size:22px;color:${esc((house && house.heart_hex) || "#e6c766")}">${esc(house ? house.name : "—")}</div>
          <div class="hint">${esc(u.identifier)} · ${esc(roleLabel(u.role))}</div>
        </div>
        <div class="stat">
          <div class="label">Posición en la Copa</div>
          <div class="value">${myRank > 0 ? "#" + myRank : "—"}</div>
          <div class="hint">${house && house.is_competing ? "Casa competidora" : "Casa Nocturna (institucional)"}</div>
        </div>
        <div class="stat">
          <div class="label">Tienda hoy</div>
          <div class="value" style="font-size:24px">${limits ? `${limits.purchases_today}/${limits.purchase_limit}` : "—"}</div>
          <div class="hint">Compras · Activaciones ${limits ? `${limits.activations_today}/${limits.activation_limit}` : "—"}</div>
        </div>
      </div>

      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><h3 class="card-title">${icon("trophy")} Tabla de la Copa</h3><a class="btn-link" href="#/scoreboard">Ver detalle</a></div>
          ${ranked.length ? ranked.map((h, i) => `
            <div class="ledger-row">
              <div class="row" style="gap:12px">
                <div class="avatar" style="background:${esc(h.heart_hex)}22;border-color:${esc(h.heart_hex)}55;color:${esc(h.heart_hex)}">${i + 1}</div>
                <div><div style="color:var(--text-strong);font-weight:600">${esc(h.name)}</div><div class="tiny faint">${esc(h.heart_color)}</div></div>
              </div>
              <div class="gold mono" style="font-size:18px">${num(h.points)}</div>
            </div>`).join("") : `<div class="empty">Sin datos aún</div>`}
        </div>

        <div class="card">
          <div class="card-head"><h3 class="card-title">${icon("sparkles")} Accesos rápidos</h3></div>
          <div class="grid cols-2" style="gap:10px">
            ${quick.map((q) => `<a class="btn" href="${q.hash}" style="justify-content:flex-start">${icon(q.icon)} ${esc(q.label)}</a>`).join("") || `<div class="muted">Sin accesos disponibles.</div>`}
          </div>
          <div class="divider"></div>
          <div class="card-title mb-1">${icon("bell")} Novedades</div>
          ${notifs.length ? notifs.slice(0, 4).map((n) => `<div class="ledger-row" style="grid-template-columns:1fr"><div><div style="color:var(--text-strong)">${esc(n.title || n.subject || "Aviso")}</div><div class="tiny faint">${fmtDateTime(n.created_at)}</div></div></div>`).join("") : `<div class="muted small">Sin novedades.</div>`}
        </div>
      </div>

      ${house ? `
      <div class="card mt-3" style="border-color:${esc(house.heart_hex)}44">
        <div class="row between wrap">
          <div class="row" style="gap:16px">
            <div class="emblem" style="width:56px;height:56px;border-radius:14px;display:grid;place-items:center;background:${esc(house.heart_hex)}18;border:1px solid ${esc(house.heart_hex)}55;color:${esc(house.heart_hex)}">${icon("crown", "")}</div>
            <div>
              <h2 style="margin:0;color:${esc(house.heart_hex)}">${esc(house.name)}</h2>
              <div class="small muted">${esc(house.virtues || "")}</div>
            </div>
          </div>
          <div class="right small muted">
            ${house.founder ? `<div>Fundador: <b class="gold">${esc(house.founder)}</b></div>` : ""}
            ${house.founded_year ? `<div>Fundada en <b class="gold">${esc(house.founded_year)}</b></div>` : ""}
            ${house.symbols ? `<div>Símbolos: ${esc(house.symbols)}</div>` : ""}
          </div>
        </div>
        <div class="divider"></div>
        <p class="serif" style="font-size:16px;color:var(--text)">${esc(house.identity || "")}</p>
      </div>` : ""}
    `;
    return { title: "Panel", html };
  }

  /* ======================================================================
     9. Copa / Marcador
     ====================================================================== */
  async function viewScoreboard() {
    const sb = await api.get("/points/scoreboard");
    const ranked = [...(sb.houses || [])].sort((a, b) => b.points - a.points);
    const podium = [ranked[1], ranked[0], ranked[2]]; // 2,1,3 para el podio visual
    const html = `
      <div class="card pad-lg mb-3">
        <div class="card-head"><h2 class="card-title">${icon("trophy")} Copa Dark Mystery's</h2><span class="badge gold">Temporada en curso</span></div>
        <div class="podium">
          ${podium.map((h, idx) => {
            if (!h) return "";
            const rank = idx === 1 ? 1 : idx === 0 ? 2 : 3;
            return `<div class="step p${rank}">
              <div class="bar" style="border-color:${esc(h.heart_hex)}55">
                <div class="rank" style="color:${esc(h.heart_hex)}">${rank}º</div>
                <div class="house-name">${esc(h.name)}</div>
                <div class="pts">${num(h.points)}</div>
              </div>
            </div>`;
          }).join("")}
        </div>
      </div>
      <div class="grid auto-320">
        ${ranked.map((h, i) => `
          <div class="house-card">
            <div class="glow" style="background:${esc(h.heart_hex)}"></div>
            <div class="row between">
              <div class="row" style="gap:12px">
                <div class="emblem" style="color:${esc(h.heart_hex)};border-color:${esc(h.heart_hex)}55">${icon("crown", "")}</div>
                <div><div class="card-title">${esc(h.name)}</div><div class="tiny faint">${esc(h.heart_color)}</div></div>
              </div>
              <div class="right"><div class="tiny faint">Puesto</div><div class="gold" style="font-family:var(--font-display);font-size:22px">#${i + 1}</div></div>
            </div>
            <div class="divider"></div>
            <div class="row between"><span class="muted">Puntos totales</span><span class="gold mono" style="font-size:20px">${num(h.points)}</span></div>
          </div>`).join("")}
      </div>
      <div class="card mt-3">
        <div class="card-head"><h3 class="card-title">${icon("info")} Reglas de puntaje</h3></div>
        <div class="grid cols-3">
          <div><div class="label small muted upper">Podio (dinámica)</div><div class="mono">1º ${num(6000)} · 2º ${num(5000)} · 3º ${num(4000)}</div><div class="tiny faint">Resto: ${num(1500)} c/u</div></div>
          <div><div class="label small muted upper">Reto grupal</div><div class="mono">${num(40000)} · ${num(30000)} · ${num(20000)}</div><div class="tiny faint">A la Casa</div></div>
          <div><div class="label small muted upper">Reto individual</div><div class="mono">${num(16000)}</div><div class="tiny faint">Compensación cancelación: ${num(7500)}</div></div>
        </div>
        <div class="banner info mt-2">${icon("info")}<div>Máximo <b>una persona por Casa</b> en el podio (las posiciones se desplazan a la siguiente Casa elegible). <b>Excepción:</b> si solo participan dos Casas, una puede ocupar dos lugares del podio.</div></div>
      </div>`;
    return { title: "Copa", html };
  }

  /* ======================================================================
     10. Banco
     ====================================================================== */
  async function viewBank() {
    const [wallet, txs, accounts] = await Promise.all([
      api.get("/wallet/me"),
      api.get("/wallet/transactions", { query: { limit: 40 } }),
      api.get("/wallet/accounts").catch(() => []),
    ]);
    const canDeposit = hasPerm("wallet:deposit");
    const html = `
      <div class="grid cols-3 mb-3">
        <div class="stat accent-gold"><div class="label">Saldo</div><div class="value">${lun(wallet.balance)}</div><div class="hint">Moneda: Lunarias ₤</div></div>
        <div class="stat"><div class="label">Deuda</div><div class="value" style="color:${wallet.debt > 0 ? "var(--danger)" : "inherit"}">${lun(wallet.debt)}</div><div class="hint">Las ganancias futuras la saldan</div></div>
        <div class="stat"><div class="label">Movimientos</div><div class="value">${num(txs.length)}</div><div class="hint">Últimos registros</div></div>
      </div>
      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><h3 class="card-title">${icon("send")} Transferir Lunarias</h3></div>
          <form data-form="transfer">
            <div class="field"><label>Identificador destino <span class="req">*</span></label>
              <input name="to_identifier" placeholder="Ej.: MC03" required>
              <div class="help">Escribí el identificador de la cuenta destino.</div></div>
            <div class="field"><label>Monto (₤) <span class="req">*</span></label><input name="amount" type="number" min="1" required></div>
            <div class="field"><label>Motivo</label><input name="reason" placeholder="Opcional"></div>
            <button class="btn btn-primary btn-block" type="submit">Transferir</button>
          </form>
        </div>
        <div class="card">
          <div class="card-head"><h3 class="card-title">${icon("coins")} Historial personal</h3></div>
          ${txs.length ? `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Tipo</th><th>Motivo</th><th class="num">Monto</th></tr></thead><tbody>
            ${txs.map((t) => `<tr><td class="small muted">${fmtDateTime(t.created_at || t.date)}</td><td><span class="badge muted">${esc(t.type || "")}</span></td><td class="small">${esc(t.reason || "—")}</td><td class="num ${t.amount < 0 ? "amount-neg" : "amount-pos"}">${t.amount > 0 ? "+" : ""}${num(t.amount)}</td></tr>`).join("")}
          </tbody></table></div>` : `<div class="empty">${icon("receipt")}<h3>Sin movimientos</h3><p class="small">Tus transferencias y depósitos aparecerán aquí.</p></div>`}
        </div>
      </div>
      ${canDeposit ? `
      <div class="card mt-3">
        <div class="card-head"><h3 class="card-title">${icon("plus")} Operaciones de Dirección / Banco</h3></div>
        <div class="row wrap">
          <button class="btn" data-op="deposit">${icon("coins")} Depositar</button>
          <button class="btn" data-op="adjust">${icon("settings")} Ajustar</button>
          <button class="btn" data-op="sanction">${icon("alert")} Penalizar</button>
          <a class="btn" href="#/bank/accounts">${icon("users")} Ver cuentas</a>
        </div>
      </div>` : ""}
    `;
    return {
      title: "Mi billetera",
      html,
      after() {
        const f = $("[data-form=transfer]");
        if (f) f.addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            await api.post("/wallet/transfer", {
              to_identifier: e.target.to_identifier.value.trim().toUpperCase(),
              amount: parseInt(e.target.amount.value, 10),
              reason: e.target.reason.value.trim() || null,
              idempotency_key: uid(),
            });
            ok("Transferencia realizada", "El saldo se actualizó.");
            render();
          } catch (ex) { err("No se pudo transferir", ex.detail || ex.message); }
        });
        $$("[data-op]").forEach((b) => b.addEventListener("click", () => bankOp(b.getAttribute("data-op"), accounts)));
      },
    };
  }

  async function bankOp(op, accounts) {
    const opts = (accounts || []).map((a) => `<option value="${a.user.id}">${esc(a.user.identifier)} — ${esc(a.user.display_name)} (${num(a.balance)})</option>`).join("");
    const titles = { deposit: "Depositar Lunarias", adjust: "Ajustar saldo", sanction: "Penalizar Lunarias" };
    const body = `
      <div class="field"><label>Cuenta destino <span class="req">*</span></label><select name="user_id">${opts}</select></div>
      <div class="field"><label>Monto (₤) <span class="req">*</span></label><input name="amount" type="number" min="1" value="1000" required>${op === "adjust" ? `<div class="help">Podés usar valores negativos para descontar.</div>` : ""}</div>
      <div class="field"><label>Motivo <span class="req">*</span></label><input name="reason" placeholder="Descripción" required></div>`;
    const ov = openModal({
      title: titles[op],
      body,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn ${op === "sanction" ? "btn-danger" : "btn-primary"}" data-do>Confirmar</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      const user_id = parseInt(ov.querySelector("[name=user_id]").value, 10);
      const amount = parseInt(ov.querySelector("[name=amount]").value, 10);
      const reason = ov.querySelector("[name=reason]").value.trim();
      if (!reason || !amount) return err("Datos incompletos", "Completá monto y motivo.");
      try {
        if (op === "deposit") await api.post("/wallet/deposit", { user_id, amount, reason, idempotency_key: uid() });
        else if (op === "adjust") await api.post("/wallet/adjust", { user_id, amount, reason, idempotency_key: uid() });
        else await api.post("/wallet/sanction", { target_user_id: user_id, resource: "LUNARIAS", amount: Math.abs(amount), reason });
        closeModal(); ok("Operación registrada", "El movimiento quedó asentado."); render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  async function viewAccounts() {
    const accounts = await api.get("/wallet/accounts");
    const html = `
      <div class="card mb-3">
        <div class="row between wrap">
          <h2 class="card-title">${icon("users")} Cuentas y saldos</h2>
          <div class="row"><input data-search placeholder="Buscar por nombre o identificador" style="min-width:260px"></div>
        </div>
      </div>
      <div class="table-wrap">
        <table><thead><tr><th>Identificador</th><th>Nombre</th><th>Casa</th><th>Rol</th><th class="num">Saldo</th><th class="num">Deuda</th></tr></thead>
        <tbody data-rows>
          ${accounts.map((a) => `<tr data-row data-text="${esc((a.user.display_name + " " + a.user.identifier).toLowerCase())}">
            <td class="mono gold">${esc(a.user.identifier)}</td>
            <td>${esc(a.user.display_name)}</td>
            <td class="small muted">${esc(a.user.house || "—")}</td>
            <td class="small">${esc(roleLabel(a.user.role))}</td>
            <td class="num ${a.balance < 0 ? "amount-neg" : ""}">${num(a.balance)}</td>
            <td class="num ${a.debt > 0 ? "amount-neg" : "muted"}">${num(a.debt)}</td>
          </tr>`).join("")}
        </tbody></table>
      </div>`;
    return {
      title: "Cuentas", html,
      after() {
        const s = $("[data-search]");
        s.addEventListener("input", () => {
          const q = s.value.toLowerCase();
          $$("[data-row]").forEach((r) => r.classList.toggle("hidden", !r.getAttribute("data-text").includes(q)));
        });
      },
    };
  }

  async function viewApprovals() {
    const list = await api.get("/wallet/approvals");
    const pending = list.filter((a) => a.status === "PENDIENTE");
    const html = `
      <div class="banner info mb-3">${icon("info")}<div>Ajustes grandes (≥ ${num(50000)} ₤) requieren una segunda aprobación de Dirección.</div></div>
      ${pending.length ? `<div class="grid auto-320">${pending.map((a) => `
        <div class="card">
          <div class="row between"><span class="badge warn">Pendiente</span><span class="mono gold">${lun(a.amount)}</span></div>
          <div class="divider"></div>
          <div class="small"><b>Solicitante:</b> #${a.requested_by}</div>
          <div class="small muted">${esc(a.reason || "")}</div>
          <div class="row mt-2"><button class="btn btn-ok btn-sm" data-ok="${a.id}">${icon("check")} Aprobar</button>
          <button class="btn btn-danger btn-sm" data-no="${a.id}">${icon("x")} Rechazar</button></div>
        </div>`).join("")}</div>` : `<div class="empty">${icon("check")}<h3>Sin aprobaciones pendientes</h3></div>`}`;
    return {
      title: "Aprobaciones", html,
      after() {
        $$("[data-ok]").forEach((b) => b.addEventListener("click", () => resolveApproval(b.getAttribute("data-ok"), true)));
        $$("[data-no]").forEach((b) => b.addEventListener("click", () => resolveApproval(b.getAttribute("data-no"), false)));
      },
    };
  }
  async function resolveApproval(id, approve) {
    try { await api.post(`/wallet/approvals/${id}`, null, { query: { approve } }); ok("Resuelto", approve ? "Ajuste aprobado." : "Ajuste rechazado."); render(); }
    catch (ex) { err("Error", ex.detail || ex.message); }
  }

  /* ======================================================================
     11. Tienda
     ====================================================================== */
  async function viewShop() {
    const [products, hours, limits, wallet] = await Promise.all([
      api.get("/shop/products"), api.get("/shop/hours"), api.get("/shop/limits"), api.get("/wallet/me"),
    ]);
    const published = products.filter((p) => p.published);
    const html = `
      <div class="grid cols-4 mb-3">
        <div class="stat"><div class="label">Estado de la tienda</div><div class="value" style="font-size:20px;color:${hours.is_open ? "var(--ok)" : "var(--danger)"}">${hours.is_open ? "Abierta" : "Cerrada"}</div><div class="hint">${hours.is_weekday ? "Días hábiles" : "Fin de semana"}</div></div>
        <div class="stat"><div class="label">Mi saldo</div><div class="value">${lun(wallet.balance)}</div><div class="hint">${wallet.debt > 0 ? "Tenés deuda" : "Disponible"}</div></div>
        <div class="stat"><div class="label">Compras hoy (Casa)</div><div class="value">${limits.purchases_today}/${limits.purchase_limit}</div><div class="hint">Máx. ${limits.purchase_limit}/día</div></div>
        <div class="stat"><div class="label">Activaciones hoy (Casa)</div><div class="value">${limits.activations_today}/${limits.activation_limit}</div><div class="hint">Compra ≠ activación</div></div>
      </div>
      ${!hours.is_open ? `<div class="banner warn mb-3">${icon("alert")}<div>La tienda está cerrada. Abre <b>30 min después de la primera dinámica</b> y cierra <b>30 min después de la última</b> (lunes a viernes).</div></div>` : ""}
      <div class="grid auto-260">
        ${published.map((p) => `
          <div class="card product-card">
            <div class="thumb">${icon("sparkles", "")}</div>
            <div>
              <div class="row between"><div class="card-title">${esc(p.name)}</div><span class="price-tag">${num(p.price)} ₤</span></div>
              <div class="small muted mt-1">${esc(p.description || "")}</div>
            </div>
            ${p.conditions ? `<div class="tiny faint">${icon("info")} ${esc(p.conditions)}</div>` : ""}
            <div class="row wrap tiny">
              ${p.affects_points ? `<span class="badge info">Afecta puntos</span>` : ""}
              ${p.requires_approval ? `<span class="badge gold">Requiere aprobación</span>` : ""}
              ${p.stock !== null && p.stock !== undefined ? `<span class="badge muted">Stock: ${p.stock}</span>` : ""}
            </div>
            <button class="btn btn-primary btn-block" data-buy="${p.id}" ${!hours.is_open ? "disabled" : ""}>Comprar</button>
          </div>`).join("")}
      </div>`;
    return {
      title: "Tienda", html,
      after() {
        $$("[data-buy]").forEach((b) => b.addEventListener("click", async () => {
          const pid = parseInt(b.getAttribute("data-buy"), 10);
          const p = published.find((x) => x.id === pid);
          if (!(await confirmDialog("Confirmar compra", `¿Comprar "${p.name}" por ${num(p.price)} ₤?`, "Comprar"))) return;
          try {
            await api.post("/shop/purchase", { product_id: pid, idempotency_key: uid() });
            ok("Compra realizada", "Revisá tus compras para activarla.");
            render();
          } catch (ex) { err("No se pudo comprar", ex.detail || ex.message); }
        }));
      },
    };
  }

  async function viewPurchases() {
    const purchases = await api.get("/shop/purchases");
    const html = `
      <div class="card mb-3"><h2 class="card-title">${icon("receipt")} Mis compras</h2></div>
      ${purchases.length ? `<div class="table-wrap"><table><thead><tr><th>Producto</th><th>Estado</th><th class="num">Precio</th><th>Fecha</th><th></th></tr></thead><tbody>
        ${purchases.map((p) => `<tr>
          <td>${esc(p.product_name || p.product?.name || "—")}</td>
          <td><span class="badge ${p.status === "ACTIVADO" ? "ok" : p.status === "REEMBOLSADO" ? "muted" : "warn"}">${esc(p.status)}</span></td>
          <td class="num">${num(p.price_paid ?? p.price)}</td>
          <td class="small muted">${fmtDateTime(p.purchased_at)}</td>
          <td class="right">${p.status === "PENDIENTE_ACTIVACION" ? `<button class="btn btn-sm btn-ghost" data-refund="${p.id}">Solicitar reembolso</button>` : ""}</td>
        </tr>`).join("")}
      </tbody></table></div>` : `<div class="empty">${icon("bag")}<h3>Sin compras</h3><p class="small">Visitá la tienda para adquirir productos.</p></div>`}`;
    return {
      title: "Mis compras", html,
      after() {
        $$("[data-refund]").forEach((b) => b.addEventListener("click", () => requestRefund(b.getAttribute("data-refund"))));
      },
    };
  }
  async function requestRefund(purchaseId) {
    const ov = openModal({
      title: "Solicitar reembolso",
      body: `<div class="field"><label>Motivo <span class="req">*</span></label><input name="reason" placeholder="Explicá el motivo" required></div>
             <div class="banner warn">${icon("info")}<div>El reembolso requiere aprobación de Dirección y solo aplica si el producto no fue usado (dentro de 15 días).</div></div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Enviar solicitud</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      const reason = ov.querySelector("[name=reason]").value.trim();
      if (!reason) return err("Falta el motivo");
      try { await api.post("/shop/refunds", { purchase_id: parseInt(purchaseId, 10), reason }); closeModal(); ok("Solicitud enviada", "Esperá la aprobación de Dirección."); render(); }
      catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  async function viewShopManage() {
    const products = await api.get("/shop/products");
    const html = `
      <div class="card mb-3"><div class="row between"><h2 class="card-title">${icon("settings")} Catálogo</h2>
        <button class="btn btn-primary" data-new>${icon("plus")} Nuevo producto</button></div>
        <div class="banner info mt-2">${icon("info")}<div>El catálogo es configurable: agregá o editá productos sin tocar código.</div></div>
      </div>
      <div class="table-wrap"><table><thead><tr><th>Producto</th><th class="num">Precio</th><th>Estado</th><th>Puntos</th><th></th></tr></thead><tbody>
        ${products.map((p) => `<tr>
          <td><div style="color:var(--text-strong)">${esc(p.name)}</div><div class="tiny faint">${esc(p.description || "")}</div></td>
          <td class="num">${num(p.price)}</td>
          <td>${p.published ? `<span class="badge ok">Publicado</span>` : `<span class="badge muted">Oculto</span>`}</td>
          <td>${p.affects_points ? `<span class="badge info">Sí</span>` : `<span class="muted small">No</span>`}</td>
          <td class="right nowrap"><button class="btn btn-sm btn-ghost" data-edit="${p.id}">${icon("edit")}</button>
          <button class="btn btn-sm btn-ghost" data-toggle="${p.id}">${icon("refresh")}</button></td>
        </tr>`).join("")}
      </tbody></table></div>`;
    return {
      title: "Catálogo", html,
      after() {
        $("[data-new]").addEventListener("click", () => productModal(null));
        $$("[data-edit]").forEach((b) => b.addEventListener("click", () => productModal(products.find((p) => p.id === parseInt(b.getAttribute("data-edit"), 10)))));
        $$("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
          try { await api.post(`/shop/products/${b.getAttribute("data-toggle")}/toggle`); render(); } catch (ex) { err("Error", ex.detail || ex.message); }
        }));
      },
    };
  }
  function productModal(p) {
    const v = (k, d = "") => (p && p[k] !== null && p[k] !== undefined ? p[k] : d);
    const ov = openModal({
      title: p ? "Editar producto" : "Nuevo producto", wide: true,
      body: `
        <div class="inline-fields">
          <div class="field"><label>Nombre <span class="req">*</span></label><input name="name" value="${esc(v("name"))}" required></div>
          <div class="field"><label>Precio (₤) <span class="req">*</span></label><input name="price" type="number" min="0" value="${esc(v("price", 0))}" required></div>
        </div>
        <div class="field"><label>Descripción</label><textarea name="description">${esc(v("description"))}</textarea></div>
        <div class="inline-fields">
          <div class="field"><label>Condiciones</label><input name="conditions" value="${esc(v("conditions"))}"></div>
          <div class="field"><label>Requisitos de activación</label><input name="activation_requirements" value="${esc(v("activation_requirements"))}"></div>
        </div>
        <div class="field"><label>Reglas especiales</label><input name="special_rules" value="${esc(v("special_rules"))}"></div>
        <div class="inline-fields">
          <div class="field"><label>Límite compra/día</label><input name="purchase_limit_per_day" type="number" min="0" value="${esc(v("purchase_limit_per_day", ""))}"></div>
          <div class="field"><label>Límite activación/día</label><input name="activation_limit_per_day" type="number" min="0" value="${esc(v("activation_limit_per_day", ""))}"></div>
        </div>
        <div class="inline-fields">
          <div class="field"><label>Stock (vacío = ilimitado)</label><input name="stock" type="number" min="0" value="${esc(v("stock", ""))}"></div>
          <div class="field"><label>URL de imagen</label><input name="image_url" value="${esc(v("image_url"))}"></div>
        </div>
        <div class="row wrap" style="gap:18px">
          <label class="checkbox"><input type="checkbox" name="published" ${v("published", true) ? "checked" : ""}> Publicado</label>
          <label class="checkbox"><input type="checkbox" name="affects_points" ${v("affects_points", false) ? "checked" : ""}> Afecta puntos</label>
          <label class="checkbox"><input type="checkbox" name="requires_approval" ${v("requires_approval", true) ? "checked" : ""}> Requiere aprobación</label>
        </div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Guardar</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      const q = (n) => ov.querySelector(`[name=${n}]`);
      const payload = {
        name: q("name").value.trim(), price: parseInt(q("price").value, 10) || 0,
        description: q("description").value.trim() || null, conditions: q("conditions").value.trim() || null,
        activation_requirements: q("activation_requirements").value.trim() || null, special_rules: q("special_rules").value.trim() || null,
        purchase_limit_per_day: q("purchase_limit_per_day").value ? parseInt(q("purchase_limit_per_day").value, 10) : null,
        activation_limit_per_day: q("activation_limit_per_day").value ? parseInt(q("activation_limit_per_day").value, 10) : null,
        stock: q("stock").value ? parseInt(q("stock").value, 10) : null,
        image_url: q("image_url").value.trim() || null,
        published: q("published").checked, affects_points: q("affects_points").checked, requires_approval: q("requires_approval").checked,
      };
      if (!payload.name) return err("Falta el nombre");
      try {
        if (p) await api.patch(`/shop/products/${p.id}`, payload);
        else await api.post("/shop/products", payload);
        closeModal(); ok("Guardado", "Catálogo actualizado."); render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  async function viewActivations() {
    const acts = await api.get("/shop/activations");
    const html = `
      <div class="card mb-3"><h2 class="card-title">${icon("zap")} Activaciones</h2>
        <div class="banner info mt-2">${icon("info")}<div>Las activaciones se realizan hasta <b>15 min antes</b> del inicio de la dinámica y hasta las <b>00:00</b> (hora Argentina) del día.</div></div>
      </div>
      ${acts.length ? `<div class="table-wrap"><table><thead><tr><th>#</th><th>Compra</th><th>Usuario</th><th>Estado</th><th></th></tr></thead><tbody>
        ${acts.map((a) => `<tr><td class="mono">${a.id}</td><td class="mono">${a.purchase_id}</td><td>${a.user_id}</td>
          <td><span class="badge ${a.status === "ACTIVADO" ? "ok" : a.status === "PENDIENTE" ? "warn" : "muted"}">${esc(a.status)}</span></td>
          <td class="right">${a.status !== "ACTIVADO" ? `<button class="btn btn-sm btn-ok" data-act="${a.id}">Activar</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="empty">${icon("zap")}<h3>Sin activaciones</h3></div>`}`;
    return {
      title: "Activaciones", html,
      after() {
        $$("[data-act]").forEach((b) => b.addEventListener("click", async () => {
          try { await api.post(`/shop/activations/${b.getAttribute("data-act")}`, { status: "ACTIVADO", reason: "Activación manual" }); ok("Activado"); render(); }
          catch (ex) { err("Error", ex.detail || ex.message); }
        }));
      },
    };
  }

  async function viewRefunds() {
    const refunds = await api.get("/shop/refunds");
    const html = `
      <div class="card mb-3"><h2 class="card-title">${icon("rotate")} Reembolsos</h2></div>
      ${refunds.length ? `<div class="table-wrap"><table><thead><tr><th>#</th><th>Compra</th><th>Monto</th><th>Estado</th><th>Motivo</th><th></th></tr></thead><tbody>
        ${refunds.map((r) => `<tr><td class="mono">${r.id}</td><td class="mono">${r.purchase_id}</td><td class="num">${num(r.amount)}</td>
          <td><span class="badge ${r.status === "APROBADO" ? "ok" : r.status === "RECHAZADO" ? "danger" : "warn"}">${esc(r.status)}</span></td>
          <td class="small muted">${esc(r.reason || "")}</td>
          <td class="right">${r.status === "SOLICITADO" ? `<button class="btn btn-sm btn-ok" data-yes="${r.id}">Aprobar</button> <button class="btn btn-sm btn-danger" data-no="${r.id}">Rechazar</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="empty">${icon("rotate")}<h3>Sin reembolsos</h3></div>`}`;
    return {
      title: "Reembolsos", html,
      after() {
        $$("[data-yes]").forEach((b) => b.addEventListener("click", () => resolveRefund(b.getAttribute("data-yes"), true)));
        $$("[data-no]").forEach((b) => b.addEventListener("click", () => resolveRefund(b.getAttribute("data-no"), false)));
      },
    };
  }
  async function resolveRefund(id, approve) {
    try { await api.post(`/shop/refunds/${id}/resolve`, { approve, reason: approve ? "Aprobado por Dirección" : "Rechazado" }); ok("Resuelto"); render(); }
    catch (ex) { err("Error", ex.detail || ex.message); }
  }

  /* ======================================================================
     12. Puntos
     ====================================================================== */
  async function viewPoints() {
    const [ledger, sanctions, sb] = await Promise.all([
      api.get("/points/ledger", { query: { limit: 60 } }).catch(() => []),
      api.get("/points/sanctions").catch(() => []),
      api.get("/points/scoreboard"),
    ]);
    const canManage = hasPerm("points:manage");
    const html = `
      <div class="grid cols-3 mb-3">
        ${[...(sb.houses || [])].sort((a, b) => b.points - a.points).map((h) => `
          <div class="stat" style="border-color:${esc(h.heart_hex)}44"><div class="label">${esc(h.name)}</div>
          <div class="value" style="color:${esc(h.heart_hex)}">${num(h.points)}</div><div class="hint">puntos de Copa</div></div>`).join("")}
      </div>
      ${canManage ? `<div class="card mb-3"><div class="row between wrap"><h2 class="card-title">${icon("star")} Gestión de puntos</h2>
        <div class="row wrap">
          <button class="btn" data-p="casa">${icon("crown")} Casa Nocturna</button>
          <button class="btn" data-p="comp">${icon("shield")} Compensación</button>
          <button class="btn" data-p="sanction">${icon("alert")} Sanción de puntos</button>
          <a class="btn" href="#/events">${icon("flag")} Eventos</a>
        </div></div></div>` : ""}
      <div class="grid cols-2">
        <div class="card"><div class="card-head"><h3 class="card-title">${icon("chart")} Libro mayor de puntos</h3></div>
          ${ledger.length ? `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Casa</th><th>Motivo</th><th class="num">Δ</th><th class="num">Saldo</th></tr></thead><tbody>
            ${ledger.map((l) => `<tr><td class="small muted">${fmtDateTime(l.created_at)}</td><td class="small">${esc(l.house_code || l.house_id)}</td><td class="small">${esc(l.reason || l.source || "")}</td>
              <td class="num ${l.delta < 0 ? "amount-neg" : "amount-pos"}">${l.delta > 0 ? "+" : ""}${num(l.delta)}</td><td class="num muted">${num(l.balance_after)}</td></tr>`).join("")}
          </tbody></table></div>` : `<div class="empty">${icon("chart")}<h3>Sin movimientos</h3></div>`}
        </div>
        <div class="card"><div class="card-head"><h3 class="card-title">${icon("alert")} Sanciones</h3></div>
          ${sanctions.length ? `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Motivo</th><th class="num">Monto</th></tr></thead><tbody>
            ${sanctions.map((s) => `<tr><td class="small muted">${fmtDateTime(s.created_at)}</td><td class="small">${esc(s.reason || "")}</td><td class="num amount-neg">${num(s.amount)}</td></tr>`).join("")}
          </tbody></table></div>` : `<div class="empty">${icon("shield")}<h3>Sin sanciones</h3></div>`}
        </div>
      </div>`;
    return {
      title: "Puntos", html,
      after() {
        $$("[data-p]").forEach((b) => b.addEventListener("click", () => pointsOp(b.getAttribute("data-p"))));
      },
    };
  }
  async function pointsOp(op) {
    const houses = cache.houses || [];
    const competing = houses.filter((h) => h.is_competing);
    const houseOpts = houses.map((h) => `<option value="${h.id}">${esc(h.name)}</option>`).join("");
    let body = "";
    if (op === "casa") {
      body = `<div class="banner info mb-2">${icon("info")}<div>Asigná puntos de Casa Nocturna a cada Casa competidora.</div></div>
        ${competing.map((h) => `<div class="field"><label>${esc(h.name)}</label><input name="h_${h.id}" type="number" value="0"></div>`).join("")}
        <div class="field"><label>Motivo <span class="req">*</span></label><input name="reason" required></div>`;
    } else if (op === "comp") {
      body = `<div class="field"><label>Casa <span class="req">*</span></label><select name="house_id">${houseOpts}</select></div>
        <div class="field"><label>Monto (₤/pts) — por defecto 7500</label><input name="amount" type="number" value="7500"></div>
        <div class="field"><label>Motivo <span class="req">*</span></label><input name="reason" value="Compensación por cancelación" required></div>`;
    } else {
      body = `<div class="field"><label>Casa objetivo</label><select name="house_id">${houseOpts}</select></div>
        <div class="field"><label>Monto <span class="req">*</span></label><input name="amount" type="number" min="1" value="1000" required></div>
        <div class="field"><label>Motivo <span class="req">*</span></label><input name="reason" required></div>`;
    }
    const ov = openModal({
      title: { casa: "Puntos de Casa Nocturna", comp: "Compensación", sanction: "Sanción de puntos" }[op],
      body, footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Confirmar</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      try {
        if (op === "casa") {
          const allocations = competing.map((h) => ({ house_id: h.id, points: parseInt(ov.querySelector(`[name=h_${h.id}]`).value, 10) || 0 })).filter((a) => a.points);
          await api.post("/points/casa-nocturna", { allocations, reason: ov.querySelector("[name=reason]").value.trim() });
        } else if (op === "comp") {
          await api.post("/points/compensation", { house_id: parseInt(ov.querySelector("[name=house_id]").value, 10), amount: parseInt(ov.querySelector("[name=amount]").value, 10) || 7500, reason: ov.querySelector("[name=reason]").value.trim() });
        } else {
          await api.post("/points/sanction", { target_house_id: parseInt(ov.querySelector("[name=house_id]").value, 10), resource: "PUNTOS", amount: parseInt(ov.querySelector("[name=amount]").value, 10), reason: ov.querySelector("[name=reason]").value.trim() });
        }
        closeModal(); ok("Operación registrada"); render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  /* ======================================================================
     13. Eventos
     ====================================================================== */
  async function viewEvents() {
    const events = await api.get("/events");
    const canManage = hasPerm("events:manage");
    const typeLabel = { DINAMICA: "Dinámica", RETO_GRUPAL: "Reto grupal", RETO_INDIVIDUAL: "Reto individual", FLASH_STICKER: "Flash sticker" };
    const statusColor = { BORRADOR: "muted", CONFIRMADA: "ok", RECTIFICADA: "warn", CANCELADA: "danger" };
    const html = `
      <div class="card mb-3"><div class="row between wrap"><h2 class="card-title">${icon("flag")} Eventos</h2>
        ${canManage ? `<div class="row wrap"><button class="btn" data-e="group">${icon("users")} Reto grupal</button>
        <button class="btn" data-e="individual">${icon("user")} Reto individual</button>
        <button class="btn btn-primary" data-e="new">${icon("plus")} Nuevo evento</button></div>` : ""}</div></div>
      ${events.length ? `<div class="grid auto-320">${events.map((e) => `
        <div class="card">
          <div class="row between"><span class="badge ${statusColor[e.status] || "muted"}">${esc(e.status)}</span>
            <span class="badge muted">${esc(typeLabel[e.type] || e.type)}</span></div>
          <div class="card-title mt-1">${esc(e.name)}</div>
          <div class="small muted">${e.scheduled_at ? fmtDateTime(e.scheduled_at) : "Sin fecha"}</div>
          ${e.double_points ? `<span class="badge gold mt-1">Puntos dobles</span>` : ""}
          ${canManage ? `<div class="row mt-2 wrap">
            ${e.status === "BORRADOR" ? `<button class="btn btn-sm btn-ok" data-conf="${e.id}">${icon("check")} Confirmar</button>` : ""}
            ${e.status === "CONFIRMADA" ? `<button class="btn btn-sm" data-rect="${e.id}">${icon("refresh")} Rectificar</button>` : ""}
            <button class="btn btn-sm btn-danger" data-cancel="${e.id}">${icon("x")} Cancelar</button>
          </div>` : ""}
        </div>`).join("")}</div>` : `<div class="empty">${icon("flag")}<h3>Sin eventos</h3><p class="small">${canManage ? "Creá el primer evento de la temporada." : "Aún no hay eventos programados."}</p></div>`}`;
    return {
      title: "Eventos", html,
      after() {
        const houses = cache.houses || [];
        $$("[data-e]").forEach((b) => b.addEventListener("click", () => eventModal(b.getAttribute("data-e"), houses)));
        $$("[data-conf]").forEach((b) => b.addEventListener("click", async () => { try { await api.post(`/events/${b.getAttribute("data-conf")}/confirm`); ok("Evento confirmado"); render(); } catch (ex) { err("Error", ex.detail || ex.message); } }));
        $$("[data-rect]").forEach((b) => b.addEventListener("click", async () => { try { await api.post(`/events/${b.getAttribute("data-rect")}/rectify`); ok("Evento rectificado"); render(); } catch (ex) { err("Error", ex.detail || ex.message); } }));
        $$("[data-cancel]").forEach((b) => b.addEventListener("click", async () => { if (await confirmDialog("Cancelar evento", "¿Cancelar este evento? Se aplicará compensación.", "Cancelar evento", true)) { try { await api.post(`/events/${b.getAttribute("data-cancel")}/cancel`, { reason: "Cancelado por Dirección" }); ok("Evento cancelado"); render(); } catch (ex) { err("Error", ex.detail || ex.message); } } }));
      },
    };
  }
  function eventModal(kind, houses) {
    const houseOpts = houses.map((h) => `<option value="${h.id}">${esc(h.name)}</option>`).join("");
    let body, title;
    if (kind === "group") {
      title = "Nuevo reto grupal";
      body = `<div class="field"><label>Nombre <span class="req">*</span></label><input name="name" required></div>
        <div class="field"><label>Fecha y hora</label><input name="scheduled_at" type="datetime-local"></div>
        <div class="banner info mb-2">${icon("info")}<div>Elegí el orden de llegada de las Casas (1º, 2º, 3º). Puntos: 40000 / 30000 / 20000.</div></div>
        ${[1, 2, 3].map((i) => `<div class="field"><label>${i}º puesto</label><select name="rank${i}"><option value="">—</option>${houseOpts}</select></div>`).join("")}`;
    } else if (kind === "individual") {
      title = "Nuevo reto individual";
      body = `<div class="field"><label>Nombre <span class="req">*</span></label><input name="name" required></div>
        <div class="field"><label>Casa <span class="req">*</span></label><select name="house_id">${houseOpts}</select></div>
        <div class="field"><label>Fecha y hora</label><input name="scheduled_at" type="datetime-local"></div>
        <div class="banner info mb-2">${icon("info")}<div>Cada entrega válida otorga 16000 puntos a la Casa.</div></div>`;
    } else {
      title = "Nuevo evento";
      body = `<div class="field"><label>Nombre <span class="req">*</span></label><input name="name" required></div>
        <div class="field"><label>Tipo <span class="req">*</span></label><select name="type">
          <option value="DINAMICA">Dinámica</option><option value="RETO_GRUPAL">Reto grupal</option>
          <option value="RETO_INDIVIDUAL">Reto individual</option><option value="FLASH_STICKER">Flash sticker</option></select></div>
        <div class="field"><label>Casa responsable</label><select name="house_responsible_id">${houseOpts}</select></div>
        <div class="field"><label>Fecha y hora</label><input name="scheduled_at" type="datetime-local"></div>
        <div class="field"><label>Rondas jugadas</label><input name="rounds_played" type="number" min="0"></div>
        <label class="checkbox"><input type="checkbox" name="double_points"> Puntos dobles (máx. una por día)</label>`;
    }
    const ov = openModal({ title, body, footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Crear</button>` });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      const q = (n) => ov.querySelector(`[name=${n}]`);
      const iso = q("scheduled_at") && q("scheduled_at").value ? new Date(q("scheduled_at").value).toISOString() : null;
      try {
        if (kind === "group") {
          const ranking = [1, 2, 3].map((i) => q("rank" + i).value).filter(Boolean).map((v) => parseInt(v, 10));
          if (!q("name").value.trim()) return err("Falta el nombre");
          await api.post("/events/group-challenge", { name: q("name").value.trim(), scheduled_at: iso, ranking });
        } else if (kind === "individual") {
          if (!q("name").value.trim()) return err("Falta el nombre");
          await api.post("/events/individual-challenge", { name: q("name").value.trim(), house_id: parseInt(q("house_id").value, 10), scheduled_at: iso });
        } else {
          await api.post("/events", {
            name: q("name").value.trim(), type: q("type").value,
            house_responsible_id: q("house_responsible_id") ? parseInt(q("house_responsible_id").value, 10) : null,
            scheduled_at: iso, double_points: q("double_points") ? q("double_points").checked : false,
            rounds_played: q("rounds_played") && q("rounds_played").value ? parseInt(q("rounds_played").value, 10) : null,
          });
        }
        closeModal(); ok("Evento creado"); render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  /* ======================================================================
     14. Calendario
     ====================================================================== */
  async function viewCalendar() {
    const [schedule, events] = await Promise.all([
      api.get("/schedule").catch(() => []),
      api.get("/events").catch(() => []),
    ]);
    const now = new Date();
    const year = now.getFullYear(), month = now.getMonth();
    const first = new Date(year, month, 1);
    const startDow = (first.getDay() + 6) % 7; // lunes = 0
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const dows = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
    const byDay = {};
    events.forEach((e) => { const d = parseDT(e.scheduled_at); if (d && d.getMonth() === month && d.getFullYear() === year) { const k = d.getDate(); (byDay[k] = byDay[k] || []).push(e); } });
    schedule.forEach((s) => { if (s.date) { const d = parseDT(s.date); if (d && d.getMonth() === month) { const k = d.getDate(); (byDay[k] = byDay[k] || []).push({ name: s.activity_name, scheduled_at: s.date, type: s.activity_type, _sched: true }); } } });

    let cells = "";
    for (let i = 0; i < startDow; i++) cells += `<div class="cal-cell empty"></div>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const isToday = d === now.getDate();
      const evs = byDay[d] || [];
      cells += `<div class="cal-cell ${isToday ? "today" : ""}">
        <div class="dnum">${d}</div>
        ${evs.slice(0, 3).map((e) => `<div class="cal-event" title="${esc(e.name)}">${esc(e.name)}</div>`).join("")}
        ${evs.length > 3 ? `<div class="tiny faint">+${evs.length - 3} más</div>` : ""}
      </div>`;
    }
    const html = `
      <div class="card mb-3"><div class="row between"><h2 class="card-title">${icon("calendar")} ${first.toLocaleDateString("es-AR", { month: "long", year: "numeric" })}</h2>
        <span class="badge gold">Zona: ${esc(tzLabel())}</span></div></div>
      <div class="card">
        <div class="cal-grid">${dows.map((d) => `<div class="cal-dow">${d}</div>`).join("")}</div>
        <div class="cal-grid mt-1">${cells}</div>
      </div>
      <div class="grid cols-2 mt-3">
        <div class="card"><div class="card-head"><h3 class="card-title">${icon("flag")} Próximos eventos</h3></div>
          ${events.filter((e) => parseDT(e.scheduled_at) >= now).slice(0, 6).map((e) => `<div class="ledger-row"><div><div style="color:var(--text-strong)">${esc(e.name)}</div><div class="tiny faint">${fmtDateTime(e.scheduled_at)}</div></div><span class="badge muted">${esc(e.type)}</span></div>`).join("") || `<div class="muted small">Sin eventos próximos.</div>`}
        </div>
        <div class="card"><div class="card-head"><h3 class="card-title">${icon("calendar")} Horarios cargados</h3></div>
          ${schedule.length ? schedule.map((s) => `<div class="ledger-row"><div><div style="color:var(--text-strong)">${esc(s.activity_name || s.activity_type)}</div><div class="tiny faint">${esc(s.start_time || "")}${s.end_time ? "–" + esc(s.end_time) : ""}</div></div><span class="badge muted">${esc(s.status || "")}</span></div>`).join("") : `<div class="muted small">Sin horarios cargados.</div>`}
        </div>
      </div>`;
    return { title: "Calendario", html };
  }

  /* ======================================================================
     15. Partis
     ====================================================================== */
  async function viewPartis() {
    const summary = await api.get("/partis/summary").catch(() => []);
    const canManage = hasPerm("partis:manage");
    const total = summary.reduce((a, s) => a + (s.partis || 0), 0);
    const html = `
      <div class="grid cols-3 mb-3">
        <div class="stat accent-gold"><div class="label">Partis totales</div><div class="value">${num(total)}</div><div class="hint">Registros de participación</div></div>
        <div class="stat"><div class="label">Participantes</div><div class="value">${num(summary.length)}</div><div class="hint">Cuentas registradas</div></div>
        <div class="stat"><div class="label">Promedio</div><div class="value">${summary.length ? (total / summary.length).toFixed(1) : "0"}</div><div class="hint">Partis por persona</div></div>
      </div>
      ${canManage ? `<div class="card mb-3"><div class="row between"><h2 class="card-title">${icon("award")} Registro manual</h2>
        <button class="btn btn-primary" data-add>${icon("plus")} Otorgar partis</button></div></div>` : ""}
      <div class="table-wrap"><table><thead><tr><th>Identificador</th><th>Nombre</th><th>Casa</th><th class="num">Partis</th></tr></thead><tbody>
        ${summary.sort((a, b) => b.partis - a.partis).map((s) => `<tr><td class="mono gold">${esc(s.identifier)}</td><td>${esc(s.display_name)}</td>
          <td class="small muted">${esc(houseById(s.house_id)?.name || "—")}</td><td class="num">${num(s.partis)}</td></tr>`).join("")}
      </tbody></table></div>`;
    return {
      title: "Partis", html,
      after() {
        const b = $("[data-add]");
        if (b) b.addEventListener("click", () => partisModal(summary));
      },
    };
  }
  function partisModal(users) {
    const opts = users.map((u) => `<option value="${u.user_id}">${esc(u.identifier)} — ${esc(u.display_name)}</option>`).join("");
    const ov = openModal({
      title: "Otorgar partis",
      body: `<div class="field"><label>Usuario <span class="req">*</span></label><select name="user_id">${opts}</select></div>
        <div class="field"><label>Cantidad de partis <span class="req">*</span></label><input name="partis" type="number" min="1" value="1" required></div>
        <div class="field"><label>Motivo</label><input name="reason" placeholder="Opcional"></div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Otorgar</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      try {
        await api.post("/partis", { user_id: parseInt(ov.querySelector("[name=user_id]").value, 10), partis: parseInt(ov.querySelector("[name=partis]").value, 10), reason: ov.querySelector("[name=reason]").value.trim() || null });
        closeModal(); ok("Partis otorgadas"); render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  /* ======================================================================
     16. Usuarios
     ====================================================================== */
  async function viewUsers() {
    const users = await api.get("/users");
    const canCreate = hasPerm("users:create");
    const html = `
      <div class="card mb-3"><div class="row between wrap"><h2 class="card-title">${icon("users")} Usuarios</h2>
        <div class="row"><input data-search placeholder="Buscar…" style="min-width:220px">${canCreate ? `<button class="btn btn-primary" data-new>${icon("plus")} Crear cuenta</button>` : ""}</div></div></div>
      <div class="table-wrap"><table><thead><tr><th>Identificador</th><th>Nombre</th><th>Casa</th><th>Rol</th><th>Estado</th><th></th></tr></thead><tbody data-rows>
        ${users.map((u) => `<tr data-row data-text="${esc((u.display_name + " " + u.identifier).toLowerCase())}">
          <td class="mono gold">${esc(u.identifier)}</td>
          <td><div class="row" style="gap:8px"><span class="avatar" style="width:28px;height:28px;font-size:12px">${esc(initials(u.display_name))}</span>${esc(u.display_name)}</div></td>
          <td class="small">${u.house ? houseDot(u.house) : "—"}</td>
          <td class="small">${esc(roleLabel(u.role))}</td>
          <td>${statusBadge(u.status)}</td>
          <td class="right nowrap"><button class="btn btn-sm btn-ghost" data-view="${u.id}">${icon("user")}</button></td>
        </tr>`).join("")}
      </tbody></table></div>`;
    return {
      title: "Usuarios", html,
      after() {
        const s = $("[data-search]");
        if (s) s.addEventListener("input", () => { const q = s.value.toLowerCase(); $$("[data-row]").forEach((r) => r.classList.toggle("hidden", !r.getAttribute("data-text").includes(q))); });
        const nb = $("[data-new]"); if (nb) nb.addEventListener("click", createUserModal);
        $$("[data-view]").forEach((b) => b.addEventListener("click", () => userDetailModal(users.find((u) => u.id === parseInt(b.getAttribute("data-view"), 10)))));
      },
    };
  }
  async function createUserModal() {
    const houses = cache.houses || [];
    const roles = cache.roles || [];
    const ov = openModal({
      title: "Crear cuenta",
      body: `<div class="banner info mb-2">${icon("info")}<div>Solo Dirección crea cuentas. Se envía una invitación de un solo uso para el primer acceso.</div></div>
        <div class="field"><label>Nombre visible <span class="req">*</span></label><input name="display_name" required></div>
        <div class="inline-fields">
          <div class="field"><label>Casa <span class="req">*</span></label><select name="house_id">${houses.map((h) => `<option value="${h.id}">${esc(h.name)}</option>`).join("")}</select></div>
          <div class="field"><label>Rol <span class="req">*</span></label><select name="role">${roles.map((r) => `<option value="${r.code}">${esc(r.name)}</option>`).join("")}</select></div>
        </div>
        <div class="field"><label>Correo (opcional)</label><input name="email" type="email"></div>
        <div class="field"><label>Zona horaria</label><select name="timezone" data-tz></select></div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Crear e invitar</button>`,
    });
    await fillTimezoneSelect(ov.querySelector("[data-tz]"));
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      const q = (n) => ov.querySelector(`[name=${n}]`);
      try {
        const res = await api.post("/users", { display_name: q("display_name").value.trim(), house_id: parseInt(q("house_id").value, 10), role: q("role").value, email: q("email").value.trim() || null, timezone: q("timezone").value || null });
        closeModal();
        const id = res && res.user ? res.user.identifier : "";
        ok("Cuenta creada", id ? `Identificador: ${id}` : "Invitación enviada.");
        render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }
  async function userDetailModal(u) {
    if (!u) return;
    const houses = cache.houses || [];
    const roles = cache.roles || [];
    const ov = openModal({
      title: `${u.display_name} · ${u.identifier}`, wide: true,
      body: `
        <div class="grid cols-2">
          <div class="field"><label>Nombre visible</label><input name="display_name" value="${esc(u.display_name)}"></div>
          <div class="field"><label>Correo</label><input name="email" value="${esc(u.email || "")}"></div>
        </div>
        <div class="grid cols-2">
          <div class="field"><label>Rol</label><select name="role">${roles.map((r) => `<option value="${r.code}" ${r.code === u.role ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>
          <div class="field"><label>Casa</label><select name="house_id">${houses.map((h) => `<option value="${h.id}" ${h.id === u.house_id ? "selected" : ""}>${esc(h.name)}</option>`).join("")}</select></div>
        </div>
        <div class="field"><label>Estado</label><select name="status">
          ${["ACTIVA", "CONGELADA", "DADA_DE_BAJA", "PENDIENTE_DE_ACTIVACION"].map((s) => `<option value="${s}" ${s === u.status ? "selected" : ""}>${s}</option>`).join("")}
        </select></div>
        <div class="field"><label>Zona horaria</label><select name="timezone" data-tz></select></div>
        <div class="divider"></div>
        <div class="row wrap"><button class="btn btn-ok btn-sm" data-freeze>Congelar</button><button class="btn btn-sm" data-unfreeze>Reactivar</button>
        <button class="btn btn-sm" data-resend>Reenviar invitación</button></div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cerrar</button><button class="btn btn-primary" data-do>Guardar cambios</button>`,
    });
    await fillTimezoneSelect(ov.querySelector("[data-tz]"), u.timezone);
    const q = (n) => ov.querySelector(`[name=${n}]`);
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      try {
        await api.patch(`/users/${u.id}`, { display_name: q("display_name").value.trim(), email: q("email").value.trim() || null, timezone: q("timezone").value || null });
        if (q("role").value !== u.role) await api.post(`/users/${u.id}/role`, { role: q("role").value });
        if (parseInt(q("house_id").value, 10) !== u.house_id) await api.post(`/users/${u.id}/house`, { house_id: parseInt(q("house_id").value, 10) });
        if (q("status").value !== u.status) await api.post(`/users/${u.id}/status`, { status: q("status").value, reason: "Cambio desde panel" });
        closeModal(); ok("Usuario actualizado"); render();
      } catch (ex) { err("Error", ex.detail || ex.message); }
    });
    ov.querySelector("[data-freeze]").addEventListener("click", async () => { try { await api.post(`/users/${u.id}/freeze`, { reason: "Congelada desde panel" }); closeModal(); ok("Cuenta congelada"); render(); } catch (ex) { err("Error", ex.detail || ex.message); } });
    ov.querySelector("[data-unfreeze]").addEventListener("click", async () => { try { await api.post(`/users/${u.id}/unfreeze`); closeModal(); ok("Cuenta reactivada"); render(); } catch (ex) { err("Error", ex.detail || ex.message); } });
    ov.querySelector("[data-resend]").addEventListener("click", async () => { try { await api.post(`/users/${u.id}/resend-invitation`); ok("Invitación reenviada"); } catch (ex) { err("Error", ex.detail || ex.message); } });
  }

  /* ======================================================================
     17. Reclamaciones
     ====================================================================== */
  async function viewComplaints() {
    const list = await api.get("/complaints").catch(() => []);
    const canResolve = hasPerm("complaints:resolve");
    const html = `
      <div class="card mb-3"><div class="row between"><h2 class="card-title">${icon("message")} Reclamaciones</h2>
        <button class="btn btn-primary" data-new>${icon("plus")} Nueva reclamación</button></div></div>
      ${list.length ? `<div class="grid auto-320">${list.map((c) => `
        <div class="card"><div class="row between"><span class="badge ${c.status === "RESUELTA" ? "ok" : "warn"}">${esc(c.status)}</span><span class="tiny faint">${fmtDate(c.created_at)}</span></div>
        <div class="card-title mt-1">${esc(c.subject)}</div>
        <div class="small muted">${esc(c.reason)}</div>
        ${c.resolution ? `<div class="banner ok mt-2">${icon("check")}<div>${esc(c.resolution)}</div></div>` : ""}
        ${canResolve && c.status !== "RESUELTA" ? `<button class="btn btn-sm btn-ok mt-2" data-res="${c.id}">Resolver</button>` : ""}</div>`).join("")}</div>` : `<div class="empty">${icon("message")}<h3>Sin reclamaciones</h3></div>`}`;
    return {
      title: "Reclamaciones", html,
      after() {
        $("[data-new]").addEventListener("click", complaintModal);
        $$("[data-res]").forEach((b) => b.addEventListener("click", () => resolveComplaint(b.getAttribute("data-res"))));
      },
    };
  }
  function complaintModal() {
    const ov = openModal({
      title: "Nueva reclamación",
      body: `<div class="field"><label>Asunto <span class="req">*</span></label><input name="subject" required></div>
        <div class="field"><label>Motivo <span class="req">*</span></label><textarea name="reason" required></textarea></div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Enviar</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      try { await api.post("/complaints", { subject: ov.querySelector("[name=subject]").value.trim(), reason: ov.querySelector("[name=reason]").value.trim() }); closeModal(); ok("Reclamación enviada"); render(); }
      catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }
  async function resolveComplaint(id) {
    const ov = openModal({
      title: "Resolver reclamación",
      body: `<div class="field"><label>Resolución <span class="req">*</span></label><textarea name="resolution" required></textarea></div>`,
      footer: `<button class="btn btn-ghost" data-cancel>Cancelar</button><button class="btn btn-primary" data-do>Resolver</button>`,
    });
    ov.querySelector("[data-cancel]").addEventListener("click", closeModal);
    ov.querySelector("[data-do]").addEventListener("click", async () => {
      try { await api.post(`/complaints/${id}/resolve`, { status: "RESUELTA", resolution: ov.querySelector("[name=resolution]").value.trim() }); closeModal(); ok("Reclamación resuelta"); render(); }
      catch (ex) { err("Error", ex.detail || ex.message); }
    });
  }

  /* ======================================================================
     18. Reportes
     ====================================================================== */
  async function viewReports() {
    const data = await api.get("/reports").catch(() => ({ reports: [] }));
    const labels = {
      wallet_global: "Banco global", wallet_account: "Billetera por cuenta", purchases: "Compras", refunds: "Reembolsos",
      activations: "Activaciones", products: "Catálogo", house_points: "Puntos por Casa", events: "Eventos",
      rewards: "Recompensas", partis: "Partis", members: "Miembros", sanctions: "Sanciones", admin_activity: "Actividad administrativa",
    };
    const html = `
      <div class="card mb-3"><h2 class="card-title">${icon("download")} Reportes</h2>
        <div class="banner info mt-2">${icon("info")}<div>Los reportes se generan en el backend respetando tus permisos. Exportá en CSV o XLSX.</div></div></div>
      <div class="grid auto-260">
        ${(data.reports || []).map((r) => `
          <div class="card">
            <div class="row between"><div class="card-title">${esc(labels[r] || r)}</div>${icon("chart", "")}</div>
            <div class="row mt-2"><button class="btn btn-sm" data-export="${r}" data-fmt="csv">CSV</button>
            <button class="btn btn-sm" data-export="${r}" data-fmt="xlsx">XLSX</button></div>
          </div>`).join("")}
      </div>`;
    return {
      title: "Reportes", html,
      after() {
        $$("[data-export]").forEach((b) => b.addEventListener("click", () => exportReport(b.getAttribute("data-export"), b.getAttribute("data-fmt"))));
      },
    };
  }
  async function exportReport(name, fmt) {
    try {
      const res = await api.raw(`/reports/${name}`, { query: { format: fmt } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${name}.${fmt}`; document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      ok("Descarga iniciada", `${name}.${fmt}`);
    } catch (ex) { err("No se pudo exportar", ex.detail || ex.message); }
  }

  /* ======================================================================
     19. Auditoría
     ====================================================================== */
  async function viewAudit() {
    const logs = await api.get("/audit", { query: { limit: 120 } }).catch(() => []);
    const html = `
      <div class="card mb-3"><h2 class="card-title">${icon("shield")} Auditoría</h2>
        <div class="banner info mt-2">${icon("info")}<div>Registro de solo-anexado. Toda operación sensible queda asentada con actor, acción, entidad e IP.</div></div></div>
      <div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Entidad</th><th>IP</th></tr></thead><tbody>
        ${logs.map((l) => `<tr><td class="small muted">${fmtDateTime(l.created_at)}</td><td class="mono gold">${esc(l.actor_identifier || l.actor_id || "—")}</td>
          <td><span class="badge muted">${esc(l.action)}</span></td><td class="small">${esc(l.entity_type || "")} ${l.entity_id ? "#" + esc(l.entity_id) : ""}</td>
          <td class="small faint mono">${esc(l.ip || "—")}</td></tr>`).join("")}
      </tbody></table></div>`;
    return { title: "Auditoría", html };
  }

  /* ======================================================================
     20. Configuración
     ====================================================================== */
  async function viewConfig() {
    const settings = await api.get("/config").catch(() => []);
    const list = Array.isArray(settings) ? settings : (settings.settings || []);
    const html = `
      <div class="card mb-3"><h2 class="card-title">${icon("settings")} Configuración</h2>
        <div class="banner info mt-2">${icon("info")}<div>Parámetros globales del sistema. Los cambios quedan auditados.</div></div></div>
      <div class="grid auto-320">
        ${list.map((s) => `
          <div class="card">
            <div class="field"><label>${esc(s.key)}</label>
              <input data-set="${esc(s.key)}" value="${esc(typeof s.value === "object" ? JSON.stringify(s.value) : s.value)}">
              ${s.description ? `<div class="help">${esc(s.description)}</div>` : ""}</div>
            <button class="btn btn-sm btn-primary" data-save="${esc(s.key)}">Guardar</button>
          </div>`).join("") || `<div class="empty">${icon("settings")}<h3>Sin parámetros</h3></div>`}
      </div>`;
    return {
      title: "Configuración", html,
      after() {
        $$("[data-save]").forEach((b) => b.addEventListener("click", async () => {
          const key = b.getAttribute("data-save");
          const input = $(`[data-set="${key}"]`);
          let value = input.value;
          try { value = JSON.parse(value); } catch { /* dejar como string */ }
          try { await api.put("/config", { key, value }); ok("Guardado", key); }
          catch (ex) { err("Error", ex.detail || ex.message); }
        }));
      },
    };
  }

  /* ======================================================================
     21. Perfil
     ====================================================================== */
  async function viewProfile() {
    const u = currentUser();
    const house = u.house;
    const html = `
      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><h2 class="card-title">${icon("user")} Mi perfil</h2></div>
          <div class="row" style="gap:16px;margin-bottom:18px">
            <div class="avatar" style="width:64px;height:64px;font-size:24px">${esc(initials(u.display_name))}</div>
            <div>
              <div style="font-family:var(--font-display);font-size:20px;color:var(--text-strong)">${esc(u.display_name)}</div>
              <div class="mono gold">${esc(u.identifier)}</div>
              <div class="small muted">${esc(roleLabel(u.role))} ${house ? "· " + esc(house.name) : ""}</div>
            </div>
          </div>
          <form data-form="profile">
            <div class="field"><label>Nombre visible</label><input name="display_name" value="${esc(u.display_name)}"></div>
            <div class="field"><label>URL de foto</label><input name="photo_url" value="${esc(u.photo_url || "")}" placeholder="https://…"></div>
            <div class="field"><label>${icon("globe")} Zona horaria / país</label>
              <select name="timezone" data-tz></select>
              <div class="help">Adaptá los horarios a tu país. Por defecto: Argentina (Buenos Aires).</div></div>
            <div class="field"><label>Idioma</label>
              <select name="locale"><option value="es" ${u.locale === "es" ? "selected" : ""}>Español</option><option value="en" ${u.locale === "en" ? "selected" : ""}>English</option><option value="pt" ${u.locale === "pt" ? "selected" : ""}>Português</option></select></div>
            <button class="btn btn-primary" type="submit">Guardar cambios</button>
          </form>
        </div>
        <div class="col">
          <div class="card">
            <div class="card-head"><h3 class="card-title">${icon("lock")} Seguridad</h3></div>
            <form data-form="pwd">
              <div class="field"><label>Contraseña actual</label><input name="current_password" type="password" required></div>
              <div class="field"><label>Nueva contraseña</label><input name="new_password" type="password" required></div>
              <button class="btn" type="submit">Cambiar contraseña</button>
            </form>
          </div>
          <div class="card">
            <div class="card-head"><h3 class="card-title">${icon("mail")} Correo</h3></div>
            <div class="row between"><span>${esc(u.email || "Sin correo")}</span>${u.email_verified ? `<span class="badge ok">Verificado</span>` : `<span class="badge warn">Sin verificar</span>`}</div>
            ${!u.email_verified ? `<button class="btn btn-sm mt-2" data-resend-verif>Reenviar verificación</button>` : ""}
          </div>
          ${house ? `<div class="card" style="border-color:${esc(house.heart_hex)}44">
            <div class="card-head"><h3 class="card-title" style="color:${esc(house.heart_hex)}">${esc(house.name)}</h3></div>
            <div class="small muted">${esc(house.virtues || "")}</div>
            <p class="serif mt-1">${esc(house.identity || "")}</p>
          </div>` : ""}
        </div>
      </div>`;
    return {
      title: "Perfil", html,
      async after() {
        await fillTimezoneSelect($("[data-tz]"), u.timezone);
        $("[data-form=profile]").addEventListener("submit", async (e) => {
          e.preventDefault(); const f = e.target;
          try {
            await api.patch("/auth/me", { display_name: f.display_name.value.trim(), photo_url: f.photo_url.value.trim() || null, timezone: f.timezone.value, locale: f.locale.value });
            await api.me();
            ok("Perfil actualizado", "Zona horaria: " + tzLabel());
            render();
          } catch (ex) { err("Error", ex.detail || ex.message); }
        });
        $("[data-form=pwd]").addEventListener("submit", async (e) => {
          e.preventDefault(); const f = e.target;
          try { await api.post("/auth/change-password", { current_password: f.current_password.value, new_password: f.new_password.value }); ok("Contraseña cambiada"); f.reset(); }
          catch (ex) { err("Error", ex.detail || ex.message); }
        });
        const rv = $("[data-resend-verif]");
        if (rv) rv.addEventListener("click", async () => { try { await api.post("/auth/resend-verification"); ok("Enviado", "Revisá tu correo."); } catch (ex) { err("Error", ex.detail || ex.message); } });
      },
    };
  }

  /* ======================================================================
     22. 404
     ====================================================================== */
  function viewNotFound() {
    return { title: "No encontrado", html: `<div class="empty">${icon("search")}<h3>Página no encontrada</h3><p class="small">La sección que buscás no existe.</p><a class="btn btn-primary mt-2" href="#/">Volver al panel</a></div>` };
  }

  /* ======================================================================
     23. Arranque
     ====================================================================== */
  async function boot() {
    // Si hay token, validar sesión
    if (store.token) {
      try { await api.me(); } catch { store.clear(); }
    }
    if (!location.hash) location.hash = store.token ? "#/" : "#/login";
    await render();
  }

  document.addEventListener("DOMContentLoaded", boot);
  if (document.readyState !== "loading") boot();
})();
