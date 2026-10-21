"""Captura de pantallas de las vistas principales (para documentación)."""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = "docs/screenshots"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)

    # Login
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(1000)
    pg.screenshot(path=f"{OUT}/01-login.png")

    # Login como Dirección
    pg.fill("[name=identifier]", "DN01")
    pg.fill("[name=password]", "DarkMystery2024!")
    pg.click("[data-form=login] button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{OUT}/02-dashboard.png")

    views = [
        ("#/scoreboard", "03-scoreboard"),
        ("#/bank", "04-banco"),
        ("#/bank/accounts", "05-cuentas"),
        ("#/shop", "06-tienda"),
        ("#/points", "07-copa-puntos"),
        ("#/calendar", "08-calendario"),
        ("#/partis", "09-partis"),
        ("#/users", "10-usuarios"),
        ("#/config", "11-config"),
        ("#/profile", "12-perfil"),
    ]
    for route, name in views:
        pg.evaluate(f"location.hash = '{route}'")
        pg.wait_for_timeout(1100)
        pg.screenshot(path=f"{OUT}/{name}.png")
        print("capturado", name)

    b.close()
print("Listo:", OUT)
