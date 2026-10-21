"""Smoke test de UI con Playwright: carga la SPA, inicia sesión y navega.

Uso:
    python scripts/smoke_ui.py [base_url]
"""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
IDENT = "DN01"
PWD = "DarkMystery2024!"

errors = []
console = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.on("console", lambda m: console.append((m.type, m.text)))
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1) Cargar login
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_timeout(800)
        print("TITLE:", page.title())
        assert page.query_selector("[data-form=login]"), "No se renderizó el formulario de login"
        print("OK: login renderizado")

        # 2) Iniciar sesión
        page.fill("[name=identifier]", IDENT)
        page.fill("[name=password]", PWD)
        page.click("[data-form=login] button[type=submit]")
        page.wait_for_timeout(2500)
        print("HASH tras login:", page.evaluate("location.hash"))
        assert page.query_selector(".app-shell"), "No se montó el shell tras login"
        print("OK: shell montado (dashboard)")

        # 3) Navegar por las vistas principales
        routes = [
            "#/scoreboard", "#/calendar", "#/bank", "#/bank/accounts",
            "#/shop", "#/shop/purchases", "#/points", "#/events",
            "#/partis", "#/users", "#/reports", "#/audit", "#/config", "#/profile",
        ]
        for r in routes:
            page.evaluate(f"location.hash = '{r}'")
            page.wait_for_timeout(900)
            shell = page.query_selector(".app-shell")
            content = page.query_selector(".content")
            has = bool(content and content.inner_text().strip())
            status = "OK" if (shell and has) else "VACIO/ERROR"
            print(f"  {status:10s} {r}")

        # 4) Verificar footer requerido
        body = page.inner_text("body")
        assert "POWERED BY" in body.upper(), "Falta el footer POWERED BY"
        assert "ZETA LESTRANGE" in body.upper(), "Falta ZETA LESTRANGE"
        print("OK: footer 'POWERED BY: ZETA LESTRANGE' presente")

        page.screenshot(path="scripts/smoke_dashboard.png", full_page=False)
        browser.close()

    print("\n=== ERRORES DE PÁGINA ===")
    if errors:
        for e in errors:
            print("  ERR:", e)
    else:
        print("  (ninguno)")

    print("\n=== CONSOLA (warn/error) ===")
    for t, m in console:
        if t in ("error", "warning"):
            print(f"  [{t}] {m}")
    print("  (fin)")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
