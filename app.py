from flask import request, redirect, Flask, Response, render_template, jsonify, url_for, flash, session
import threading
import numpy as np
import pygame
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, date
import mysql.connector
from mysql.connector import Error
import random
import socket
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import json
import os
import urllib.parse
import base64

def cifrar_texto(texto):
    # Cifrado sencillo y eficiente
    clave = "L1A_K3Y"
    cifrado = "".join(chr(ord(c) ^ ord(clave[i % len(clave)])) for i, c in enumerate(texto))
    return base64.b64encode(cifrado.encode('utf-8')).decode('utf-8')

def descifrar_texto(texto_cifrado):
    clave = "L1A_K3Y"
    try:
        descifrado_b64 = base64.b64decode(texto_cifrado.encode('utf-8')).decode('utf-8')
        return "".join(chr(ord(c) ^ ord(clave[i % len(clave)])) for i, c in enumerate(descifrado_b64))
    except Exception:
        return ""
#Debe de salir
# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

contra_db = "P3l0n100j0t3$"

# CONFIGURACIÓN ESP32 CON IP PÚBLICA
ESP32_IP = "201.66.195.11"  # ← TU IP PÚBLICA DEL ESP32
ESP32_PORT = 80

# LISTA DE ADMINS (Boletas que saltan el límite diario y restricciones de horario)
ADMIN_BOLETAS = ["2024160385","2024160324"] # Reemplaza o agrega las que necesites



# ESTADO GLOBAL PARA EL MONITOR DIVIDIDO (MEMORIA RAM)
# Esto permite que el HTML se actualice sin consultar la DB constantemente
datos_accesos = {
    "izquierda": {
        "nombre": "Esperando...",
        "mensaje": "Carril Izquierdo Habilitado",
        "foto": "/static/img/placeholder.png", 
        "color": "gray", # gray, green, red
        "timestamp": 0
    },
    "derecha": {
        "nombre": "Esperando...",
        "mensaje": "Carril Derecho Habilitado",
        "foto": "/static/img/placeholder.png",
        "color": "gray",
        "timestamp": 0
    }
}

print("\n" + "="*70)
print("🔧 CONFIGURACIÓN DEL SISTEMA")
print("="*70)
print(f"📍 IP Pública ESP32: {ESP32_IP}")
print(f"📡 Puerto ESP32: {ESP32_PORT}")
print("="*70)


# ============================================================================
# CLASE DE CONEXIÓN ESP32 WIFI - VERSIÓN PARA IP PÚBLICA
# ============================================================================

class ConexionESP32:
    """
    Clase para comunicación WiFi con ESP32 usando IP pública
    """
    def __init__(self, esp_ip=ESP32_IP, esp_port=ESP32_PORT, timeout=10):
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.timeout = timeout
        self.conectado = False
        self.session = requests.Session()
        
        # Configurar reintentos para conexiones inestables
        retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        
        self.verificar_conexion_inicial()

    def verificar_conexion_inicial(self):
        """Verifica si el ESP32 es alcanzable al inicio"""
        try:
            print(f"📡 Intentando conectar con ESP32 en http://{self.esp_ip}:{self.esp_port}...")
            # Un ping simple a la raíz o un endpoint de estado
            response = self.session.get(f"http://{self.esp_ip}:{self.esp_port}/", timeout=3)
            if response.status_code == 200:
                self.conectado = True
                print("✅ ESP32 Conectado exitosamente")
            else:
                print(f"⚠️ ESP32 respondió con código: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ No se pudo conectar con ESP32: {e}")
            self.conectado = False

    def enviar_comando(self, comando):
        """
        Envía un comando al ESP32 para abrir torniquete
        comando: '1' para izquierda, '2' para derecha (según tu configuración)
        """
        if not self.conectado:
            # Intentar reconexión rápida
            try:
                requests.get(f"http://{self.esp_ip}:{self.esp_port}/", timeout=1)
                self.conectado = True
            except:
                print("❌ ESP32 sigue desconectado, no se envió comando")
                return False

        try:
            # Enviar comando al endpoint correspondiente
            # Asumiendo que el ESP32 espera /abrir?cmd=1 o similar, o ruta directa /1
            # Ajusta esta URL según tu código de Arduino/ESP32
            url = f"http://{self.esp_ip}:{self.esp_port}/{comando}" 
            print(f"📤 Enviando señal a: {url}")
            response = self.session.get(url, timeout=2)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error enviando comando al ESP32: {e}")
            self.conectado = False
            return False



# ============================================================================
# FUNCIÓN DE PRUEBA DE CONEXIÓN
# ============================================================================

def probar_conexion_esp32():
    """Prueba la conexión con el ESP32"""
    print("\n" + "="*60)
    print("🧪 PRUEBA DE CONEXIÓN CON ESP32")
    print("="*60)
    
    print(f"🔍 Probando conexión a {ESP32_IP}:{ESP32_PORT}...")
    
    try:
        # Crear socket de prueba
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(5)
        
        # Intentar conectar
        resultado = test_socket.connect_ex((ESP32_IP, ESP32_PORT))
        
        if resultado == 0:
            print("✅ Conexión TCP exitosa")
            
            # Intentar leer mensaje
            try:
                test_socket.settimeout(2)
                mensaje = test_socket.recv(1024).decode(errors="ignore")
                if mensaje:
                    print(f"📡 Mensaje del ESP32: {mensaje}")
            except socket.timeout:
                print("ℹ️ No se recibió mensaje (puede ser normal)")
            
            test_socket.close()
            
            # Probar comunicación completa
            print("\n🔍 Probando comunicación completa...")
            esp_test = ConexionESP32(esp_ip=ESP32_IP, esp_port=ESP32_PORT)
            if esp_test.conectar():
                if esp_test.enviar_comando(2):
                    print("✅ Comunicación funcionando correctamente")
                esp_test.desconectar()
                return True
            else:
                print("❌ No se pudo establecer comunicación completa")
                return False
        else:
            print(f"❌ No se pudo conectar (código error: {resultado})")
            test_socket.close()
            return False
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

# ============================================================================
# INICIALIZACIÓN DE LA CONEXIÓN ESP32
# ============================================================================

print(f"\n🔌 Inicializando conexión con ESP32...")
esp32 = ConexionESP32(esp_ip=ESP32_IP, esp_port=ESP32_PORT)

# Probar conexión
if probar_conexion_esp32():
    print(f"\n✅ ESP32 detectado y funcionando en {ESP32_IP}:{ESP32_PORT}")
    if esp32.conectar():
        print("✅ Conexión establecida correctamente")
    else:
        print("⚠️ Problemas con la conexión completa")
        esp32 = None
else:
    print(f"\n❌ No se pudo conectar con el ESP32")
    print("⚠️ El sistema funcionará sin control de torniquete")
    esp32 = None

