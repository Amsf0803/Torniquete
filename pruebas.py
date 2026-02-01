# Este archvio es para la salida del torniquete via WiFi con ESP32 :)

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


# ============================================================================
# CLASE DE CONEXIÓN ESP32 WIFI (REEMPLAZA PYSERIAL)
# ============================================================================

# Recordar que debe de haber un esp32 corriendo un servidor TCP en el puerto indicado y que sea solo para la salida del torniquete y otro para la entrada


class ConexionESP32:
    """
    Clase para comunicación WiFi con ESP32
    Reemplaza completamente pyserial
    """
    def __init__(self, esp_ip="192.168.1.100", esp_port=5000, timeout=5):
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.timeout = timeout
        self.socket = None
        self.conectado = False
        self.lock = threading.Lock()
        
    def conectar(self):
        """Establece conexión TCP con el ESP32"""
        with self.lock:
            try:
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect((self.esp_ip, self.esp_port))
                self.conectado = True
                print(f"✅ Conectado al ESP32 en {self.esp_ip}:{self.esp_port}")
                return True
                
            except socket.timeout:
                print(f"⏱️ Timeout conectando al ESP32 en {self.esp_ip}:{self.esp_port}")
                self.conectado = False
                return False
            except Exception as e:
                print(f"❌ Error conectando al ESP32: {e}")
                self.conectado = False
                return False
        
    def enviar_comando(self, comando):
        """Envía comando con reconexión automática (versión robusta para ESP32 torniquete)"""
        with self.lock:

            # Si no existe socket o está desconectado → reconectar
            if not self.conectado:
                if not self.conectar():
                    return False

            try:
                self.socket.sendall(comando.encode())

                # Esperar respuesta (si la hay)
                self.socket.settimeout(2)
                try:
                    respuesta = self.socket.recv(1024).decode().strip()
                    print(f"📡 ESP32 responde: {respuesta}")
                except socket.timeout:
                    pass

                return True

            except (BrokenPipeError, ConnectionResetError, OSError):
                print("⚠️ El ESP32 cerró la conexión → reconectando...")

                # Marcar como desconectado
                self.conectado = False

                # Intentar reconectar
                if not self.conectar():
                    return False

                # Reintentar el envío
                try:
                    self.socket.sendall(comando.encode())
                    return True
                except:
                    return False

    
    def write(self, data):
        """Método de compatibilidad con pyserial"""
        if isinstance(data, bytes):
            comando = data.decode()
        else:
            comando = str(data)
        
        return self.enviar_comando(comando)
    
    def abrir_torniquete(self):
        """Comando '2' - Abrir torniquete"""
        return self.enviar_comando('2')
    
    def cerrar_torniquete(self):
        """Comando '0' - Cerrar torniquete"""
        return self.enviar_comando('0')
    
    def verificar_estado(self):
        """Comando 'S' - Consultar estado del ESP32"""
        return self.enviar_comando('S')
    
    def ping(self):
        """Comando 'P' - Verificar que ESP32 está vivo"""
        return self.enviar_comando('P')
    
    def desconectar(self):
        """Cierra la conexión"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
            self.conectado = False
            print("🔌 Desconectado del ESP32")


# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

contra_db = "P3l0n100j0t3$"

# CONFIGURAR IP DEL ESP32 AQUÍ
ESP32_IP = "192.168.0.144"
ESP32_PORT = 5000

# Inicializar conexión con ESP32
intento = 0
esp32 = None
while True:
    try:
        esp32 = ConexionESP32(esp_ip=ESP32_IP, esp_port=ESP32_PORT)
        if esp32.conectar():
            print(f"✅ Conexión WiFi con ESP32 establecida")
            print(f"📡 IP ESP32: {ESP32_IP}:{ESP32_PORT}")
            break
        else:
            raise Exception("No se pudo conectar")
    except Exception as e:
        print(f"❌ Error al conectar con ESP32 (intento {intento + 1}): {e}")
        intento += 1
        if intento >= 5:
            print("⚠️ No se pudo conectar con ESP32 después de 5 intentos")
            print("⚠️ El sistema continuará sin control de torniquete")
            esp32 = None
            break
        import time
        time.sleep(2)


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
# CLASE PRINCIPAL
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
    
    def activar_torniquete(self):
        """Activa el torniquete vía WiFi al ESP32"""
        if self.esp32:
            try:
                resultado = self.esp32.abrir_torniquete()
                if resultado:
                    print("✅ Torniquete activado vía WiFi")
                else:
                    print("⚠️ No se pudo activar torniquete")
                return resultado
            except Exception as e:
                print(f"❌ Error activando torniquete: {e}")
                return False
        else:
            print("⚠️ ESP32 no conectado")
            return False
    
    def extraer_boleta_de_url(self, url):
        """Función unificada que detecta el tipo de URL y extrae la boleta"""
        print(f"\n🔍 Detectando tipo de enlace...")
        
        if self.es_qr_administrativo(url):
            print("🏢 QR Administrativo - ACCESO DIRECTO")
            boleta = "ADMINISTRATIVO"
            self.activar_torniquete()
            return boleta
        
        if self.es_qr_guardia(url):
            print("🛡️ QR Guardia - ACCESO DIRECTO")
            boleta = "GUARDIA"
            self.activar_torniquete()
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
    
    def procesar_qr(self, url):
        """Procesa un QR con flujo optimizado"""
        print(f"\n{'='*60}")
        print(f"🔍 PROCESANDO QR")
        print(f"{'='*60}")
        
        if self.es_qr_administrativo(url):
            print("🏢 QR ADMINISTRATIVO - ACCESO DIRECTO")
            self.play_success_sound()
            self.activar_torniquete()
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
            self.activar_torniquete()
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
    
    def obtener_estado_acceso_salida(self, boleta, inscrito_valor=None, grupo=None):
        """Verifica acceso/salida con control de horario"""
        salir = False
        bloquear_b = 0
        
        if boleta == "ADMINISTRATIVO":
            salir = True
            print("🏢 Acceso administrativo concedido")
            self.activar_torniquete()
            return {"salir": False, "bloquear_b": bloquear_b, "acceso": acceso}
        elif boleta == "GUARDIA":
            salir = True
            print("🛡️ Acceso guardia concedido")
            self.activar_torniquete()
            return {"salir": False, "bloquear_b": bloquear_b, "acceso": acceso}
        

        if grupo is None:
            grupo = self.buscar_grupo_por_boleta(boleta)
            if not grupo:
                print(f"❌ No se encontró grupo para boleta {boleta}")
                return {"salir": salir, "bloquear_b": bloquear_b, "acceso": False}
        
        base_datos = self.buscar_horario_en_mismo_grupo(boleta, grupo)
        if not base_datos:
            print(f"❌ No se encontró horario para boleta {boleta}")
            return {"salir": salir, "bloquear_b": bloquear_b, "acceso": False}
        
        if inscrito_valor is None:
            inscrito = self.get_inscrito(boleta, grupo)
        else:
            inscrito = inscrito_valor
        
        if inscrito != 1:
            return {"salir": salir, "bloquear_b": bloquear_b, "acceso": False}
        
        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        
        horarios_dia = self.obtener_horario_dia(boleta, base_datos, dia_nombre)
        if not horarios_dia:
            return {"salir": salir, "bloquear_b": bloquear_b, "acceso": False}
        
        primera_info, ultima_info = self.obtener_primera_y_ultima_hora(horarios_dia)
        if not (primera_info and ultima_info):
            return {"salir": salir, "bloquear_b": bloquear_b, "acceso": False}
        
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
        
        acceso = False
        
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
            
            # Verificar bloqueo de salida
            db_config_temp = self.db_config.copy()
            db_config_temp['database'] = base_datos
            
            conexion_grupo = mysql.connector.connect(**db_config_temp)
            cursor_grupo = conexion_grupo.cursor(dictionary=True)
            
            cursor_grupo.execute(f"SELECT cerro FROM `{base_datos}` WHERE boleta = %s", (boleta,))
            resultado_abrio = cursor_grupo.fetchone()
            
            if resultado_abrio:
                abrio_actual = int(resultado_abrio["cerro"]) if resultado_abrio["cerro"] is not None else 0
                if abrio_actual == 1:
                    bloquear_b = 1
                    print("❌ Salida bloqueada (ya salió)")
                else:
                    print("✅ Salida disponible")

            # Evaluar con pase temporal
            if pase:
                hora_inicio_pase_time = datetime.strptime(str(pase['hora_inicio']), "%H:%M").time()
                hora_fin_pase_time = datetime.strptime(str(pase['hora_fin']), "%H:%M").time()
                
                hora_inicio_pase = datetime.combine(hoy, hora_inicio_pase_time)
                hora_fin_pase = datetime.combine(hoy, hora_fin_pase_time)
                hora_salida_minima = hora_inicio_pase - timedelta(minutes=15)
                
                if ahora >= hora_salida_minima and bloquear_b == 0:
                    salir = True
                    self.activar_torniquete()
                    cursor_grupo.execute(f"UPDATE {base_datos} SET cerro = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
            else:
                # Sin pase temporal
                if ahora >= hora_salida_minima and bloquear_b == 0:
                    salir = True
                    self.activar_torniquete()
                    cursor_grupo.execute(f"UPDATE {base_datos} SET cerro = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
            
            cursor_grupo.close()
            conexion_grupo.close()
            
        except mysql.connector.Error as e:
            print(f"Error verificando pase: {e}")
        
        return {
            "salir": salir,
            "bloquear_b": bloquear_b,
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

    
    def registrar_acceso_excel(self, boleta, nombre, grupo, puede_entrar, es_salida): # Abandonado, si estas leyendo esto y eres parte del club ps intentalo agregar o practica ns hechale ganas w
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
        return render_template('index_s.html', foto=None, boleta=None, inscrito=None, 
                            acceso=False, salir=False)
    
    boleta = verificador.extraer_boleta_de_url(url)
    
    if boleta == "ADMINISTRATIVO":
        acceso_directo = True
        tipo_acceso = "administrativo"
        print("✅ Acceso administrativo concedido")
        return render_template('index_s.html', foto=None, boleta=None, inscrito=None, 
                        acceso=False, salir=False, operacion_mochila=False,
                        acceso_directo=acceso_directo, tipo_acceso=tipo_acceso)
    
    elif boleta == "GUARDIA":
        acceso_directo = True
        tipo_acceso = "guardia"
        print("✅ Acceso de guardia concedido")
        return render_template('index_s.html', foto=None, boleta=None, inscrito=None, 
                        acceso=False, salir=False, operacion_mochila=False,
                        acceso_directo=acceso_directo, tipo_acceso=tipo_acceso)
    
    if not boleta:
        return render_template('index_s.html', foto=None, boleta=None, inscrito=None, 
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
    bloquear_b = estado.get('bloquear_b', 0)
    acceso = estado.get('acceso', False)

    print(f"📊 Resultados:")
    print(f"   Boleta: {boleta}")
    print(f"   Grupo: {grupo}")
    print(f"   Inscrito: {inscrito}")
    print(f"   Salida: {salir}")
    
    return render_template(
        'index_s.html', 
        boleta=boleta, 
        inscrito=inscrito, 
        salir=salir, 
        bloquear_b=bloquear_b,
        acceso=acceso,
        boleta_especial=boleta_especial, 
        mensaje_especial=mensaje_especial
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    try:
        print("\n" + "="*70)
        print("🚀 INICIANDO SERVIDOR FLASK")
        print("="*70)
        print(f"📱 URL Local: http://localhost:5000")
        print(f"🌐 URL Red: http://0.0.0.0:5000")
        print(f"🗄️ Bases de datos: {len(bases_datos)} grupos")
        print(f"⚡ Optimizaciones: Búsqueda binaria + Cache")
        print(f"📡 ESP32 WiFi: {ESP32_IP}:{ESP32_PORT}")
        print(f"🔌 Estado ESP32: {'✅ Conectado' if esp32 and esp32.conectado else '❌ Desconectado'}")
        print("\n📋 Funcionalidades:")
        print("   ✅ Detección de QR en tiempo real")
        print("   ✅ Verificación de horarios optimizada")
        print("   ✅ Control de torniquete vía WiFi")
        print("   ✅ Log de accesos")
        print("   ✅ Sonidos de confirmación")
        print("   ✅ Interface web")
        print("   ✅ Búsqueda rápida con cache")
        print("="*70 + "\n")
        
        verificador.crear_indices_sql_optimizacion()
        
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n👋 Cerrando aplicación...")
    finally:
        verificador.stop()
        print("✅ Aplicación cerrada correctamente")