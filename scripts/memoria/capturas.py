"""Captura las pantallas de la plataforma para la memoria (Playwright + Microsoft Edge instalado).

Solo lectura: navega y muestra pantallas, no crea ni cierra movimientos.
Uso:  .venv/Scripts/python scripts/memoria/capturas.py  [--url http://localhost:8085]
"""
import argparse
import os

from playwright.sync_api import sync_playwright

SALIDA = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "memoria", "img")
CLAVE = "demo1234"


def entrar(pagina, base, email):
    r = pagina.request.post(f"{base}/api/sesion", data={"email": email, "clave": CLAVE})
    assert r.ok, r.text()


def foto(pagina, nombre, completa=False, espera=1500):
    pagina.wait_for_timeout(espera)
    pagina.screenshot(path=os.path.join(SALIDA, f"{nombre}.png"), full_page=completa)
    print("  ✓", nombre)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8085")
    base = p.parse_args().url
    os.makedirs(SALIDA, exist_ok=True)

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(channel="msedge")

        # ------------------------------------------------ celular
        movil = navegador.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                      is_mobile=True, has_touch=True, locale="es-CO")
        pg = movil.new_page()
        pg.goto(f"{base}/"); foto(pg, "01_inicio_sesion", completa=True)
        pg.goto(f"{base}/generador.html"); foto(pg, "02_generador_registro", completa=True, espera=2500)
        pg.goto(f"{base}/m/RCD-DEMO01"); foto(pg, "03_generador_estado_cerrado")
        pg.goto(f"{base}/m/RCD-DEMO04"); foto(pg, "04_generador_estado_rechazado", completa=True)
        pg.goto(f"{base}/api/publico/movimientos/RCD-DEMO01/certificado"); foto(pg, "05_certificado", completa=True)

        entrar(pg, base, "porteria@plantasur.demo")
        pg.goto(f"{base}/portero.html"); pg.wait_for_timeout(1200)
        pg.click("#simular")
        foto(pg, "06_portero_placa")
        pg.fill("#placa", "XYZ-123"); pg.click("#buscar"); foto(pg, "07_portero_movimientos", completa=True)
        pg.click("#continuar"); foto(pg, "08_portero_recibido", completa=True)
        pg.click("#a-rechazo"); foto(pg, "09_portero_rechazo", completa=True)

        entrar(pg, base, "conductor@transportes.demo")
        pg.goto(f"{base}/campo.html"); foto(pg, "10_campo_mapa", espera=4500)
        pg.evaluate("ver('viajes')"); foto(pg, "11_campo_viajes", completa=True)
        pg.evaluate("ver('datos')"); foto(pg, "12_campo_datos", completa=True, espera=2500)
        pg.evaluate("ver('registro')"); foto(pg, "13_campo_registro", completa=True, espera=2500)
        movil.close()

        # ------------------------------------------------ PC
        pc = navegador.new_context(viewport={"width": 1440, "height": 900}, locale="es-CO")
        pg = pc.new_page()
        entrar(pg, base, "admin@transportes.demo")
        pg.goto(f"{base}/admin.html#dashboard"); foto(pg, "20_admin_dashboard", completa=True, espera=3000)
        pg.goto(f"{base}/admin.html#seguimiento"); pg.reload(); foto(pg, "21_admin_seguimiento", espera=5000)
        pg.goto(f"{base}/admin.html#control"); pg.reload(); pg.wait_for_timeout(4000)
        pg.evaluate("""() => document.querySelectorAll('.leaflet-control-layers-overlays label').forEach(l => {
            const i = l.querySelector('input');
            if (/Comunas \\(WMS|Capa normativa \\(WMS/.test(l.textContent) && !i.checked) i.click();
            if (/Receptores y zonas/.test(l.textContent) && i.checked) i.click(); })""")
        foto(pg, "22_admin_control_wms", espera=5000)
        pg.goto(f"{base}/admin.html#geocercas"); pg.reload(); foto(pg, "23_admin_geocercas", espera=5000)
        pg.goto(f"{base}/admin.html#movimientos"); pg.reload(); foto(pg, "24_admin_movimientos", espera=2500)
        pg.goto(f"{base}/admin.html#flota"); pg.reload(); foto(pg, "25_admin_flota", espera=2000)
        pc.close()
        navegador.close()


if __name__ == "__main__":
    main()
