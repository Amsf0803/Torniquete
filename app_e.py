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

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

contra_db = "P3l0n100j0t3$"

# CONFIGURACIÓN ESP32 CON IP PÚBLICA
ESP32_IP = "201.66.195.11"  # ← TU IP PÚBLICA DEL ESP32
ESP32_PORT = 5000

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
        self.socket = None
        self.conectado = False
        self.lock = threading.Lock()

    def conectar(self):
        """Establece conexión TCP con el ESP32 usando IP pública"""
        with self.lock:
            try:
                # Cerrar conexión previa si existe
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                
                # Crear nuevo socket
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                
                # Conectar al ESP32 usando IP pública
                print(f"🔌 Conectando a ESP32 en {self.esp_ip}:{self.esp_port}...")
                self.socket.connect((self.esp_ip, self.esp_port))
                self.conectado = True
                
                # Leer mensaje de bienvenida
                try:
                    self.socket.settimeout(3.0)
                    welcome = self.socket.recv(1024).decode(errors="ignore").strip()
                    if welcome:
                        print(f"📡 Mensaje ESP32: {welcome}")
                except socket.timeout:
                    print("ℹ️ No se recibió mensaje de bienvenida (puede ser normal)")
                except Exception as e:
                    print(f"⚠️ Error leyendo mensaje: {e}")
                
                # Restaurar timeout
                self.socket.settimeout(self.timeout)
                
                print(f"✅ Conectado al ESP32 en {self.esp_ip}:{self.esp_port}")
                return True
                
            except Exception as e:
                print(f"❌ Error conectando al ESP32: {e}")
                print("\n💡 Solución de problemas:")
                print("   1. Verifica que el ESP32 esté encendido")
                print("   2. Asegúrate que el puerto 5000 esté abierto en el router")
                print("   3. Revisa configuraciones de firewall")
                print("   4. Verifica la IP: " + self.esp_ip)
                
                self.conectado = False
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None
                return False

    def enviar_comando(self, comando):
        """
        Envía comando al ESP32 (formato: "2\n" o "3\n")
        """
        if not self.conectado or not self.socket:
            print("⚠️ No hay conexión, intentando reconectar...")
            if not self.conectar():
                print("❌ No se pudo reconectar")
                return False
        
        try:
            # Convertir a string si es número
            if isinstance(comando, int):
                comando = str(comando)
            
            # El ESP32 espera comando + \n
            comando_str = comando.strip()
            comando_final = f"{comando_str}\n"
            
            print(f"📤 Enviando comando al ESP32: '{comando_str}'")
            
            # Enviar comando
            self.socket.sendall(comando_final.encode())
            
            # Leer respuesta (timeout corto)
            self.socket.settimeout(2.0)
            try:
                respuesta = self.socket.recv(1024).decode(errors="ignore").strip()
                if respuesta:
                    print(f"📥 Respuesta ESP32: {respuesta}")
                    
                    # Manejar estados especiales
                    if "BUSY" in respuesta.upper():
                        print("⚠️ ESP32 ocupado")
                        return False
                    elif "OK:" in respuesta:
                        print("✅ Comando aceptado")
                        return True
                    elif "INVALID" in respuesta.upper():
                        print("❌ Comando inválido")
                        return False
                        
            except socket.timeout:
                print("ℹ️ ESP32 no respondió (puede ser normal)")
                return True  # Asumimos éxito si no hay respuesta
            except Exception as e:
                print(f"⚠️ Error leyendo respuesta: {e}")
                return True  # Asumimos éxito
            
            # Restaurar timeout
            self.socket.settimeout(self.timeout)
            
            return True
            
        except Exception as e:
            print(f"❌ Error enviando comando: {e}")
            self.desconectar()
            return False

    def abrir_torniquete_comando2(self):
        """Comando '2' - Activar torniquete modo 2"""
        return self.enviar_comando(2)
    
    def abrir_torniquete_comando3(self):
        """Comando '3' - Activar torniquete modo 3"""
        return self.enviar_comando(3)
    
    def ping(self):
        """Verifica que ESP32 está vivo"""
        try:
            if not self.conectado or not self.socket:
                return False
            
            # Guardar timeout actual
            old_timeout = self.socket.gettimeout()
            self.socket.settimeout(2.0)
            
            # Enviar ping simple
            try:
                self.socket.sendall(b"\n")
                # Intentar leer algo
                try:
                    self.socket.recv(1)
                except socket.timeout:
                    pass  # Es normal que timeout en ping
            except:
                self.conectado = False
                return False
            
            # Restaurar timeout
            self.socket.settimeout(old_timeout)
            return True
            
        except:
            self.conectado = False
            return False

    def desconectar(self):
        """Cierra la conexión"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            self.conectado = False
            print("🔌 Desconectado del ESP32")
    
    def write(self, data):
        """Método de compatibilidad con pyserial"""
        return self.enviar_comando(data)

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
        """Precarga y ordena los URLs de un grupo para búsqueda binaria"""
        if grupo in self._indices_ordenados:
            return
        
        try:
            db_config_temp = self.db_config.copy()
            db_config_temp['database'] = grupo
            
            with mysql.connector.connect(**db_config_temp, connection_timeout=10) as connection:
                with connection.cursor() as cursor:
                    query = f"""
                        SELECT url_origen, boleta, nombre
                        FROM {grupo}
                        WHERE url_origen IS NOT NULL AND url_origen != ''
                        ORDER BY url_origen
                    """
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                    
                    self._indices_ordenados[grupo] = resultados
                    print(f"📊 Índice cargado para {grupo}: {len(resultados)} registros")
                    
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
    
    def buscar_credencial_dae_optimizado(self, url):
        """Búsqueda ultra-optimizada de credencial DAE"""
        if url in self._url_cache:
            print(f"⚡ Credencial encontrada en cache")
            return self._url_cache[url]
        
        print(f"\n🔍 Buscando credencial DAE...")
        
        for grupo in self.bases_datos:
            if grupo in self._indices_ordenados:
                resultado = self.busqueda_binaria_url(self._indices_ordenados[grupo], url)
                if resultado:
                    url_origen, boleta, nombre = resultado
                    print(f"✅ Encontrado en '{grupo}'")
                    print(f"   Boleta: {boleta}")
                    print(f"   Nombre: {nombre}")
                    
                    resultado_final = (grupo, boleta)
                    self._url_cache[url] = resultado_final
                    return resultado_final
        
        for grupo in self.bases_datos:
            try:
                db_config_temp = self.db_config.copy()
                db_config_temp['database'] = grupo
                
                with mysql.connector.connect(**db_config_temp, connection_timeout=5) as connection:
                    with connection.cursor() as cursor:
                        query = f"""
                            SELECT boleta, nombre, url_origen
                            FROM {grupo}
                            WHERE url_origen = %s
                            LIMIT 1
                        """
                        
                        cursor.execute(query, (url,))
                        resultado = cursor.fetchone()
                        
                        if resultado:
                            boleta, nombre, link = resultado
                            print(f"✅ Credencial encontrada en '{grupo}'")
                            print(f"   Boleta: {boleta}")
                            
                            resultado_final = (grupo, boleta)
                            self._url_cache[url] = resultado_final
                            return resultado_final
                            
            except Error as e:
                print(f"⚠️ Error en '{grupo}': {e}")
                continue
        
        print(f"❌ No se encontró la credencial")
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
    
    def extraer_boleta_de_url(self, url):
        """Función unificada que detecta el tipo de URL y extrae la boleta"""
        print(f"\n🔍 Detectando tipo de enlace...")
        
        if self.es_qr_administrativo(url):
            print("🏢 QR Administrativo - ACCESO DIRECTO")
            boleta = "ADMINISTRATIVO"
            self.activar_torniquete(2)
            return boleta
        
        if self.es_qr_guardia(url):
            print("🛡️ QR Guardia - ACCESO DIRECTO")
            boleta = "GUARDIA"
            self.activar_torniquete(3)
            return boleta
        
        if self.es_enlace_dae(url):
            print("📇 Enlace DAE detectado")
            grupo, boleta = self.buscar_credencial_dae_optimizado(url)
            return boleta
        
        elif self.es_enlace_saes(url):
            print("📋 Enlace SAES detectado")
            return self.extraer_boleta_de_url_saes(url)
        
        else:
            print("⚠️ Tipo de enlace desconocido")
            return self.extraer_boleta_de_url_saes(url)
    
    def obtener_grupo_por_url(self, url):
        """Obtiene el grupo según el tipo de URL"""
        if self.es_qr_administrativo(url) or self.es_qr_guardia(url):
            return None
        
        if self.es_enlace_dae(url):
            grupo, _ = self.buscar_credencial_dae_optimizado(url)
            return grupo
        
        elif self.es_enlace_saes(url):
            boleta = self.extraer_boleta_de_url_saes(url)
            if boleta:
                return self.buscar_grupo_por_boleta(boleta)
        
        return None
    
<<<<<<< HEAD
=======
    
>>>>>>> origin/main
    def procesar_qr(self, url):
        """Procesa un QR con flujo optimizado"""
        print(f"\n{'='*60}")
        print(f"🔍 PROCESANDO QR")
        print(f"{'='*60}")
        
        if self.es_qr_administrativo(url):
            print("🏢 QR ADMINISTRATIVO - ACCESO DIRECTO")
            self.play_success_sound()
            self.activar_torniquete(2)
            return {
                "tipo": "administrativo",
                "status": "OK",
                "puede_entrar": True,
                "acceso_directo": True,
                "mensaje": "Personal Administrativo"
            }
        
        if self.es_qr_guardia(url):
            print("🛡️ QR GUARDIA - ACCESO DIRECTO")
            self.play_success_sound()
            self.activar_torniquete(3)
            return {
                "tipo": "guardia",
                "status": "OK",
                "puede_entrar": True,
                "acceso_directo": True,
                "mensaje": "Personal de Guardia"
            }
        
        boleta = None
        base_datos_grupo = None
        
        if self.es_enlace_dae(url):
            print("📇 Tipo: CREDENCIAL DAE")
            
            base_datos_grupo, boleta = self.buscar_credencial_dae_optimizado(url)
            
            if not boleta or not base_datos_grupo:
                print("❌ Credencial no registrada")
                self.play_error_sound()
                return {
                    "tipo": "dae",
                    "status": "Error",
                    "puede_entrar": False,
                    "acceso_directo": False,
                    "mensaje": "Credencial no encontrada"
                }
            
            print(f"\n📊 INFORMACIÓN:")
            print(f"   Boleta: {boleta}")
            print(f"   Grupo: {base_datos_grupo}")
            
            base_datos_horario = self.buscar_horario_en_mismo_grupo(boleta, base_datos_grupo)
            
            if not base_datos_horario:
                print("❌ No se encontró horario")
                self.play_error_sound()
                return {
                    "tipo": "dae",
                    "boleta": boleta,
                    "grupo": base_datos_grupo,
                    "status": "Error",
                    "puede_entrar": False,
                    "acceso_directo": False,
                    "mensaje": "Sin horario registrado"
                }
        
        elif self.es_enlace_saes(url):
            print("📋 Tipo: HORARIO SAES")
            
            boleta = self.extraer_boleta_de_url_saes(url)
            
            if not boleta:
                print("❌ No se pudo extraer boleta")
                self.play_error_sound()
                return {
                    "tipo": "saes",
                    "status": "Error",
                    "puede_entrar": False,
                    "acceso_directo": False,
                    "mensaje": "No se pudo leer el horario"
                }
            
            base_datos_grupo = self.buscar_grupo_por_boleta(boleta)
            
            if not base_datos_grupo:
                print(f"❌ Boleta {boleta} no registrada")
                self.play_error_sound()
                return {
                    "tipo": "saes",
                    "boleta": boleta,
                    "status": "Error",
                    "puede_entrar": False,
                    "acceso_directo": False,
                    "mensaje": "Alumno no registrado"
                }
            
            base_datos_horario = self.buscar_horario_en_mismo_grupo(boleta, base_datos_grupo)
            
            if not base_datos_horario:
                print("❌ No se encontró horario")
                self.play_error_sound()
                return {
                    "tipo": "saes",
                    "boleta": boleta,
                    "grupo": base_datos_grupo,
                    "status": "Error",
                    "puede_entrar": False,
                    "acceso_directo": False,
                    "mensaje": "Sin horario registrado"
                }
        
        else:
            print("❌ Tipo de QR no reconocido")
            self.play_error_sound()
            return {
                "status": "Error",
                "puede_entrar": False,
                "acceso_directo": False,
                "mensaje": "Tipo de QR no válido"
            }
        
        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        
        print(f"📅 Día actual: {dia_nombre}")
        
        if dia_actual >= 5:
            print("🏖️ Es fin de semana")
            self.play_error_sound()
            return {
                "boleta": boleta,
                "grupo": base_datos_grupo,
                "status": "Fin de semana",
                "puede_entrar": False,
                "acceso_directo": False,
                "mensaje": "No hay clases"
            }
        
        horarios_dia = self.obtener_horario_dia(boleta, base_datos_horario, dia_nombre)
        
        if not horarios_dia:
            print(f"❌ No hay clases para {dia_nombre}")
            self.play_error_sound()
            return {
                "boleta": boleta,
                "grupo": base_datos_grupo,
                "status": "Sin clases",
                "puede_entrar": False,
                "acceso_directo": False,
                "mensaje": f"Sin clases el {dia_nombre}"
            }
        
        inscrito_valor = self.get_inscrito(boleta, base_datos_grupo)
        
        if inscrito_valor != 1:
            print(f"❌ Usuario no inscrito")
            self.play_error_sound()
            return {
                "boleta": boleta,
                "grupo": base_datos_grupo,
                "status": "No inscrito",
                "puede_entrar": False,
                "acceso_directo": False,
                "mensaje": "Usuario no inscrito"
            }
        
        estado = self.obtener_estado_acceso_salida(
            boleta, 
            inscrito_valor=inscrito_valor,
            grupo=base_datos_grupo
        )
        
        puede_entrar = estado.get("acceso", False)
        
        if puede_entrar:
            print("✅ ACCESO PERMITIDO")
            self.play_success_sound()
            self.activar_torniquete(2)  # Comando 2 para estudiantes
            
            try:
                self.registrar_acceso_excel(boleta, "", base_datos_grupo, puede_entrar, False)
            except:
                pass
        else:
            print("❌ ACCESO DENEGADO")
            self.play_error_sound()
        
        return {
            "boleta": boleta,
            "grupo": base_datos_grupo,
            "tipo": "estudiante",
            "status": "OK" if puede_entrar else "Fuera de horario",
            "puede_entrar": puede_entrar,
            "acceso_directo": False,
            "horarios": horarios_dia
        }
    
<<<<<<< HEAD
=======


>>>>>>> origin/main
    def precargar_todos_los_indices(self):
        """Precarga todos los índices"""
        print("\n🚀 PRECARGANDO ÍNDICES...")
        
        for grupo in self.bases_datos:
            self.precargar_indices_grupo(grupo)
        
        print(f"\n✅ Precarga completada: {len(self._indices_ordenados)} grupos")
    
    def crear_indices_sql_optimizacion(self):
        """Crea índices SQL para búsquedas rápidas"""
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
                        cursor.execute(f"""
                            SELECT COUNT(*)
                            FROM information_schema.statistics
                            WHERE table_schema = '{grupo}'
                            AND table_name = '{grupo}'
                            AND index_name = 'idx_url_origen'
                        """)
                        
                        if cursor.fetchone()[0] == 0:
                            print(f"📝 Creando índice url_origen en '{grupo}'")
                            cursor.execute(f"""
                                CREATE INDEX idx_url_origen 
                                ON {grupo} (url_origen)
                            """)
                            connection.commit()
                            indices_creados += 1
                        else:
                            indices_existentes += 1
                        
                        cursor.execute(f"""
                            SELECT COUNT(*)
                            FROM information_schema.statistics
                            WHERE table_schema = '{grupo}'
                            AND table_name = '{grupo}'
                            AND index_name = 'idx_boleta'
                        """)
                        
                        if cursor.fetchone()[0] == 0:
                            print(f"📝 Creando índice boleta en '{grupo}'")
                            cursor.execute(f"""
                                CREATE INDEX idx_boleta 
                                ON {grupo} (boleta)
                            """)
                            connection.commit()
                            indices_creados += 1
                        
            except Error as e:
                print(f"❌ Error en '{grupo}': {e}")
                errores += 1
                continue
        
        print("\n" + "="*70)
        print("📊 RESUMEN")
        print("="*70)
        print(f"✅ Índices nuevos: {indices_creados}")
        print(f"ℹ️  Ya existentes: {indices_existentes}")
        print(f"❌ Errores: {errores}")
        print("="*70)
        
        return {
            "creados": indices_creados,
            "existentes": indices_existentes,
            "errores": errores
        }
    
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
    
    def extraer_boleta_de_url_saes(self, url):
        """Extrae el número de boleta desde una URL del SAES"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            print("🌐 Solicitando página del SAES...")
            response = get_with_retries(url, headers, retries=3, backoff=2, timeout=20)
            print("✅ Página recibida, extrayendo boleta...")
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            boleta_element = soup.find('div', class_='boleta')
            if boleta_element:
                boleta_text = boleta_element.get_text().strip()
                numeros = re.findall(r'\d{10}', boleta_text)
                if numeros:
                    return numeros[0]
            
            texto_completo = soup.get_text()
            patron_boleta = r'boleta[:\s]*(\d{10})'
            match_boleta = re.search(patron_boleta, texto_completo, re.IGNORECASE)
            if match_boleta:
                return match_boleta.group(1)
            
            numeros_10_digitos = re.findall(r'\b\d{10}\b', texto_completo)
            if numeros_10_digitos:
                return numeros_10_digitos[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Error extrayendo boleta de URL SAES: {e}")
            return None
    
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
        

    def obtener_estado_acceso_salida(self, boleta, inscrito_valor=None, grupo=None):
        """Verifica acceso/salida con control de horario"""
        acceso = False
        bloquear_a = 0
        
        
        if grupo is None:
            grupo = self.buscar_grupo_por_boleta(boleta)
            if not grupo:
                print(f"❌ No se encontró grupo para boleta {boleta}")
                return {"salir": False, "bloquear_a": bloquear_a, "acceso": acceso}
        
        base_datos = self.buscar_horario_en_mismo_grupo(boleta, grupo)
        if not base_datos:
            print(f"❌ No se encontró horario para boleta {boleta}")
            return {"salir": False, "bloquear_a": bloquear_a, "acceso": acceso}
        
        if inscrito_valor is None:
            inscrito = self.get_inscrito(boleta, grupo)
        else:
            inscrito = inscrito_valor
        
        if inscrito != 1:
            return {"salir": False, "bloquear_a": bloquear_a, "acceso": acceso}
        
        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        horarios_dia = self.obtener_horario_dia(boleta, base_datos, dia_nombre)
        if not horarios_dia:
            return {"salir": False, "bloquear_a": bloquear_a, "acceso": acceso}
        
        primera_info, ultima_info = self.obtener_primera_y_ultima_hora(horarios_dia)
        if not (primera_info and ultima_info):
            return {"salir": False, "bloquear_a": bloquear_a, "acceso": acceso}
        
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
        
        try:
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

            conexion_grupo = mysql.connector.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=base_datos
            )
            cursor_grupo = conexion_grupo.cursor(dictionary=True)

            cursor_grupo.execute(f"SELECT abrio FROM {base_datos} WHERE boleta = %s", (boleta,))
            resultado_abrio = cursor_grupo.fetchone()
            cursor_grupo.close()
            conexion_grupo.close()
            if resultado_abrio:
                abrio_actual = int(resultado_abrio["abrio"]) if resultado_abrio["abrio"] is not None else 0
                if abrio_actual == 1:
                    bloquear_a = 1
                    print("❌ Entrada bloqueada (ya ingresó)")
                else:
                    print("✅ Entrada disponible")


            if pase:
                hora_inicio_pase_time = datetime.strptime(str(pase['hora_inicio']), "%H:%M").time()
                hora_fin_pase_time = datetime.strptime(str(pase['hora_fin']), "%H:%M").time()

                hora_inicio_pase = datetime.combine(hoy, hora_inicio_pase_time)
                hora_fin_pase = datetime.combine(hoy, hora_fin_pase_time)
                hora_salida_minima = hora_inicio_pase - timedelta(minutes=15)

                if hora_entrada_minima <= ahora <= hora_salida_minima and bloquear_a == 0:
                    acceso = True
                    self.activar_torniquete(2)
                    cursor_grupo.execute(f"UPDATE {base_datos} SET abrio = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
                    print("✅ Acceso permitido con pase temporal")
                    self.actualizar_registros_entradas()
            else:
                if hora_entrada_minima <= ahora <= hora_salida_dt and bloquear_a == 0:
                    acceso = True
                    self.activar_torniquete(2)
                    cursor_grupo.execute(f"UPDATE {base_datos} SET abrio = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
                    print("✅ Acceso permitido dentro del horario")
                    self.actualizar_registros_entradas()



        except mysql.connector.Error as e:
            print(f"Error verificando pase: {e}")
        
        return {
            "salir": salir,
            "bloquear_a": bloquear_a,
            "acceso": acceso
        }
    
    def boleta(self, url):
        """Obtiene el número de boleta desde cualquier tipo de QR"""
        return self.extraer_boleta_de_url(url)
    
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

# ============================================================================
# RUTAS FLASK
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('qr_url', '').strip()
    else:
        url = request.args.get('url', '').strip()
    
    if not url:
        return render_template('index_e.html', foto=None, boleta=None, inscrito=None, 
                            acceso=False, salir=False)
    
    boleta = verificador.extraer_boleta_de_url(url)
    
    if boleta == "ADMINISTRATIVO":
        acceso_directo = True
        tipo_acceso = "administrativo"
        print("✅ Acceso administrativo concedido")
        return render_template('index_e.html', foto=None, boleta=None, inscrito=None, 
                        acceso=False, salir=False, operacion_mochila=False,
                        acceso_directo=acceso_directo, tipo_acceso=tipo_acceso)
    
    elif boleta == "GUARDIA":
        acceso_directo = True
        tipo_acceso = "guardia"
        print("✅ Acceso de guardia concedido")
        return render_template('index_e.html', foto=None, boleta=None, inscrito=None, 
                        acceso=False, salir=False, operacion_mochila=False,
                        acceso_directo=acceso_directo, tipo_acceso=tipo_acceso)
    
    if not boleta:
        return render_template('index_e.html', foto=None, boleta=None, inscrito=None, 
                            error="No se pudo extraer la boleta del QR.", 
                            acceso=False, salir=False, operacion_mochila=False)
    
    boletas_especiales = {
        2024160324: "How did we get here?",
        2024160330: "The cake is a lie",
    }
    
    mensaje_especial = None
    boleta_especial = False
    
    if int(boleta) in boletas_especiales:
        print("🎮 Boleta especial detectada")
        boleta_especial = True
        mensaje_especial = boletas_especiales[int(boleta)]
    
    grupo = None
    
    if verificador.es_enlace_dae(url):
        grupo, _ = verificador.buscar_credencial_dae_optimizado(url)
        print(f"📇 Grupo desde DAE: {grupo}")
    
    if not grupo:
        grupo = verificador.buscar_grupo_por_boleta(boleta)
        print(f"📋 Grupo desde boleta: {grupo}")
    
    base_datos_encontrada = None
    if grupo:
        base_datos_encontrada = verificador.buscar_horario_en_mismo_grupo(boleta, grupo)
    else:
        base_datos_encontrada = verificador.buscar_tabla_horario(boleta)
    
    inscrito = None
    if base_datos_encontrada and grupo:
        inscrito = verificador.get_inscrito(boleta, grupo)
    elif base_datos_encontrada:
        inscrito = verificador.get_inscrito(boleta, base_datos_encontrada)
    
    estado = verificador.obtener_estado_acceso_salida(
        boleta, 
        inscrito_valor=inscrito,
        grupo=grupo if grupo else base_datos_encontrada
    )
    
    salir = estado.get('salir', False)
    bloquear_a = estado.get('bloquear_a', 0)
    acceso = estado.get('acceso', False)
    operacion_mochila = verificador.operacion_mochila(boleta)

    print(f"📊 Resultados:")
    print(f"   Boleta: {boleta}")
    print(f"   Grupo: {grupo}")
    print(f"   Inscrito: {inscrito}")
    print(f"   Acceso: {acceso}")
    
    return render_template(
        'index_e.html', 
        boleta=boleta, 
        inscrito=inscrito, 
        salir=salir, 
        bloquear_a=bloquear_a,
        acceso=acceso,
        boleta_especial=boleta_especial, 
        mensaje_especial=mensaje_especial,
        operacion_mochila=operacion_mochila,
        
    )

# Ruta API para control manual del ESP32
@app.route('/api/control_esp32', methods=['POST'])
def control_esp32():
    """API para control manual del ESP32"""
    try:
        data = request.get_json()
        comando = data.get('comando')
        
        if not comando or comando not in [2, 3]:
            return jsonify({'error': 'Comando inválido. Use 2 o 3'}), 400
        
        if verificador.esp32 and verificador.esp32.conectado:
            if comando == 2:
                success = verificador.esp32.abrir_torniquete_comando2()
            else:
                success = verificador.esp32.abrir_torniquete_comando3()
            
            if success:
                return jsonify({'success': True, 'comando': comando})
            else:
                return jsonify({'error': 'No se pudo enviar comando'}), 500
        else:
            return jsonify({'error': 'ESP32 no conectado'}), 503
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para verificar estado del ESP32
@app.route('/api/estado_esp32', methods=['GET'])
def estado_esp32():
    """Verifica estado de conexión con ESP32"""
    if verificador.esp32:
        estado = verificador.esp32.ping()
        return jsonify({
            'conectado': estado,
            'ip': ESP32_IP if estado else None,
            'puerto': ESP32_PORT
        })
    return jsonify({'conectado': False})

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*70)
        print("🚀 INICIANDO SISTEMA COMPLETO")
        print("="*70)
        print(f"📱 URL Local: http://localhost:5000")
        print(f"🌐 URL Red: http://0.0.0.0:5000")
        print(f"🗄️ Bases de datos: {len(bases_datos)} grupos")
        print(f"📡 ESP32 WiFi: {ESP32_IP}:{ESP32_PORT}")
        print(f"🔌 Estado ESP32: {'✅ Conectado' if esp32 and esp32.conectado else '❌ Desconectado'}")
        print("\n📋 Funcionalidades activas:")
        print("   ✅ Detección de QR en tiempo real")
        print("   ✅ Control de torniquete vía WiFi")
        print("   ✅ Interface web Flask")
        print("   ✅ Sonidos de confirmación")
        print("   ✅ API para control manual")
        print("="*70 + "\n")
        
        # Crear índices SQL si es necesario
        verificador.crear_indices_sql_optimizacion()
        
        # Iniciar servidor Flask
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n👋 Cerrando aplicación...")
    finally:
        verificador.stop()
        print("✅ Aplicación cerrada correctamente")