import os
import re
import sys
import time
import requests
import cv2
import pandas as pd
import mysql.connector
from mysql.connector import Error
from PIL import Image
from pyzbar.pyzbar import decode
from bs4 import BeautifulSoup
from collections import Counter
import urllib3

# Suprimir advertencias de SSL al hacer requests al SAES
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ═══════════════════════════════════════════════════════════════
# CONSTANTES Y PATRONES
# ═══════════════════════════════════════════════════════════════
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}
PATRON_BOLETA = re.compile(r'(\d{10})')

# FIX #1 — el patrón original \d[A-Z]{2}\d solo capturaba grupos hasta XTM9.
# Ahora \d+ al final permite 2TM10, 2TM15, 2TM20, etc.
PATRON_GRUPO = re.compile(r'\b(\d[A-Z]{2}\d+)\b')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# ═══════════════════════════════════════════════════════════════
# BASE DE DATOS — leer tipo de semestre (1=impar, 2=par)
# ═══════════════════════════════════════════════════════════════

CONTRA_DB = "P3l0n100j0t3$"   # Misma contraseña que en Admin.py

def obtener_tipo_semestre():
    """
    Consulta la base de datos 'Semestre', tabla 'semestre', columna 'semestre'.
    Retorna:
        1  → semestre impar  (grupos válidos: 1, 3, 5)
        2  → semestre par    (grupos válidos: 2, 4, 6)
        0  → no se pudo leer (modo sin filtro)
    """
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=CONTRA_DB,
            database="Semestre"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT semestre FROM semestre LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            tipo = int(row[0])
            if tipo in (1, 2):
                nombre = "IMPAR (1°, 3°, 5°)" if tipo == 1 else "PAR (2°, 4°, 6°)"
                print(f"🗓️  Tipo de semestre detectado: {tipo} → {nombre}")
                return tipo

        print("⚠️  No se encontró tipo de semestre en la BD.  Se usará modo sin filtro.")
        return 0

    except Error as e:
        print(f"⚠️  No se pudo conectar a la BD Semestre: {e}")
        print("    → Se continuará SIN filtro de semestre par/impar.")
        return 0


# ═══════════════════════════════════════════════════════════════
# FUNCIONES DE PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

def decodificar_qr(ruta_imagen):
    """Intenta decodificar el QR con protección contra archivos corruptos."""
    try:
        # 1. Intentar primero con PIL (más estable para evitar segmentation faults)
        imagen_pil = Image.open(ruta_imagen)
        imagen_pil.verify()  # Verifica que no esté corrupta a nivel de bits

        # Volver a abrir porque verify() cierra el puntero del archivo
        imagen_pil = Image.open(ruta_imagen)
        qr_codes = decode(imagen_pil)
        if qr_codes:
            return qr_codes[0].data.decode('utf-8')

    except Exception:
        pass  # Si PIL falla o la imagen está corrupta, intentamos con OpenCV

    try:
        # 2. Fallback con OpenCV
        imagen = cv2.imread(ruta_imagen)
        if imagen is not None and imagen.size > 0:
            qr_codes = decode(imagen)
            if qr_codes:
                return qr_codes[0].data.decode('utf-8')
    except Exception:
        pass

    return None


def es_enlace_saes(url):
    return 'saes' in url.lower() or 'validahorario' in url.lower()


def extraer_grupos_de_horario(soup):
    """
    Extrae los grupos del horario SAES del alumno.

    FIX #2 — Se ignoran filas donde alguna celda contenga 'RECURSANDO'
    (materias en recurse pertenecen a otro semestre y no deben contar
    para determinar el grupo original del alumno).
    """
    grupos = []
    for tabla in soup.find_all('table'):
        for fila in tabla.find_all('tr')[1:]:
            celdas = fila.find_all(['th', 'td'])
            if len(celdas) < 2:
                continue

            # ── FIX #2: saltar fila si cualquier celda menciona RECURSANDO ──
            texto_fila = fila.get_text()
            if 'RECURSANDO' in texto_fila.upper():
                continue  # Esta materia es de recurse → no cuenta

            # ── FIX #1: ahora el regex captura también 2TM10, 2TM15, etc. ──
            match = PATRON_GRUPO.search(celdas[0].get_text().strip())
            if match:
                grupos.append(match.group(1))

    return grupos


def determinar_grupo_original(grupos, tipo_semestre=0):
    """
    Determina el grupo original de un alumno a partir de sus grupos de horario.

    FIX #3 — Se filtra por tipo de semestre activo:
        tipo_semestre = 1 → solo se consideran grupos de semestres 1, 3 y 5
        tipo_semestre = 2 → solo se consideran grupos de semestres 2, 4 y 6
        tipo_semestre = 0 → sin filtro (fallback si no se pudo leer la BD)

    Dentro de los grupos válidos, se elige el semestre más alto y
    el grupo más frecuente en ese semestre.
    Si hay empate → Casos_curiosos.
    """
    if not grupos:
        return "Casos_curiosos"

    # FIX #3: filtrar por semestre par o impar según corresponda
    semestres_validos = {
        1: {1, 3, 5},   # impar
        2: {2, 4, 6},   # par
    }

    if tipo_semestre in semestres_validos:
        grupos_filtrados = [
            g for g in grupos
            if g[0].isdigit() and int(g[0]) in semestres_validos[tipo_semestre]
        ]
        # Si el filtro dejó algo, trabajar con eso; si no, volver a la lista original
        if grupos_filtrados:
            grupos = grupos_filtrados
        else:
            # Ningún grupo coincide con el semestre activo → caso curioso
            return "Casos_curiosos"

    # Buscar el semestre más alto entre los grupos válidos
    semestres = [int(g[0]) for g in grupos if g[0].isdigit()]
    if not semestres:
        return "Casos_curiosos"

    semestre_max = max(semestres)
    grupos_semestre_max = [g for g in grupos if int(g[0]) == semestre_max]

    if not grupos_semestre_max:
        return "Casos_curiosos"

    # Elegir el más frecuente; si hay empate → Casos_curiosos
    conteo = Counter(grupos_semestre_max)
    max_frecuencia = max(conteo.values())
    grupos_max = [g for g, f in conteo.items() if f == max_frecuencia]

    return grupos_max[0] if len(grupos_max) == 1 else "Casos_curiosos"