def get_with_retries(url, headers, retries=3, backoff=2, timeout=20):
    """Hace petición HTTP con reintentos automáticos"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session.get(url, headers=headers, timeout=timeout)


# Instancia global del ESP32
esp32 = ConexionESP32()

# ============================================================================
# LÓGICA DE PROCESAMIENTO DUAL (CON TUS REGLAS PERSONALIZADAS)
# ============================================================================



def procesar_entrada_dual(url_codigo, es_lado_izquierdo):
    """
    Procesa QR, determina permisos y DEFINE EL ESTILO VISUAL para el HTML.
    """
    lado_key = "izquierda" if es_lado_izquierdo else "derecha"
    comando_esp = "2" if es_lado_izquierdo else "3"
    
    print(f"\n🔄 [PROCESANDO {lado_key.upper()}] Código recibido...")
    print(f"🔗 URL: {url_codigo}...")

    # --- 1. EXTRACCIÓN Y VERIFICACIÓN ---
    try:
        # Llamamos al verificador pasando el lado para que sepa qué torniquete abrir
        resultado = verificador.procesar_qr(
            url_codigo, 
            solo_verificar=False,  # Sí queremos abrir torniquete
            lado_izquierdo=es_lado_izquierdo  # Nuevo parámetro
        )
        
        acceso_concedido = resultado.get('puede_entrar', False)
        nombre_alumno = resultado.get('nombre', 'Desconocido')
        mensaje_estado = resultado.get('mensaje', 'Procesando...')
        foto_url = resultado.get('foto', '/static/images/placeholder.png')
        boleta = str(resultado.get('boleta', ''))
        
    except Exception as e:
        print(f"❌ Error en verificador: {e}")
        import traceback
        traceback.print_exc()
        acceso_concedido = False
        nombre_alumno = "Error Sistema"
        mensaje_estado = f"Fallo en verificación: {str(e)}"
        foto_url = ""
        boleta = ""

    # --- 2. DETERMINAR ESTILO VISUAL ---
    estilo_css = "inscrito-inactivo"
    titulo_tarjeta = "Acceso Denegado"
    mensaje_mochila = "Comunícate con personal"

    # A) ADMINISTRATIVOS Y GUARDIAS
    if "administrativo" in mensaje_estado.lower() or "personal administrativo" in mensaje_estado.lower():
        estilo_css = "master"
        titulo_tarjeta = "Acceso Administrativo"
        mensaje_mochila = "Bienvenid@"
        acceso_concedido = True

    elif "guardia" in mensaje_estado.lower() or "personal de guardia" in mensaje_estado.lower():
        estilo_css = "master"
        titulo_tarjeta = "Personal de Guardia"
        mensaje_mochila = "Bienvenid@"
        acceso_concedido = True

    # B) BOLETAS ESPECIALES
    elif boleta == "2024160324":
        estilo_css = "inscrito-LIA"
        titulo_tarjeta = "Integrante de LIA - Ebani"
        mensaje_mochila = "🔧 Lead Técnico -- Tester 💻"
    elif boleta == "2024160385":
        estilo_css = "inscrito-LIA"
        titulo_tarjeta = "Integrante de LIA - André"
        mensaje_mochila = "🔧 Lead Coder -- Backend -- GOD 💻"
    elif boleta == "2024160550":
        estilo_css = "inscrito-LIA"
        titulo_tarjeta = "Integrante de LIA - Mati"
        mensaje_mochila = "Matilolazo"
    elif boleta == "2024160383":
        estilo_css = "inscrito-LIA"
        titulo_tarjeta = "Integrante de LIA - Ashley"
        mensaje_mochila = "🔧 Tesis -- Tester 💻"
    elif boleta == "2024160344":
        estilo_css = "inscrito-LIA"
        titulo_tarjeta = "Integrante de LIA - Sofi"
        mensaje_mochila = "⚠️ Oye cuidado con los jojo's 🗣️🙏 ⚠️"
    elif boleta == "2024160095":
        estilo_css = "inscrito-LIA"
        titulo_tarjeta = "Integrante de LIA - Andrew"
        mensaje_mochila = "⚠️ El del saberes ⚠️"
    elif boleta == "2024160330":
        estilo_css = "inscrito-Especial"
        mensaje_mochila = "The cake is a lie"
    
    # C) ALUMNOS NORMALES
    elif acceso_concedido:
        estilo_css = "inscrito-activo"
        titulo_tarjeta = "Entrada Autorizada"
        mensaje_mochila = "Bienvenido de nuevo."
    else:
        if "suspendido" in mensaje_estado.lower():
            estilo_css = "inscrito-suspendido"
            titulo_tarjeta = "Cuenta Suspendida"
        elif "ya ingresó" in mensaje_estado.lower() or "bloqueada" in mensaje_estado.lower():
            estilo_css = "inscrito-inactivo"
            titulo_tarjeta = "Ya ingresaste"
            mensaje_mochila = "Solo una entrada por día"
        else:
            estilo_css = "inscrito-inactivo"
            titulo_tarjeta = "No puedes entrar"

    # --- 3. SONIDOS ---
    if acceso_concedido:
        try:
            pygame.mixer.Sound("static/sounds/success.wav").play()
        except:
            pass
    else:
        try:
            pygame.mixer.Sound("static/sounds/error.wav").play()
        except:
            pass

    # --- 4. ACTUALIZAR MEMORIA GLOBAL ---
    datos_accesos[lado_key] = {
        "boleta": boleta,
        "nombre": nombre_alumno,
        "mensaje": mensaje_estado,
        "foto": foto_url,
        "estilo": estilo_css,
        "titulo": titulo_tarjeta,
        "mochila": mensaje_mochila,
        "timestamp": time.time()
    }
    
    print(f"{'✅' if acceso_concedido else '❌'} [{lado_key.upper()}] {nombre_alumno} - {mensaje_estado}")
    
    return acceso_concedido





# ============================================================================
# SERVIDOR SOCKET PARA ESCÁNERES (SEGUNDO HILO)
# ============================================================================

def servidor_escaneres_background():
    HOST = '201.66.195.124'
    PORT = 65432
    
    print(f"🔄 Iniciando servicio de escucha de Escáneres en puerto {PORT}...")
    
    while True: # Bucle de reinicio por si el socket muere
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((HOST, PORT))
                s.listen()
                
                while True:
                    conn, addr = s.accept()
                    with conn:
                        data = conn.recv(4096)
                        if not data: continue
                        try:
                            # Decodificar mensaje de la Computadora A
                            mensaje = json.loads(data.decode('utf-8'))
                            
                            texto_url = mensaje.get('texto', '').strip()
                            
                            # --- NUEVA LÓGICA DE DETECCIÓN DE LADO ---
                            escaner_id = mensaje.get('escaner', '')
                            es_izq = (escaner_id == 'IZQ')
                            # -----------------------------------------
                            
                            if texto_url:
                                # Usar contexto de aplicación Flask para tener acceso a DB/Verificador
                                with app.app_context():
                                    procesar_entrada_dual(texto_url, es_izq)
                            
                        except json.JSONDecodeError:
                            print("⚠️ JSON corrupto recibido del escáner")
                        except Exception as e:
                            print(f"⚠️ Error procesando paquete: {e}")
        except Exception as e:
            print(f"❌ Error en servidor socket (reiniciando en 5s): {e}")
            time.sleep(5)


# Inicializar pygame para sonidos
try:
    pygame.mixer.init()
except:
    print("⚠️ No se pudo iniciar Pygame (sonidos desactivados)")


# ============================================================================
# CLASE PRINCIPAL DEL SISTEMA
# ============================================================================

class QRHorarioVerificador:
    def __init__(self, db_config=None, esp32_conexion=None):
        """Inicializa el verificador de horarios por QR para web"""
        self.lock = threading.Lock()
        self.running = True
        
        self.esp32 = esp32_conexion
        
        self.scanned_codes = []
        self.last_log_entries = []
        self.resultado_mochila_por_boleta = {}
        
        if db_config is None:
            self.db_config = {
                'host': 'localhost',
                'user': 'root',
                'password': contra_db
            }
        else:
            self.db_config = db_config
        
        self.dias_semana = {
            0: 'lunes',
            1: 'martes',
            2: 'miercoles',
            3: 'jueves',
            4: 'viernes',
            5: 'sabado',
            6: 'domingo'
        }
        
        self.bases_datos = bases_datos
        self._url_cache = {}
        self._indices_ordenados = {}
        
        self.audio_azteca()
        print("🔄 Inicializando sistema...")
    
    def audio_azteca(self):
        """Inicializa el sistema de audio"""
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.audio_activo = True
            print("✅ Sistema de audio inicializado")
        except Exception as e:
            print(f"❌ No se pudo inicializar el audio: {e}")
            self.audio_activo = False
    
    def sonidito(self, frecuencia=800, duracion=0.4):
        """Crea un sonido de beep programáticamente"""
        if not self.audio_activo:
            return None
            
        try:
            sample_rate = 22050
            frames = int(duracion * sample_rate)
            arr = np.zeros((frames, 2), dtype=np.int16)
            
            for i in range(frames):
                onda = int(4096 * np.sin(2 * np.pi * frecuencia * i / sample_rate))
                fade = min(i / (frames * 0.1), (frames - i) / (frames * 0.1), 1.0)
                arr[i] = [int(onda * fade), int(onda * fade)]
            
            return pygame.sndarray.make_sound(arr)
        except Exception as e:
            print(f"Error creando sonido: {e}")
            return None
    
    def play_success_sound(self):
        """Reproduce sonido de éxito"""
        if not self.audio_activo:
            return
        try:
            for freq in [600, 800, 1000]:
                beep = self.sonidito(freq, 0.15)
                if beep:
                    beep.play()
                    pygame.time.wait(120)
        except:
            print("\a\a\a")
    
    def play_error_sound(self):
        """Reproduce sonido de error"""
        if not self.audio_activo:
            return
        try:
            beep = self.sonidito(300, 0.5)
            if beep:
                beep.play()
        except:
            print("\a")
    
    def play_scan_sound(self):
        """Reproduce sonido de escaneo"""
        if not self.audio_activo:
            return
        try:
            beep = self.sonidito(700, 0.1)
            if beep:
                beep.play()
        except:
            print("\a")
    
    def es_enlace_dae(self, url):
        """Verifica si el enlace es de DAE credenciales"""
        patrones_dae = [
            r'servicios\.dae\.ipn\.mx.*vcred',
            r'.vcred/\?h=.',
            r'.dae.*cred.',
        ]
        return any(re.search(patron, url, re.IGNORECASE) for patron in patrones_dae)
    
    def es_enlace_saes(self, url):
        """Verifica si el enlace es del SAES (horario)"""
        patrones_saes = [
            r'saes.*horario',
            r'.saes.',
            r'.consultaHorario.'
        ]
        return any(re.search(patron, url, re.IGNORECASE) for patron in patrones_saes)
    
    def es_qr_administrativo(self, texto):
        """Verifica si es el QR de administrativos/servicio social"""
        patrones_admin = [
            r'administrativos',
            r'asuntos\s*externos'
        ]
        return any(re.search(patron, texto, re.IGNORECASE) for patron in patrones_admin)
    
    def es_qr_guardia(self, texto):
        """Verifica si es el QR de guardias/caseta"""
        patrones_guardia = [
            r'guardias',
            r'caseta',
            r'salida'
        ]
        return any(re.search(patron, texto, re.IGNORECASE) for patron in patrones_guardia)
    

    def precargar_indices_grupo(self, grupo):
            """Precarga y ordena los URLs (DAE y SAES) de un grupo para búsqueda binaria"""
            if grupo in self._indices_ordenados:
                return
            
            try:
                db_config_temp = self.db_config.copy()
                db_config_temp['database'] = grupo
                
                with mysql.connector.connect(**db_config_temp, connection_timeout=10) as connection:
                    with connection.cursor() as cursor:
                        # Precargar URLs DAE
                        query_dae = f"SELECT url_origen, boleta, nombre FROM {grupo} WHERE url_origen IS NOT NULL AND url_origen != '' ORDER BY url_origen"
                        cursor.execute(query_dae)
                        resultados_dae = cursor.fetchall()
                        
                        # Precargar URLs SAES (Nuevo)
                        query_saes = f"SELECT url_saes, boleta, nombre FROM {grupo} WHERE url_saes IS NOT NULL AND url_saes != '' ORDER BY url_saes"
                        cursor.execute(query_saes)
                        resultados_saes = cursor.fetchall()
                        
                        self._indices_ordenados[grupo] = {
                            "dae": resultados_dae,
                            "saes": resultados_saes
                        }
                        print(f"📊 Índices cargados para {grupo}: {len(resultados_dae)} DAE, {len(resultados_saes)} SAES")
                        
            except Error as e:
                print(f"⚠️ Error precargando índices de '{grupo}': {e}")



    
    def busqueda_binaria_url(self, urls_ordenados, url_buscado):
        """Búsqueda binaria en lista de URLs ordenados"""
        izq, der = 0, len(urls_ordenados) - 1
        
        while izq <= der:
            medio = (izq + der) // 2
            url_medio = urls_ordenados[medio][0]
            
            if url_medio == url_buscado:
                return urls_ordenados[medio]
            elif url_medio < url_buscado:
                izq = medio + 1
            else:
                der = medio - 1
        
        return None
    


    def buscar_alumno_por_url(self, url, tipo_enlace):
            """
            Búsqueda ultra-optimizada unificada para DAE o SAES.
            Maneja variaciones de http/https y decodificación de caracteres especiales (%2f, %3d)
            """
            if url in self._url_cache:
                print(f"⚡ Enlace {tipo_enlace.upper()} encontrado en cache")
                return self._url_cache[url]
            
            print(f"\n🔍 Buscando enlace {tipo_enlace.upper()}...")
            columna_db = "url_origen" if tipo_enlace == 'dae' else "url_saes"
            
            # 1. Búsqueda rápida en RAM (Búsqueda EXACTA)
            for grupo in self.bases_datos:
                if grupo in self._indices_ordenados and tipo_enlace in self._indices_ordenados[grupo]:
                    resultado = self.busqueda_binaria_url(self._indices_ordenados[grupo][tipo_enlace], url)
                    if resultado:
                        url_encontrada, boleta, nombre = resultado
                        print(f"✅ Encontrado en '{grupo}' (RAM)")
                        print(f"   Boleta: {boleta} | Nombre: {nombre}")
                        resultado_final = (grupo, boleta)
                        self._url_cache[url] = resultado_final
                        return resultado_final

    # --- PREPARAR BÚSQUEDA FLEXIBLE (CORREGIDA) ---
            # 1. Quitamos http, https, www, el puerto :443 y espacios en blanco
            url_limpia = url.replace("https://", "").replace("http://", "").replace("www.", "").replace(":443", "").strip()
            
            # 2. Decodificamos la URL (convierte %2f en /, %3d en =, etc.)
            url_decodificada = urllib.parse.unquote(url_limpia)
            
            # 3. Preparamos el formato para la consulta SQL LIKE (Buscamos ambas versiones)
            url_like_normal = f"%{url_limpia}%"
            url_like_decodificada = f"%{url_decodificada}%"

            # 2. Búsqueda directa en Base de Datos (Respaldo con búsqueda FLEXIBLE)
            for grupo in self.bases_datos:
                try:
                    db_config_temp = self.db_config.copy()
                    db_config_temp['database'] = grupo
                    
                    with mysql.connector.connect(**db_config_temp, connection_timeout=5) as connection:
                        with connection.cursor() as cursor:
                            # Buscamos si coincide con la URL cruda o con la URL decodificada
                            query = f"""
                                SELECT boleta, nombre, {columna_db}
                                FROM {grupo}
                                WHERE {columna_db} LIKE %s OR {columna_db} LIKE %s
                                LIMIT 1
                            """
                            cursor.execute(query, (url_like_normal, url_like_decodificada))
                            resultado = cursor.fetchone()
                            
                            if resultado:
                                boleta, nombre, url_encontrada = resultado
                                print(f"✅ Enlace {tipo_enlace.upper()} encontrado en '{grupo}' (DB FLEXIBLE)")
                                print(f"   Boleta: {boleta} | Coincidencia DB: {url_encontrada}")
                                resultado_final = (grupo, boleta)
                                self._url_cache[url] = resultado_final
                                return resultado_final
                                
                except Error as e:
                    continue
            
            print(f"❌ No se encontró el enlace {tipo_enlace.upper()}")
            return None, None



    def buscar_horario_en_mismo_grupo(self, boleta, grupo):
        """Busca el horario SOLO en el grupo donde está la credencial"""
        try:
            db_config_temp = self.db_config.copy()
            db_config_temp['database'] = grupo
            
            with mysql.connector.connect(**db_config_temp, connection_timeout=5) as connection:
                with connection.cursor() as cursor:
                    query_check = f"""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = '{grupo}' 
                        AND table_name = '{boleta}'
                    """
                    
                    cursor.execute(query_check)
                    existe = cursor.fetchone()[0] > 0
                    
                    if existe:
                        print(f"✅ Horario encontrado en '{grupo}'")
                        return grupo
                    else:
                        print(f"⚠️ Horario no encontrado en '{grupo}'")
                        return None
                        
        except Error as e:
            print(f"❌ Error buscando horario: {e}")
            return None
    
    def buscar_tabla_horario(self, boleta):
        """Busca la tabla del horario en todas las bases"""
        for base_datos in self.bases_datos:
            try:
                db_config_temp = self.db_config.copy()
                db_config_temp['database'] = base_datos
                
                connection = mysql.connector.connect(**db_config_temp, connection_timeout=5)
                cursor = connection.cursor()
                
                query_check_table = f"""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = '{base_datos}' 
                AND table_name = '{boleta}'
                """
                
                cursor.execute(query_check_table)
                existe_tabla = cursor.fetchone()[0] > 0
                
                if existe_tabla:
                    print(f"✅ Tabla de horario '{boleta}' encontrada")
                    cursor.close()
                    connection.close()
                    return base_datos
                
                cursor.close()
                connection.close()
                
            except Error as e:
                print(f"⚠️ Error verificando '{base_datos}': {e}")
                continue
        
        print(f"❌ No se encontró tabla de horario")
        return None
    
    def activar_torniquete(self, comando=2):
        """Activa el torniquete vía WiFi al ESP32"""
        if self.esp32:
            try:
                if comando == 2:
                    resultado = self.esp32.abrir_torniquete_comando2()
                elif comando == 3:
                    resultado = self.esp32.abrir_torniquete_comando3()
                else:
                    print(f"❌ Comando {comando} no válido")
                    return False
                
                if resultado:
                    print(f"✅ Torniquete activado (comando {comando})")
                else:
                    print(f"⚠️ No se pudo activar torniquete (comando {comando})")
                return resultado
            except Exception as e:
                print(f"❌ Error activando torniquete: {e}")
                return False
        else:
            print("⚠️ ESP32 no conectado - Simulando activación")
            return True
    

    def comprobar_acceso_ilimitado():
        try:
            conexion = mysql.connector.connect(host="localhost", user="root", password=contra_db, database="Semestre")
            cursor = conexion.cursor(dictionary=True)
                
            cursor.execute("SHOW TABLES LIKE 'acceso'")
            if not cursor.fetchone():
                return False
                
            cursor.execute("SELECT verificacion FROM acceso LIMIT 1")
            fila = cursor.fetchone()
            
            if fila and fila['verificacion']:                    
                texto_descifrado = descifrar_texto(fila['verificacion'])
                if texto_descifrado == "Acceso_concedido":
                    return True
                    
        except Error as e:
            print(f"Error comprobando acceso ilimitado: {e}")
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conexion' in locals() and conexion.is_connected(): conexion.close()
            
        return False

    def procesar_qr(self, url, solo_verificar=False, lado_izquierdo=True):
            """
            Procesa un QR. 
            Si solo_verificar=True, NO abre el torniquete, solo devuelve si puede entrar.
            lado_izquierdo: True para izquierda (comando 1), False para derecha (comando 2)
            """
            print(f"\n{'='*60}")
            print(f"🔍 PROCESANDO QR (Modo {'Verificación' if solo_verificar else 'Activo'})")
            print(f"📍 Lado: {'IZQUIERDO' if lado_izquierdo else 'DERECHO'}")
            print(f"{'='*60}")
            
            comando_torniquete = "2" if lado_izquierdo else "3"
            
            # --- LÓGICA ADMINISTRATIVA ---
            if self.es_qr_administrativo(url):
                print("🏢 QR ADMINISTRATIVO - ACCESO DIRECTO")
                self.play_success_sound()
                if not solo_verificar and self.esp32 and self.esp32.conectado:
                    self.esp32.enviar_comando(comando_torniquete)
                return {
                    "tipo": "administrativo", "status": "OK", "puede_entrar": True, 
                    "mensaje": "Personal Administrativo", "nombre": "Administrativo", 
                    "foto": "/static/img/admin.png", "boleta": "ADMIN"
                }

            # --- LÓGICA GUARDIA ---
            if self.es_qr_guardia(url):
                print("🛡️ QR GUARDIA - ACCESO DIRECTO")
                self.play_success_sound()
                if not solo_verificar and self.esp32 and self.esp32.conectado:
                    self.esp32.enviar_comando(comando_torniquete)
                return {
                    "tipo": "guardia", "status": "OK", "puede_entrar": True, 
                    "mensaje": "Personal de Guardia", "nombre": "Guardia", 
                    "foto": "/static/img/guardia.png", "boleta": "GUARDIA"
                }

            # --- LÓGICA ALUMNOS (DAE / SAES) ---
            boleta = None
            base_datos_grupo = None
            tipo_qr = ""

            # 1. Identificar Tipo y Buscar en BD
            if self.es_enlace_dae(url):
                print("📇 Enlace DAE detectado")
                base_datos_grupo, boleta = self.buscar_alumno_por_url(url, "dae")
                tipo_qr = "dae"
                
            elif self.es_enlace_saes(url):
                print("📋 Enlace SAES detectado")
                base_datos_grupo, boleta = self.buscar_alumno_por_url(url, "saes")
                tipo_qr = "saes"

            # Validaciones de Existencia
            if not boleta or not base_datos_grupo:
                print("❌ Alumno no encontrado en la base de datos.")
                self.play_error_sound()
                return {
                    "status": "Error", 
                    "puede_entrar": False, 
                    "mensaje": "Alumno no registrado o QR desconocido", 
                    "nombre": "Desconocido", 
                    "foto": "",
                    "boleta": ""
                }

            print(f"✅ Datos recuperados -> Boleta: {boleta} | Grupo: {base_datos_grupo}")

            # 2. Obtener nombre del alumno y foto
            nombre_alumno = boleta  # Default
            foto_url = f"/static/image/{boleta}.jpg"
            
            try:
                db_config_temp = self.db_config.copy()
                db_config_temp['database'] = base_datos_grupo
                
                with mysql.connector.connect(**db_config_temp, connection_timeout=5) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(f"SELECT nombre, imagen_path FROM {base_datos_grupo} WHERE boleta = %s LIMIT 1", (boleta,))
                        resultado = cursor.fetchone()
                        if resultado:
                            if resultado[0]: nombre_alumno = resultado[0]
                            if resultado[1] and resultado[1].strip(): foto_url = resultado[1]
            except Exception as e:
                print(f"⚠️ No se pudo obtener detalles del alumno: {e}")

            # =========================================================================
            # 🌟 NUEVA LÓGICA: COMPROBAR ACCESO ILIMITADO (ANTES DEL HORARIO)
            # =========================================================================
            if self.comprobar_acceso_ilimitado():
                print("🔓 ACCESO ILIMITADO ACTIVADO - Omitiendo validación de horario")
                self.play_success_sound()
                
                # Mandar comando a la ESP32 para abrir
                if not solo_verificar and self.esp32 and self.esp32.conectado:
                    self.esp32.enviar_comando(comando_torniquete)
                    
                return {
                    "boleta": boleta,
                    "grupo": base_datos_grupo,
                    "status": "OK",
                    "puede_entrar": True,
                    "mensaje": "Acceso Libre (Sin Horario)", # Mensaje que saldrá en pantalla
                    "nombre": nombre_alumno,
                    "foto": foto_url
                }
            # =========================================================================

            # 3. Buscar Horario (Verificar que exista la tabla con nombre de la boleta)
            base_datos_horario = self.buscar_horario_en_mismo_grupo(boleta, base_datos_grupo)
            if not base_datos_horario:
                self.play_error_sound()
                return {
                    "status": "Error", "puede_entrar": False, 
                    "mensaje": "Sin horario registrado", "nombre": nombre_alumno,
                    "foto": foto_url, "boleta": boleta
                }

            # 4. Validar fin de semana (Excepto para Admins)
            if datetime.now().weekday() >= 5 and boleta not in ADMIN_BOLETAS:
                self.play_error_sound()
                return {
                    "status": "Fin de semana",
                    "puede_entrar": False,
                    "mensaje": "No hay clases hoy",
                    "nombre": nombre_alumno,
                    "foto": foto_url,
                    "boleta": boleta
                }
            
            # ... (El resto de tu código sigue igual hacia abajo)

            # 5. Obtener estado final y activar torniquete si corresponde
            inscrito_valor = self.get_inscrito(boleta, base_datos_grupo)
            
            # --- NUEVA LÓGICA PARA ADMINS ---
            if boleta in ADMIN_BOLETAS:
                print(f"👑 ADMIN DETECTADO: {boleta} - Saltando restricciones")
                estado = {"acceso": True, "mensaje": "Acceso Administrador"}
                
                # Definir el comando correcto según el escáner que lo leyó
                # 2 = Izquierda, 3 = Derecha
                comando_admin = "2" if lado_izquierdo else "3"
                
                # Mandamos a abrir el torniquete inmediatamente
                if not solo_verificar and self.esp32 and self.esp32.conectado:
                    self.esp32.enviar_comando(comando_admin)
                    print(f"⚙️ Comando Admin '{comando_admin}' enviado al ESP32")
            else:
                # Flujo normal para los demás alumnos
                estado = self.obtener_estado_acceso_salida(
                    boleta, 
                    inscrito_valor=inscrito_valor, 
                    grupo=base_datos_grupo, 
                    lado_izquierdo=lado_izquierdo, 
                    solo_verificar=solo_verificar
                )

            puede_entrar = estado.get("acceso", False)

            if puede_entrar:
                print("✅ ACCESO PERMITIDO")
                self.play_success_sound()
                # Registrar en Excel (opcional si lo usas)
                try:
                    self.registrar_acceso_excel(boleta, nombre_alumno, base_datos_grupo, puede_entrar, False)
                except: pass
            else:
                print("❌ ACCESO DENEGADO")
                self.play_error_sound()

            return {
                "boleta": boleta,
                "grupo": base_datos_grupo,
                "status": "OK" if puede_entrar else "Denegado",
                "puede_entrar": puede_entrar,
                "mensaje": estado.get("mensaje", "Acceso Denegado"),
                "nombre": nombre_alumno,
                "foto": foto_url
            }





    def crear_indices_sql_optimizacion(self):
            """Crea índices SQL para búsquedas rápidas (Actualizado con url_saes)"""
            print("\n" + "="*70)
            print("🔧 CREANDO ÍNDICES SQL")
            print("="*70)
            
            indices_creados = 0
            indices_existentes = 0
            errores = 0
            
            for grupo in self.bases_datos:
                try:
                    db_config_temp = self.db_config.copy()
                    db_config_temp['database'] = grupo
                    
                    with mysql.connector.connect(**db_config_temp, connection_timeout=30) as connection:
                        with connection.cursor() as cursor:
                            # 1. Índice para DAE (url_origen)
                            cursor.execute(f"""
                                SELECT COUNT(*) FROM information_schema.statistics
                                WHERE table_schema = '{grupo}' AND table_name = '{grupo}' AND index_name = 'idx_url_origen'
                            """)
                            if cursor.fetchone()[0] == 0:
                                print(f"📝 Creando índice url_origen en '{grupo}'")
                                cursor.execute(f"CREATE INDEX idx_url_origen ON {grupo} (url_origen(255))")
                                connection.commit()
                                indices_creados += 1
                            else:
                                indices_existentes += 1
                            
                            # 2. Índice para SAES (url_saes) - NUEVO
                            cursor.execute(f"""
                                SELECT COUNT(*) FROM information_schema.statistics
                                WHERE table_schema = '{grupo}' AND table_name = '{grupo}' AND index_name = 'idx_url_saes'
                            """)
                            if cursor.fetchone()[0] == 0:
                                try:
                                    print(f"📝 Creando índice url_saes en '{grupo}'")
                                    # Usamos (255) para limitar la longitud del índice en campos TEXT
                                    cursor.execute(f"CREATE INDEX idx_url_saes ON {grupo} (url_saes(255))")
                                    connection.commit()
                                    indices_creados += 1
                                except Exception as e:
                                    print(f"⚠️ No se pudo crear índice url_saes (quizás la columna no existe aún): {e}")
                            else:
                                indices_existentes += 1
                            
                            # 3. Índice para Boleta
                            cursor.execute(f"""
                                SELECT COUNT(*) FROM information_schema.statistics
                                WHERE table_schema = '{grupo}' AND table_name = '{grupo}' AND index_name = 'idx_boleta'
                            """)
                            if cursor.fetchone()[0] == 0:
                                print(f"📝 Creando índice boleta en '{grupo}'")
                                cursor.execute(f"CREATE INDEX idx_boleta ON {grupo} (boleta)")
                                connection.commit()
                                indices_creados += 1
                            
                except Error as e:
                    print(f"❌ Error en '{grupo}': {e}")
                    errores += 1
                    continue
            
            print(f"\n📊 RESUMEN: Creados: {indices_creados} | Existentes: {indices_existentes} | Errores: {errores}")
            return {"creados": indices_creados, "existentes": indices_existentes}


    def limpiar_cache(self):
        """Limpia todos los caches"""
        self._url_cache.clear()
        self._indices_ordenados.clear()
        self.scanned_codes.clear()
        self.resultado_mochila_por_boleta.clear()
        self.last_log_entries.clear()
        print("🧹 Cache limpiado completamente")
    
    def obtener_estadisticas(self):
        """Muestra estadísticas del sistema"""
        print(f"\n📊 ESTADÍSTICAS DEL SISTEMA")
        print(f"   URLs en cache: {len(self._url_cache)}")
        print(f"   Grupos con índices: {len(self._indices_ordenados)}")
        print(f"   Total grupos: {len(self.bases_datos)}")
        print(f"   ESP32: {'✅ Conectado' if self.esp32 and self.esp32.conectado else '❌ Desconectado'}")
        
        if self._indices_ordenados:
            total_registros = sum(len(indices) for indices in self._indices_ordenados.values())
            print(f"   Registros indexados: {total_registros}")
    
    def buscar_grupo_por_boleta(self, boleta):
        """Busca en qué grupo está registrada una boleta"""
        for base_datos in self.bases_datos:
            try:
                db_config_temp = self.db_config.copy()
                db_config_temp['database'] = base_datos
                
                with mysql.connector.connect(**db_config_temp, connection_timeout=5) as connection:
                    with connection.cursor() as cursor:
                        query = f"""
                            SELECT boleta 
                            FROM {base_datos}
                            WHERE boleta = %s
                            LIMIT 1
                        """
                        
                        cursor.execute(query, (boleta,))
                        resultado = cursor.fetchone()
                        
                        if resultado:
                            print(f"✅ Boleta encontrada en grupo '{base_datos}'")
                            return base_datos
                        
            except Error as e:
                print(f"⚠️ Error verificando grupo '{base_datos}': {e}")
                continue
        
        return None

    def obtener_horario_dia(self, boleta, base_datos, dia):
        """Obtiene el horario específico del día para una boleta"""
        try:
            db_config_temp = self.db_config.copy()
            db_config_temp['database'] = base_datos
            
            # Encerrar la boleta entre ` ` para que MySQL lo acepte como tabla
            tabla = f"`{boleta}`"

            with mysql.connector.connect(**db_config_temp) as connection:
                with connection.cursor() as cursor:
                    query = f"""
                        SELECT materia, profesor, {dia}
                        FROM {tabla}
                        WHERE {dia} IS NOT NULL AND {dia} != '' AND {dia} != '-'
                        ORDER BY {dia}
                    """

                    cursor.execute(query)
                    resultados = cursor.fetchall()
                    
                    if resultados:
                        horarios_dia = []
                        for materia, profesor, horario in resultados:
                            if horario.strip():
                                horarios_dia.append({
                                    'materia': materia,
                                    'profesor': profesor,
                                    'horario': horario.strip(),
                                })
                        
                        return horarios_dia if horarios_dia else None
                    
                    return None
                    
        except Error as e:
            print(f"❌ Error obteniendo horario: {e}")
            return None

    
    def get_inscrito(self, boleta, grupo):
        """Devuelve el valor de inscrito (0,1,2)"""
        try:
            db_config_temp = self.db_config.copy()
            db_config_temp['database'] = grupo
            
            with mysql.connector.connect(**db_config_temp) as conexion:
                with conexion.cursor() as cursor:
                    query = f"SELECT inscrito FROM {grupo} WHERE boleta = %s LIMIT 1"
                    cursor.execute(query, (boleta,))
                    resultado = cursor.fetchone()
                    
                    if resultado:
                        return resultado[0]
                    else:
                        return None
                        
        except mysql.connector.Error as e:
            print(f"❌ Error en get_inscrito: {e}")
            return None
    
    def obtener_primera_y_ultima_hora(self, horarios_dia):
        """Extrae la primera y última hora del día"""
        if not horarios_dia:
            return None, None
        
        horas = []
        for horario in horarios_dia:
            horario_str = horario['horario']
            patron_hora = r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
            match = re.search(patron_hora, horario_str)
            if match:
                hora_inicio = match.group(1)
                hora_fin = match.group(2)
                horas.append((hora_inicio, hora_fin, horario))
        
        if not horas:
            return None, None
        
        horas.sort(key=lambda x: x[0])
        
        primera_clase = horas[0][2]
        ultima_clase = horas[-1][2]
        primera_hora = horas[0][0]
        ultima_hora = horas[-1][1]
        
        return (primera_hora, primera_clase), (ultima_hora, ultima_clase)

    def actualizar_registros_salida(self):

        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        print(f"📅 Actualizando salida para el dia: {dia_nombre}...")
        try:
            # Corregí el nombre de la DB a "Semestre" (noté que decía "Semstre")
            conexion_registro = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database="Semestre" 
            )
            cursor_registro = conexion_registro.cursor()

            # COALESCE({dia_nombre}, 0) significa: Si el campo está vacío (NULL), úsalo como 0.
            query_update = f"UPDATE registros_salida SET {dia_nombre} = COALESCE({dia_nombre}, 0) + 1"
            cursor_registro.execute(query_update)
            conexion_registro.commit()

            # Si rowcount es 0, significa que la tabla estaba totalmente vacía (sin filas)
            if cursor_registro.rowcount == 0:
                print("La tabla estaba vacía, creando primer registro de salida...")
                query_insert = f"INSERT INTO registros_salida ({dia_nombre}) VALUES (1)"
                cursor_registro.execute(query_insert)
                conexion_registro.commit()
            else:
                print(f"Se sumó +1 en la salida al día {dia_nombre}")

        except Exception as e:
            print(f"Error: {e}")

        finally:
            # Siempre cerrar conexiones
            if 'cursor_registro' in locals() and cursor_registro:
                cursor_registro.close()
            if 'conexion_registro' in locals() and conexion_registro.is_connected():
                conexion_registro.close()
        

    def actualizar_registros_entradas(self):

        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        print(f"📅 Actualizando entrada para el dia: {dia_nombre}...")
        try:
            # Corregí el nombre de la DB a "Semestre" (noté que decía "Semstre")
            conexion_registro = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database="Semestre" 
            )
            cursor_registro = conexion_registro.cursor()

            # COALESCE({dia_nombre}, 0) significa: Si el campo está vacío (NULL), úsalo como 0.
            query_update = f"UPDATE registros SET {dia_nombre} = COALESCE({dia_nombre}, 0) + 1"
            cursor_registro.execute(query_update)
            conexion_registro.commit()

            # Si rowcount es 0, significa que la tabla estaba totalmente vacía (sin filas)
            if cursor_registro.rowcount == 0:
                print("La tabla estaba vacía, creando primer registro...")
                query_insert = f"INSERT INTO registros ({dia_nombre}) VALUES (1)"
                cursor_registro.execute(query_insert)
                conexion_registro.commit()
            else:
                print(f"Se sumó +1 al día {dia_nombre}")

        except Exception as e:
            print(f"Error: {e}")

        finally:
            # Siempre cerrar conexiones
            if 'cursor_registro' in locals() and cursor_registro:
                cursor_registro.close()
            if 'conexion_registro' in locals() and conexion_registro.is_connected():
                conexion_registro.close()
        



    def obtener_estado_acceso_salida(self, boleta, inscrito_valor=None, grupo=None, 
                                        lado_izquierdo=True, solo_verificar=False):
        """
        Verifica acceso/salida con control de horario
        lado_izquierdo: True para torniquete izquierdo (1), False para derecho (2)
        solo_verificar: True si solo queremos verificar sin abrir torniquete
        """
        acceso = False
        bloquear_a = 0
        comando_torniquete = "1" if lado_izquierdo else "2"
        
        if grupo is None:
            grupo = self.buscar_grupo_por_boleta(boleta)
            if not grupo:
                print(f"❌ No se encontró grupo para boleta {boleta}")
                return {
                    "salir": False, 
                    "bloquear_a": bloquear_a, 
                    "acceso": acceso,
                    "mensaje": "Grupo no encontrado"
                }
        
        base_datos = self.buscar_horario_en_mismo_grupo(boleta, grupo)
        if not base_datos:
            print(f"❌ No se encontró horario para boleta {boleta}")
            return {
                "salir": False, 
                "bloquear_a": bloquear_a, 
                "acceso": acceso,
                "mensaje": "Sin horario registrado"
            }
        
        if inscrito_valor is None:
            inscrito = self.get_inscrito(boleta, grupo)
        else:
            inscrito = inscrito_valor
        
        if inscrito != 1:
            return {
                "salir": False, 
                "bloquear_a": bloquear_a, 
                "acceso": acceso,
                "mensaje": "No estás inscrito"
            }
        
        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        
        horarios_dia = self.obtener_horario_dia(boleta, base_datos, dia_nombre)
        if not horarios_dia:
            return {
                "salir": False, 
                "bloquear_a": bloquear_a, 
                "acceso": acceso,
                "mensaje": "Sin clases hoy"
            }
        
        primera_info, ultima_info = self.obtener_primera_y_ultima_hora(horarios_dia)
        if not (primera_info and ultima_info):
            return {
                "salir": False, 
                "bloquear_a": bloquear_a, 
                "acceso": acceso,
                "mensaje": "Error en horario"
            }
        
        ahora = datetime.now()
        hoy = ahora.date()
        hora_inicio_str = primera_info[1]['horario'].split(" - ")[0]
        hora_fin_str = ultima_info[1]['horario'].split(" - ")[1]
        
        hora_entrada_dt = datetime.strptime(hora_inicio_str, "%H:%M")
        hora_salida_dt = datetime.strptime(hora_fin_str, "%H:%M")
        
        hora_entrada_dt = datetime.combine(hoy, hora_entrada_dt.time())
        hora_salida_dt = datetime.combine(hoy, hora_salida_dt.time())
        
        hora_entrada_minima = hora_entrada_dt - timedelta(minutes=40)
        hora_salida_minima = hora_salida_dt - timedelta(minutes=15)
        
        salir = False
        mensaje = "Acceso denegado"
        
        try:
            # Verificar si ya abrió
            conexion_grupo = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=grupo
            )
            cursor_grupo = conexion_grupo.cursor(dictionary=True)

            cursor_grupo.execute(f"SELECT abrio FROM {grupo} WHERE boleta = %s", (boleta,))
            resultado_abrio = cursor_grupo.fetchone()
            
            if resultado_abrio:
                abrio_actual = int(resultado_abrio["abrio"]) if resultado_abrio["abrio"] is not None else 0
                if abrio_actual == 1:
                    bloquear_a = 1
                    mensaje = "Ya ingresaste hoy"
                    print("❌ Entrada bloqueada (ya ingresó)")
                    cursor_grupo.close()
                    conexion_grupo.close()
                    return {
                        "salir": salir,
                        "bloquear_a": bloquear_a,
                        "acceso": acceso,
                        "mensaje": mensaje
                    }

            # Verificar pases temporales
            conexion_pase = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database="Pases_salida"
            )
            cursor_pase = conexion_pase.cursor(dictionary=True)

            cursor_pase.execute("""
                SELECT hora_inicio, hora_fin
                FROM modificaciones_temporales
                WHERE grupo = %s
            """, (base_datos,))
            pase = cursor_pase.fetchone()
            
            cursor_pase.close()
            conexion_pase.close()

            if pase:
                hora_inicio_pase_time = datetime.strptime(str(pase['hora_inicio']), "%H:%M").time()
                hora_fin_pase_time = datetime.strptime(str(pase['hora_fin']), "%H:%M").time()

                hora_inicio_pase = datetime.combine(hoy, hora_inicio_pase_time)
                hora_fin_pase = datetime.combine(hoy, hora_fin_pase_time)
                hora_salida_minima = hora_inicio_pase - timedelta(minutes=15)

                if hora_entrada_minima <= ahora <= hora_salida_minima:
                    acceso = True
                    mensaje = "Acceso con pase temporal"
                    
                    # ABRIR TORNIQUETE DEL LADO CORRECTO
                    if not solo_verificar:
                        if esp32 and esp32.conectado:
                            resultado_esp = esp32.enviar_comando(comando_torniquete)
                            if resultado_esp:
                                print(f"✅ Torniquete {comando_torniquete} activado (Pase temporal)")
                            else:
                                print(f"⚠️ Fallo activando torniquete {comando_torniquete}")
                        
                        # Actualizar base de datos
                        cursor_grupo.execute(f"UPDATE {grupo} SET abrio = 1 WHERE boleta = %s", (boleta,))
                        conexion_grupo.commit()
                        
                        # Registrar entrada
                        self.actualizar_registros_entradas()
                        
                    print("✅ Acceso permitido con pase temporal")
            else:
                if hora_entrada_minima <= ahora <= hora_salida_dt:
                    acceso = True
                    mensaje = "Acceso dentro de horario"
                    
                    # ABRIR TORNIQUETE DEL LADO CORRECTO
                    if not solo_verificar:
                        if esp32 and esp32.conectado:
                            resultado_esp = esp32.enviar_comando(comando_torniquete)
                            if resultado_esp:
                                print(f"✅ Torniquete {comando_torniquete} activado (Horario normal)")
                            else:
                                print(f"⚠️ Fallo activando torniquete {comando_torniquete}")
                        
                        # Actualizar base de datos
                        cursor_grupo.execute(f"UPDATE {grupo} SET abrio = 1 WHERE boleta = %s", (boleta,))
                        conexion_grupo.commit()
                        
                        # Registrar entrada
                        self.actualizar_registros_entradas()
                        
                    print("✅ Acceso permitido dentro del horario")
                else:
                    mensaje = "Fuera de horario"

            cursor_grupo.close()
            conexion_grupo.close()

        except mysql.connector.Error as e:
            print(f"❌ Error verificando acceso: {e}")
            mensaje = f"Error de sistema: {str(e)}"
        
        return {
            "salir": salir,
            "bloquear_a": bloquear_a,
            "acceso": acceso,
            "mensaje": mensaje
        }

    
    def stop(self):
        """Detiene el verificador"""
        self.running = False
        if self.esp32:
            self.esp32.desconectar()
        print("🛑 Verificador detenido")

    def operacion_mochila(self, boleta):
        """Devuelve True o False para revisión de mochila (aleatorio 20%)"""
        return random.random() < 0.2
    
    def registrar_acceso_excel(self, boleta, nombre, grupo, puede_entrar, es_salida):
        """Registra el acceso en un archivo Excel"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tipo = "SALIDA" if es_salida else "ENTRADA"
            estado = "PERMITIDO" if puede_entrar else "DENEGADO"
            
            print(f"📝 Registro: {timestamp} | {boleta} | {nombre} | {grupo} | {tipo} | {estado}")
            
        except Exception as e:
            print(f"⚠️ Error registrando: {e}")

