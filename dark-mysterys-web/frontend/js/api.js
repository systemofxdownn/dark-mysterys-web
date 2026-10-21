/* ==========================================================================
   Dark Mystery's — Cliente API
   Envoltorio de fetch con manejo de token, errores y utilidades.
   ========================================================================== */
(function () {
  "use strict";

  const TOKEN_KEY = "dm_token";
  const USER_KEY = "dm_user";

  const store = {
    get token() { return localStorage.getItem(TOKEN_KEY); },
    set token(v) { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY); },
    get user() { try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch { return null; } },
    set user(v) { v ? localStorage.setItem(USER_KEY, JSON.stringify(v)) : localStorage.removeItem(USER_KEY); },
    clear() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); },
  };

  class ApiError extends Error {
    constructor(status, detail, payload) {
      super(typeof detail === "string" ? detail : "Error de la API");
      this.status = status;
      this.detail = detail;
      this.payload = payload;
    }
  }

  async function request(method, path, body, opts = {}) {
    const headers = { "Content-Type": "application/json" };
    const token = store.token;
    if (token && !opts.noAuth) headers["Authorization"] = "Bearer " + token;

    let url = "/api" + path;
    if (opts.query) {
      const qs = new URLSearchParams();
      Object.entries(opts.query).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") qs.append(k, v); });
      const s = qs.toString();
      if (s) url += "?" + s;
    }

    let res;
    try {
      res = await fetch(url, {
        method,
        headers,
        body: body !== undefined && body !== null ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError(0, "No se pudo conectar con el servidor.");
    }

    // Descargas (blob)
    if (opts.raw) {
      if (!res.ok) throw new ApiError(res.status, await res.text());
      return res;
    }

    let data = null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      try { data = await res.json(); } catch { data = null; }
    } else {
      data = await res.text();
    }

    if (!res.ok) {
      let detail = (data && data.detail) || data || res.statusText;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      if (res.status === 401 && !opts.noRedirect) {
        store.clear();
        if (!location.hash.startsWith("#/login")) location.hash = "#/login";
      }
      throw new ApiError(res.status, detail, data);
    }
    return data;
  }

  const api = {
    store,
    ApiError,
    get: (p, opts) => request("GET", p, null, opts),
    post: (p, b, opts) => request("POST", p, b, opts),
    put: (p, b, opts) => request("PUT", p, b, opts),
    patch: (p, b, opts) => request("PATCH", p, b, opts),
    del: (p, opts) => request("DELETE", p, null, opts),
    raw: (p, opts) => request("GET", p, null, { ...opts, raw: true }),

    // --- Auth ---
    async login(identifier, password) {
      const data = await request("POST", "/auth/login", { identifier, password }, { noAuth: true });
      store.token = data.access_token;
      return data;
    },
    async me() {
      const data = await request("GET", "/auth/me");
      store.user = data;
      return data;
    },
    logout() { store.clear(); },
    hasPerm(perm) {
      const u = store.user;
      return !!(u && u.permissions && u.permissions.includes(perm));
    },
    hasAny(...perms) { return perms.some((p) => api.hasPerm(p)); },
  };

  window.DM = window.DM || {};
  window.DM.api = api;
  window.DM.store = store;
})();
