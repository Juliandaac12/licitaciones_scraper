import os
import json
import gspread
import asyncio
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from playwright.async_api import async_playwright

BASE_URL = "https://www.mercadopublico.cl/BuscarLicitacion"
SPREADSHEET_ID = "1TqiNXXAgfKlSu2b_Yr9r6AdQU_WacdROsuhcHL0i6Mk"

def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    print("✅ Conexión con Google Sheets exitosa")
    return client.open_by_key(SPREADSHEET_ID)

def cargar_palabras_clave(sheet):
    try:
        hoja = sheet.worksheet("Palabras Clave")
        palabras_raw = hoja.col_values(2)[8:]  # Columna B desde fila 9
        palabras_clave = [p.strip() for p in palabras_raw if p.strip()]
        print(f"🔑 {len(palabras_clave)} palabras clave cargadas desde Google Sheets.")
        return palabras_clave
    except Exception as e:
        print(f"❌ Error al cargar palabras clave: {e}")
        return []

async def buscar_y_extraer(page, palabra):
    print(f"🔎 Buscando: {palabra}")
    resultados = []

    try:
        await page.goto(BASE_URL)
        await page.fill("#textoBusqueda", palabra)
        await page.keyboard.press("Enter")
        await page.wait_for_selector(".lic-block-body")
        tarjetas = await page.query_selector_all(".lic-block-body")

        for tarjeta in tarjetas:
            try:
                enlace = await tarjeta.query_selector("a")
                onclick = await enlace.get_attribute("onclick")
                if not onclick or "DetailsAcquisition.aspx?" not in onclick:
                    continue

                start = onclick.find("DetailsAcquisition.aspx?")
                qs = onclick[start:].split("'")[0]
                link_ficha = "https://www.mercadopublico.cl/Procurement/Modules/RFB/" + qs
                id_real = qs.split("idlicitacion=")[-1].strip()

                if not any(tipo in id_real for tipo in ["LE", "LP", "LQ", "LR"]):
                    continue

                tipo = {
                    "LE": "100-1000 UTM",
                    "LP": "1000-2000 UTM",
                    "LQ": "2000-5000 UTM",
                    "LR": "5000+ UTM"
                }.get(id_real[:2], "")

                ficha = await page.context.new_page()
                await ficha.goto(link_ficha)
                await ficha.wait_for_selector("body")

                def extraer(id):
                    return ficha.locator(f"#{id}").text_content().catch(lambda _: "")

                titulo = await extraer("lblNombreLicitacion")
                descripcion = await extraer("lblFicha1Descripcion")
                fecha_publicacion = await extraer("lblFicha3Publicacion")
                fecha_cierre = await extraer("lblFicha3Cierre")
                fecha_apertura = await extraer("lblFicha3ActoAperturaTecnica")
                fecha_visita = await extraer("lblFicha3Visita")
                obligatoria = "Sí" if fecha_visita else "No aparece en ficha"
                tipo_monto = await extraer("lblFicha7TituloMontoEstimado") or "NO PUBLICO"
                monto = await extraer("lblFicha7MontoEstimado") or "NF"

                await ficha.close()

                resultados.append({
                    "palabra": palabra,
                    "fecha_extraccion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "fecha_publicacion": fecha_publicacion,
                    "id": id_real,
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "tipo": tipo,
                    "monto": monto,
                    "tipo_monto": tipo_monto,
                    "link_ficha": link_ficha,
                    "fecha_visita": fecha_visita,
                    "visita_obligatoria": obligatoria,
                    "fecha_cierre": fecha_cierre,
                    "fecha_apertura": fecha_apertura
                })

            except Exception as e:
                print(f"⚠️ Error en tarjeta individual: {e}")

    except Exception as e:
        print(f"❌ Error general en búsqueda: {e}")

    return resultados

async def ejecutar_scraping(fecha_objetivo, palabras):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        resultados_totales = []
        for palabra in palabras:
            resultados = await buscar_y_extraer(page, palabra)
            resultados_totales.extend(resultados)

        await browser.close()
        return resultados_totales