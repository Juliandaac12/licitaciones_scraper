import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

SPREADSHEET_ID = "1TqiNXXAgfKlSu2b_Yr9r6AdQU_WacdROsuhcHL0i6Mk"

def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)

def cargar_palabras_clave(sheet):
    try:
       hoja = sheet.worksheet("Palabras Clave")
       palabras_raw = hoja.col_values(6)[7:]  # Columna F (6), desde fila 8 (índice 7)
       palabras_clave = [p.strip() for p in palabras_raw if p.strip()]
       print(f"🔑 {len(palabras_clave)} palabras clave cargadas desde Google Sheets.")
       return palabras_clave

    except Exception as e:
        print(f"❌ Error al cargar palabras clave: {e}")
        return []

def guardar_en_hoja(resultados, fecha_objetivo):
    if not resultados:
        print("⚠️ No hay resultados para guardar.")
        return

    mes = datetime.strptime(fecha_objetivo, "%Y-%m-%d").strftime("%B").capitalize()
    sheet = conectar_google_sheets()

    columnas_ordenadas = [
        "Número", "FyH Extracción", "FyH Publicación", "ID", "Título",
        "Descripción", "Tipo", "Monto", "Tipo Monto",
        "LINK FICHA", "FyH TERRENO", "OBLIG?", "FyH CIERRE"
    ]

    df_nuevo = pd.DataFrame(resultados)

    try:
        hoja = sheet.worksheet(mes)
        data_existente = hoja.get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        hoja = sheet.add_worksheet(title=mes, rows="1000", cols="20")
        hoja.append_row(columnas_ordenadas)
        data_existente = []

    ultimo_numero = int(data_existente[-1]["Número"]) if data_existente else 0
    ids_existentes = set(row["ID"] for row in data_existente)

    df_nuevo = df_nuevo[~df_nuevo["id"].isin(ids_existentes)]

    if df_nuevo.empty:
        print("📄 No hay nuevas licitaciones para agregar (todas ya existen en la hoja).")
        return

    df_nuevo["Número"] = range(ultimo_numero + 1, ultimo_numero + 1 + len(df_nuevo))
    df_nuevo["FyH Extracción"] = df_nuevo["fecha_extraccion"]
    df_nuevo["FyH Publicación"] = df_nuevo["fecha_publicacion"]
    df_nuevo["ID"] = df_nuevo["id"]
    df_nuevo["Título"] = df_nuevo["titulo"]
    df_nuevo["Descripción"] = df_nuevo["descripcion"]
    df_nuevo["Tipo"] = df_nuevo["tipo"]
    df_nuevo["Monto"] = df_nuevo["monto"]
    df_nuevo["Tipo Monto"] = df_nuevo["tipo_monto"]
    df_nuevo["LINK FICHA"] = df_nuevo["link_ficha"]
    df_nuevo["FyH TERRENO"] = df_nuevo["fecha_visita"]
    df_nuevo["OBLIG?"] = df_nuevo["visita_obligatoria"]
    df_nuevo["FyH CIERRE"] = df_nuevo["fecha_cierre"]

    df_nuevo = df_nuevo[columnas_ordenadas]

    hoja.append_rows(df_nuevo.values.tolist(), value_input_option="USER_ENTERED")
    print(f"✅ {len(df_nuevo)} nuevas licitaciones guardadas en la hoja '{mes}'")