# ============================================================================
# CONFIGURACIÓN FLASK
# ============================================================================

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'clave_secreta_segura'

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': contra_db
}

# Obtener configuración de la base de datos Semestre
try:
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password=contra_db,
        database="Semestre"
    )
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT semestre, grupo, 1_2_TM, 3_4_CM, 3_4_AM, 3_4_MM, 3_4_IM, 3_4_PM, 3_4_EM, 3_4_LM,
            5_6_CM, 5_6_AM, 5_6_MM, 5_6_IM, 5_6_PM, 5_6_EM, 5_6_LM
        FROM semestre
        LIMIT 1
    """)
    row = cursor.fetchone()

    if row:
        semestre = int(row['semestre'])
        grupo_seleccionado = row['grupo']
        print(f"✅ Grupo seleccionado: {grupo_seleccionado}")

        bloque_prefijo = {
            1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
            2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
        }

        prefijos = bloque_prefijo.get(semestre, bloque_prefijo[2])

        bases_datos = ["Pases_salida"]
        if row['1_2_TM']:
            bases_datos.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'3_4_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[tipo]}{i}" for i in range(1, count + 1)])
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'5_6_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, count + 1)])

        print(f"ℹ️ Grupos disponibles: {bases_datos}")
    else:
        print("❌ No se encontró información en 'semestre'")
        grupo_seleccionado = None
        semestre = 2
        bases_datos = []

    cursor.close()
    conexion.close()

except Error as e:
    print(f"❌ Error al conectar a 'Semestre': {e}")
    grupo_seleccionado = None
    semestre = 2
    bases_datos = []

print("✅ Bases de datos cargadas:", bases_datos)

# Crear instancia del verificador CON ESP32
verificador = QRHorarioVerificador(db_config=db_config, esp32_conexion=esp32)

# Precargar índices
print("🔄 Precargando índices...")
try:
    verificador.precargar_todos_los_indices()
    print("✅ Índices precargados")
except Exception as e:
    print(f"⚠️ No se pudieron precargar índices: {e}")



@app.route('/')
def index():
    """
    Renderiza la interfaz de Monitor Dual.
    Ya no procesa formularios POST porque la entrada viene por los escáneres USB.
    """
    return render_template('index_e.html')


@app.route('/api/estado_monitor')
def api_estado_monitor():
    """API que consulta el HTML cada 500ms para actualizarse"""
    return jsonify(datos_accesos)

@app.route('/test_esp32')
def test_esp():
    estado = esp32.enviar_comando("2") # Prueba apertura izquierda
    return jsonify({'enviado': estado, 'conectado': esp32.conectado})

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*70)
        print("🚀 INICIANDO SISTEMA COMPLETO (DUAL SCANNER)")
        print("="*70)
        print(f"📱 URL Local: http://localhost:5000")
        print(f"📡 ESP32 WiFi: {ESP32_IP}:{ESP32_PORT}")
        print("="*70 + "\n")
        
        # Crear índices SQL si es necesario
        verificador.crear_indices_sql_optimizacion() 
        
        # ---------------------------------------------------------------
        # INICIAR EL HILO DE LOS ESCÁNERES
        # ---------------------------------------------------------------
        hilo_escaner = threading.Thread(target=servidor_escaneres_background)
        hilo_escaner.daemon = True 
        hilo_escaner.start()
        print("✅ Hilo de recepción de escáneres iniciado en segundo plano")
        # ---------------------------------------------------------------
        
        # Iniciar servidor Flask
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n👋 Cerrando...")
    except Exception as e:
        print(f"Error fatal: {e}")