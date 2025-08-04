import os
import json
import gspread
import time
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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

def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    return driver

def buscar_y_extraer(driver, palabra):
    print(f"🔎 Buscando: {palabra}")
    resultados = []
    try:
        driver.get(BASE_URL)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "textoBusqueda")))
        input_busqueda = driver.find_element(By.ID, "textoBusqueda")
        input_busqueda.clear()
        input_busqueda.send_keys(palabra)
        input_busqueda.send_keys(Keys.ENTER)

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "lic-block-body")))
        time.sleep(2)
        tarjetas = driver.find_elements(By.CLASS_NAME, "lic-block-body")

        for tarjeta in tarjetas:
            try:
                enlace = tarjeta.find_element(By.CSS_SELECTOR, "a")
                onclick = enlace.get_attribute("onclick")
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

                driver.execute_script("window.open(arguments[0]);", link_ficha)
                driver.switch_to.window(driver.window_handles[1])

                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(1)

                def extraer(id):
                    try:
                        return driver.find_element(By.ID, id).text.strip()
                    except NoSuchElementException:
                        return ""

                titulo = extraer("lblNombreLicitacion")
                descripcion = extraer("lblFicha1Descripcion")
                fecha_publicacion = extraer("lblFicha3Publicacion")
                fecha_cierre = extraer("lblFicha3Cierre")
                fecha_apertura = extraer("lblFicha3ActoAperturaTecnica")
                fecha_visita = extraer("lblFicha3Visita")
                obligatoria = "Sí" if fecha_visita else "No aparece en ficha"
                tipo_monto = extraer("lblFicha7TituloMontoEstimado") or "NO PUBLICO"
                monto = extraer("lblFicha7MontoEstimado") or "NF"

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

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

def ejecutar_scraping(fecha_objetivo, palabras):
    driver = iniciar_driver()
    resultados_totales = []

    for palabra in palabras:
        resultados = buscar_y_extraer(driver, palabra)
        resultados_totales.extend(resultados)

    driver.quit()
    return resultados_totales
