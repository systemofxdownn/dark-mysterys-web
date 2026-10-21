"""Verifica que la navegación se filtra por permisos (rol ESTUDIANTE)."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
errors = []

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))

    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(600)
    pg.fill("[name=identifier]", "MC03")   # María, Corvus, ESTUDIANTE
    pg.fill("[name=password]", "DarkMystery2024!")
    pg.click("[data-form=login] button[type=submit]")
    pg.wait_for_timeout(2500)

    nav = pg.eval_on_selector_all("[data-nav]", "els => els.map(e => e.getAttribute('data-nav'))")
    print("Nav visible para ESTUDIANTE:", nav)

    # El estudiante NO debe ver usuarios/auditoría/config
    forbidden = ["#/users", "#/audit", "#/config"]
    leaked = [f for f in forbidden if f in nav]
    print("Filtraciones de admin:", leaked or "(ninguna)")

    pg.screenshot(path="scripts/smoke_student.png")
    b.close()

print("Errores de página:", errors or "(ninguno)")
assert not leaked, f"El estudiante ve rutas restringidas: {leaked}"
assert not errors, errors
print("OK: navegación filtrada correctamente por permisos")
