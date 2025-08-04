import os
import json
import gspread
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import undetected_chromedriver as uc

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
        palabras_raw = hoja.col_values(2)[8:]  # Columna B (índice 2), desde fila 9 (índice 8)
        palabras_clave = [p.strip() for p in palabras_raw if p.strip()]
        print(f"🔑 {len(palabras_clave)} palabras clave cargadas desde Google Sheets.")
        return palabras_clave
    except Exception as e:
        print(f"❌ Error al cargar palabras clave: {e}")
        return []

def iniciar_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless")  # Ejecuta sin interfaz gráfica
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    driver = uc.Chrome(options=options)
    return driver

    return webdriver.Chrome(options=options)

def buscar_y_extraer(driver, palabra, fecha_objetivo):
    print(f"🔎 Buscando: {palabra}")
    resultados = []

    try:
        driver.get(BASE_URL)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "textoBusqueda")))
        input_busqueda = driver.find_element(By.ID, "textoBusqueda")
        input_busqueda.clear()
        input_busqueda.send_keys(palabra)
        input_busqueda.send_keys(Keys.ENTER)

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "lic-block-body")))
        time.sleep(2)

        tarjetas = driver.find_elements(By.CLASS_NAME, "lic-block-body")

        for tarjeta in tarjetas:
            try:
                onclick = tarjeta.find_element(By.CSS_SELECTOR, "a").get_attribute("onclick")
                if "DetailsAcquisition.aspx?" not in onclick:
                    continue

                start = onclick.find("DetailsAcquisition.aspx?")
                qs = onclick[start:].split("'")[0]
                link_ficha = "https://www.mercadopublico.cl/Procurement/Modules/RFB/" + qs
                id_real = qs.split("idlicitacion=")[-1].strip()

                if not any(tipo in id_real for tipo in ["LE", "LP", "LQ", "LR"]):
                    continue

                if "LE" in id_real:
                    tipo = "100-1000 UTM"
                elif "LP" in id_real:
                    tipo = "1000-2000 UTM"
                elif "LQ" in id_real:
                    tipo = "2000-5000 UTM"
                elif "LR" in id_real:
                    tipo = "5000+ UTM"
                else:
                    tipo = ""

                driver.execute_script("window.open(arguments[0]);", link_ficha)
                driver.switch_to.window(driver.window_handles[1])
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(2)

                try:
                    titulo = driver.find_element(By.ID, "lblNombreLicitacion").text.strip()
                except:
                    titulo = ""

                try:
                    descripcion = driver.find_element(By.ID, "lblFicha1Descripcion").text.strip()
                except:
                    descripcion = ""

                try:
                    fecha_publicacion = driver.find_element(By.ID, "lblFicha3Publicacion").text.strip()
                except:
                    fecha_publicacion = ""

                try:
                    fecha_cierre = driver.find_element(By.ID, "lblFicha3Cierre").text.strip()
                except:
                    fecha_cierre = ""

                try:
                    fecha_apertura = driver.find_element(By.ID, "lblFicha3ActoAperturaTecnica").text.strip()
                except:
                    fecha_apertura = ""

                try:
                    fecha_visita = driver.find_element(By.ID, "lblFicha3Visita").text.strip()
                    obligatoria = "Sí" if fecha_visita else "No aparece en ficha"
                except:
                    fecha_visita = "No disponible"
                    obligatoria = "No aparece en ficha"

                try:
                    tipo_monto = driver.find_element(By.ID, "lblFicha7TituloMontoEstimado").text.strip()
                except:
                    tipo_monto = "NO PUBLICO"

                try:
                    monto = driver.find_element(By.ID, "lblFicha7MontoEstimado").text.strip()
                except:
                    monto = "NF"

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
        resultados = buscar_y_extraer(driver, palabra, fecha_objetivo)
        resultados_totales.extend(resultados)

    driver.quit()
    return resultados_totales