def limpiar_ruta(ruta):
    return ruta.strip().strip("'").strip('"')


# ═══════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║  PROCESADOR DE QRs SAES → GRUPO ORIGINAL (LIA)      ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    # ── 0. Leer tipo de semestre desde la BD ──────────────────────────────────
    tipo_semestre = obtener_tipo_semestre()

    # 1. Pedir rutas
    ruta_excel = limpiar_ruta(input("\n📄 Arrastra aquí tu archivo Excel (.xlsx) y presiona Enter:\n> "))
    if not os.path.isfile(ruta_excel):
        print(f"\n❌ Error: No se encontró el archivo exacto en: {ruta_excel}")
        return

    carpeta_qrs = limpiar_ruta(input("\n📂 Arrastra aquí la CARPETA con los QRs y presiona Enter:\n> "))
    if not os.path.isdir(carpeta_qrs):
        print(f"\n❌ Error: No se encontró la carpeta en: {carpeta_qrs}")
        return

    # 2. Cargar Excel
    print("\n📊 Cargando Excel...")
    try:
        df = pd.read_excel(ruta_excel)
    except Exception as e:
        print(f"❌ Error leyendo el Excel: {e}")
        return

    col_boleta = next((c for c in df.columns if c.strip().lower() == 'boleta'), None)
    if not col_boleta:
        print("❌ El Excel no tiene una columna llamada 'Boleta'")
        return

    df[col_boleta] = df[col_boleta].astype(str).str.strip()
    df['Grupo original'] = ''

    # Ordenar archivos para que siempre se procesen en el mismo orden
    archivos = sorted([f for f in os.listdir(carpeta_qrs) if f.split('.')[-1].lower() in ALLOWED_EXTENSIONS])
    print(f"📷 {len(archivos)} imágenes encontradas. Procesando...\n")

    resultados = {}

    # 3. Procesar QRs
    for idx, archivo in enumerate(archivos, 1):
        boleta_match = PATRON_BOLETA.search(archivo)
        if not boleta_match:
            continue

        boleta = boleta_match.group(1)

        # Sanitizar nombre del archivo para que la terminal no crashee
        nombre_seguro = archivo.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
        print(f"[{idx}/{len(archivos)}] 🔍 Leyendo: {nombre_seguro}...", end=" ", flush=True)

        ruta_img = os.path.join(carpeta_qrs, archivo)
        url = decodificar_qr(ruta_img)

        if url and es_enlace_saes(url):
            # SISTEMA DE REINTENTOS PARA EL SAES
            max_reintentos = 3
            exito = False

            for intento in range(max_reintentos):
                try:
                    resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)

                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.content, 'html.parser')
                        grupos = extraer_grupos_de_horario(soup)
                        resultados[boleta] = determinar_grupo_original(grupos, tipo_semestre)
                        print(f"✅ {boleta} → {resultados[boleta]}")
                        exito = True
                        break
                    else:
                        raise Exception(f"Status code: {resp.status_code}")

                except requests.exceptions.Timeout:
                    if intento < max_reintentos - 1:
                        print("⏳ SAES lento, reintentando...", end=" ", flush=True)
                        time.sleep(2)
                    else:
                        resultados[boleta] = "Casos_curiosos"
                        print(f"⚠️ SAES no respondió → Casos_curiosos")

                except Exception as e:
                    if intento < max_reintentos - 1:
                        print("🔄 Error de conexión, reintentando...", end=" ", flush=True)
                        time.sleep(2)
                    else:
                        resultados[boleta] = "Casos_curiosos"
                        print(f"⚠️ Error definitivo → Casos_curiosos")

            if exito:
                time.sleep(0.5)  # Pausa normal si todo salió bien
        else:
            print(f"❌ QR ilegible o no es SAES")

    # 4. Guardar resultados
    print("\n📝 Guardando datos en el Excel...")
    for boleta, grupo in resultados.items():
        df.loc[df[col_boleta] == boleta, 'Grupo original'] = grupo

    ruta_salida = os.path.join(os.path.dirname(ruta_excel), 'QR_procesado_oficial.xlsx')
    try:
        df.to_excel(ruta_salida, index=False)
        print(f"🎉 ¡Proceso terminado! El nuevo archivo está en:\n{ruta_salida}")
    except Exception as e:
        print(f"❌ Error al guardar el Excel: {e}")


if __name__ == '__main__':
    main()