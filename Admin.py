import threading
import time
import re
import os
import base64
import requests
import pygame
import numpy as np
import mysql.connector
from mysql.connector import Error
from bs4 import BeautifulSoup
from flask import Flask, render_template, Response, jsonify, request, redirect, session
from datetime import datetime, date
import serial
import certifi
import os
import cv2
from pyzbar.pyzbar import decode
from PIL import Image
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



contra_db = "P3l0n100j0t3$"  # Cambiar por tu contraseña de MySQL

class QRReaderWithDB:
    def __init__(self, scanner_port=None, db_config=None):
        # Configuración del escáner QR físico
        self.scanner_port = scanner_port
        self.scanner = None
        self.running = True
        

        self.input_buffer = ""
        self.last_input_time = 0
        self.buffer_lock = threading.Lock()
        self.processing_url = False

        # Inicializar conexión con escáner (asumiendo que ya está conectado)
        self.scanner = serial.Serial(self.scanner_port, 9600, timeout=1) if self.scanner_port else None
        print(f"✅ Escáner conectado en puerto: {self.scanner_port}")

        self.scanned_codes = []
        self.last_log_entries = []
        self.lock = threading.Lock()

        self.input_buffer = ""
        self.last_input_time = 0

        if db_config is None:
            self.db_config = {
                'host': 'localhost',
                'database': '4MM2',
                'user': 'root',
                'password': contra_db
            }
        else:
            self.db_config = db_config

        self.audio_azteca()
        self.init_database()
        
        # Iniciar hilo de escucha del escáner
        self.scanner_thread = threading.Thread(target=self._scanner_loop, daemon=True)
        self.scanner_thread.start()

    def _scanner_loop(self):
        """Bucle principal del escáner en hilo separado - MODIFICADO"""
        while self.running:
            try:
                if self.scanner and self.scanner.is_open:
                    if self.scanner.in_waiting > 0:
                        data = self.scanner.readline().decode('utf-8').strip()
                        if data:
                            print(f"📱 Datos recibidos: {data}")
                            # USAR BUFFER EN LUGAR DE PROCESAR DIRECTAMENTE
                            self.add_to_buffer(data)
                    else:
                        time.sleep(2)
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"❌ Error en bucle del escáner: {e}")
                time.sleep(1)

    def add_to_buffer(self, data):
        """Añade datos al buffer y programa procesamiento con delay"""
        with self.buffer_lock:
            # Si es una nueva entrada, reiniciar buffer
            current_time = time.time()
            if current_time - self.last_input_time > 2:  # Si pasaron más de 2 segundos
                self.input_buffer = ""  # Reiniciar buffer
                print(f"🔄 Buffer reiniciado para nueva entrada")
            
            # Agregar datos al buffer
            self.input_buffer += data
            self.last_input_time = current_time
            
            print(f"📝 Buffer actual: '{self.input_buffer}' (longitud: {len(self.input_buffer)})")
        
        # Programar procesamiento con delay
        # Cancelar timer anterior si existe
        if hasattr(self, 'buffer_timer'):
            self.buffer_timer.cancel()
        
        # Nuevo timer - procesar después de 2 segundos de inactividad
        self.buffer_timer = threading.Timer(2.0, self.process_buffer)
        self.buffer_timer.start()

    def process_buffer(self):
        """Procesa el buffer cuando ha pasado tiempo suficiente sin nuevos datos"""
        with self.buffer_lock:
            if not self.input_buffer.strip() or self.processing_url:
                return
            
            buffer_content = self.input_buffer.strip()
            self.processing_url = True
            
            print(f"⏰ Procesando buffer después de delay: '{buffer_content}'")
            print(f"📏 Longitud final del buffer: {len(buffer_content)}")
        
        try:
            # Verificar que sea una URL válida antes de procesar
            if self.is_valid_url(buffer_content):
                print(f"✅ URL válida detectada en buffer")
                # Procesar como antes pero con el buffer completo
                self.process_qr_data(buffer_content)
            else:
                print(f"⚠️ Buffer no contiene URL válida: {buffer_content[:50]}...")
        
        finally:
            # Limpiar buffer y permitir nuevo procesamiento
            with self.buffer_lock:
                self.input_buffer = ""
                self.processing_url = False

    def is_valid_url(self, data):
        """Verifica si los datos forman una URL válida"""
        try:
            # Verificaciones básicas
            if not data.startswith(('http://', 'https://')):
                return False
            
            if len(data) < 20:  # URLs muy cortas probablemente incompletas
                return False
            
            # Verificar que tenga estructura de URL
            from urllib.parse import urlparse
            parsed = urlparse(data)
            if not parsed.netloc or len(parsed.netloc) < 5:
                return False
            
            # Verificar que sea SAES o DAE
            if not (self.es_enlace_saes(data) or self.es_enlace_dae(data)):
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validando URL: {e}")
            return False

    def get_log_entries(self):
        """Método que se usa en /get_updates"""
        with self.lock:
            return self.last_log_entries.copy()

    def stop(self):
        """Detiene el escáner y cierra conexiones"""
        self.running = False
        if self.scanner and self.scanner.is_open:
            self.scanner.close()
        print("🔌 Escáner QR desconectado")

    def audio_azteca(self):
        """Inicializa el sistema de audio"""
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.audio_activo = True
            print("✅ Sistema de audio inicializado correctamente")
        except Exception as e:
            print(f"❌ No se pudo inicializar el audio: {e}")
            self.audio_activo = False
    
    def init_database(self):
        """Inicializa la conexión a la base de datos y crea las tablas necesarias"""
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            if self.connection.is_connected():
                print("✅ Conexión a MySQL establecida")
                self.create_tables()
        except Error as e:
            print(f"❌ Error conectando a MySQL: {e}")
            self.connection = None
    
    def create_tables(self):
        """Crea las tablas necesarias"""
        if not self.connection:
            return
            
        cursor = self.connection.cursor()
        try:
            # Tabla para horarios SAES
            create_horarios_table = """
            CREATE TABLE IF NOT EXISTS horarios_saes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                grupo VARCHAR(50),
                materia VARCHAR(255),
                profesor VARCHAR(255),
                lunes VARCHAR(50),
                martes VARCHAR(50),
                miercoles VARCHAR(50),
                jueves VARCHAR(50),
                viernes VARCHAR(50),
                fecha_escaneado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                url_origen TEXT
            )
            """
            cursor.execute(create_horarios_table)
            self.connection.commit()
            print("✅ Tabla de horarios creada/verificada correctamente")
        except Error as e:
            print(f"❌ Error creando tabla de horarios: {e}")
        try:
            create_grupo_table = f"""
            CREATE TABLE IF NOT EXISTS Horario_Grupal (
                lunes VARCHAR(100),
                martes VARCHAR(100),
                miercoles VARCHAR(100),
                jueves VARCHAR(100),
                viernes VARCHAR(100)
            )
            """
            
            cursor.execute(create_grupo_table)
            self.connection.commit()
            print(f"✅ Tabla Horario_Grupal creada/verificada correctamente")

        except:
            print("❌ No se pudo crear el horario grupal.")
        finally:
            cursor.close()
    


    def crear_tabla_grupo(self, nombre_grupo):
        """Crea una tabla específica para un grupo si no existe"""

        try:
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password= contra_db,
                database="Semestre"
            )
            cursor = conexion.cursor(dictionary=True)

            # Obtener todos los valores de la tabla 'semestre' en una sola consulta
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

                # Mapear prefijos según semestre
                bloque_prefijo = {
                    1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                        'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
                    2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                        'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
                }

                prefijos = bloque_prefijo.get(semestre, bloque_prefijo[2])  # Por defecto semestre 2

                # Crear listas de grupos dinámicamente
                bases_datos = ["Pases_salida"]
                # Bloque 1_2
                if row['1_2_TM']:
                    bases_datos.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
                # Bloque 3_4
                for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
                    count = row[f'3_4_{tipo}']
                    if count:
                        bases_datos.extend([f"{prefijos[tipo]}{i}" for i in range(1, count + 1)])
                # Bloque 5_6
                for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
                    count = row[f'5_6_{tipo}']
                    if count:
                        bases_datos.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, count + 1)])

                print(f"ℹ️ Grupos disponibles para semestre {semestre}: {bases_datos}")

                if grupo_seleccionado in bases_datos:
                    print(f"✅ El grupo '{grupo_seleccionado}' es válido para el semestre {semestre}")
                else:
                    print(f"⚠️ El grupo '{grupo_seleccionado}' no está en la lista del semestre {semestre}")
            else:
                print("❌ No se encontró información en la tabla 'semestre'.")
                grupo_seleccionado = None
                semestre = 2
                bases_datos = []

            # Cerrar cursor y conexión
            cursor.close()
            conexion.close()

        except Error as e:
            print(f"❌ Error al conectar a la base de datos 'Semestre': {e}")
            grupo_seleccionado = None
            semestre = 2
            bases_datos = []

        if not self.connection:
            return None
            
        cursor = self.connection.cursor()
        
        try:
            # Cambiar el nombre de la tabla según el grupo
            nombre_tabla = f'{grupo_seleccionado}'
            create_grupo_table = f"""
            CREATE TABLE IF NOT EXISTS `{nombre_tabla}` (
                boleta VARCHAR(20) PRIMARY KEY,
                nombre VARCHAR(255),
                curp VARCHAR(18),
                escuela VARCHAR(255),
                turno VARCHAR(50),
                inscrito TINYINT(1) DEFAULT 0,
                imagen_path TEXT,
                url_origen TEXT,
                abrio VARCHAR(10),
                cerro VARCHAR(10)
            )
            """
            
            cursor.execute(create_grupo_table)
            self.connection.commit()
            print(f"✅ Tabla '{nombre_tabla}' creada/verificada correctamente")
            return nombre_tabla
        except Error as e:
            print(f"❌ Error creando tabla para grupo {nombre_grupo}: {e}")
            return None
        finally:
            cursor.close()
    
    def sonidito(self, frecuencia=800, duracion=0.2):
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
            beep1 = self.sonidito(600, 0.1)
            beep2 = self.sonidito(800, 0.15)
            if beep1 and beep2:
                beep1.play()
                pygame.time.wait(100)
                beep2.play()
            else:
                print("\a")
        except:
            print("\a")
    
    def play_schedule_sound(self):
        """Reproduce sonido para horarios"""
        if not self.audio_activo:
            return
        try:
            for freq in [400, 600, 800]:
                beep = self.sonidito(freq, 0.1)
                if beep:
                    beep.play()
                    pygame.time.wait(80)
            else:
                print("\a\a\a")
        except:
            print("\a\a\a")
    
    def play_credential_sound(self):
        """Reproduce sonido para credenciales"""
        if not self.audio_activo:
            return
        try:
            for freq in [500, 700, 500, 900]:
                beep = self.sonidito(freq, 0.1 if freq != 900 else 0.2)
                if beep:
                    beep.play()
                    pygame.time.wait(80)
            else:
                print("\a\a\a\a")
        except:
            print("\a\a\a\a")
    


    def procesar_url(self, url):
        """Procesa una URL detectada en el QR con validación mejorada"""
        print(f"\n🔍 Procesando URL: {url}")
        
        # VALIDACIONES MEJORADAS
        try:
            # Verificar que la URL esté completa
            if len(url) < 20:  # URLs muy cortas probablemente están incompletas
                print(f"⚠️ URL muy corta, posiblemente incompleta: {url}")
                return False
            
            # Verificar que tenga un dominio válido
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc or len(parsed.netloc) < 5:
                print(f"⚠️ URL sin dominio válido: {url}")
                return False
            
            # Verificar patrones conocidos antes de hacer la petición HTTP
            if not (self.es_enlace_saes(url) or self.es_enlace_dae(url)):
                print(f"⚠️ URL no reconocida como SAES o DAE: {url}")
                print(f"   - ¿Es SAES? {self.es_enlace_saes(url)}")
                print(f"   - ¿Es DAE? {self.es_enlace_dae(url)}")
                return False
            
            print(f"✅ URL válida detectada, tipo: {'SAES' if self.es_enlace_saes(url) else 'DAE'}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Aumentar timeout y agregar más manejo de errores
            response = requests.get(url, headers=headers, timeout=120, verify=certifi.where())
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if self.es_enlace_saes(url):
                print("📅 Detectado enlace SAES - Extrayendo horario...")
                horario_info = self.extraer_info_horario(soup)
                boleta = self.extraer_boleta(url) # <--- Aquí ya extraemos la boleta
                
                if horario_info:
                    self.play_schedule_sound()
                    print(f"✅ Horario extraído: {len(horario_info['materias'])} materias")
                    
                    # MODIFICACIÓN: Pasamos la boleta como argumento extra
                    success = self.guardar_horario_bd(horario_info, url, boleta) 
                    
                    if success and boleta:
                        # Renombrar tabla solo si se guardó correctamente
                        cursor = self.connection.cursor()
                        try:
                            rename_query = f"RENAME TABLE horarios_saes TO `{boleta}`"
                            cursor.execute(rename_query)
                            
                            # Recrear tabla horarios_saes
                            create_query = """
                            CREATE TABLE horarios_saes (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                grupo VARCHAR(50),
                                materia VARCHAR(255),
                                profesor VARCHAR(255),
                                lunes VARCHAR(50),
                                martes VARCHAR(50),
                                miercoles VARCHAR(50),
                                jueves VARCHAR(50),
                                viernes VARCHAR(50),
                                fecha_escaneado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                imagen_path TEXT,
                                url_origen TEXT
                            )
                            """
                            cursor.execute(create_query)
                            print(f"✅ Tabla renombrada a {boleta}")
                        except Exception as e:
                            print(f"⚠️ Error renombrando tabla: {e}")
                            try:
                                # Vaciar el contenido de la tabla si el renombrado falla
                                cursor.execute("TRUNCATE TABLE horarios_saes")
                                print("♻️ Tabla 'horarios_saes' vaciada exitosamente.")
                            except Exception as e2:
                                print(f"❌ Error vaciando la tabla: {e2}")
                        finally:
                            cursor.close()
                    
                    return success
                else:
                    print("❌ No se pudo extraer información del horario")

            elif self.es_enlace_dae(url):
                print("🆔 Detectado enlace DAE - Extrayendo credencial...")
                credencial_info = self.extraer_info_credencial(soup)
                
                if credencial_info:
                    self.play_credential_sound()
                    print(f"✅ Credencial extraída: {credencial_info['nombre']}")
                    return self.guardar_credencial_bd(credencial_info, url)
                else:
                    print("❌ No se pudo extraer información de la credencial")
            
        except requests.exceptions.Timeout:
            print(f"❌ Timeout al acceder a la URL: {url}")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Error de conexión: {e}")
        except requests.exceptions.HTTPError as e:
            print(f"❌ Error HTTP {e.response.status_code}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de petición: {e}")
        except Exception as e:
            print(f"❌ Error procesando URL: {e}")
        
        return False

    # 2. MEJORAR las funciones de detección de enlaces

    def es_enlace_saes(self, url):
        """Verifica si el enlace es de SAES horarios con validación mejorada"""
        patrones_saes = [
            r'saes\.cecyt\d+\.ipn\.mx.*ValidaHorario',
            r'.*ValidaHorario\.aspx.*',
            r'.*saes.*horario.*',
            r'.*ipn\.mx.*saes.*',
            r'servicios\.saes\.ipn\.mx',
        ]
        
        es_saes = any(re.search(patron, url, re.IGNORECASE) for patron in patrones_saes)
        if es_saes:
            print(f"✅ URL identificada como SAES: {url}")
        return es_saes

    def es_enlace_dae(self, url):
        """Verifica si el enlace es de DAE credenciales con validación mejorada"""
        patrones_dae = [
            r'servicios\.dae\.ipn\.mx.*vcred',
            r'.*vcred/\?h=.*',
            r'.*dae.*cred.*',
            r'.*ipn\.mx.*dae.*',
            r'dae\.ipn\.mx',
        ]
        
        es_dae = any(re.search(patron, url, re.IGNORECASE) for patron in patrones_dae)
        if es_dae:
            print(f"✅ URL identificada como DAE: {url}")
        return es_dae

    def set_buffer_timeout(self, timeout_seconds=2.0):
        """Permite ajustar el tiempo de espera del buffer"""
        self.buffer_timeout = timeout_seconds
        print(f"⚙️ Timeout de buffer ajustado a {timeout_seconds} segundos")

    # OPCIONAL: Método para limpiar buffer manualmente
    def clear_buffer(self):
        """Limpia el buffer manualmente"""
        with self.buffer_lock:
            self.input_buffer = ""
            self.processing_url = False
            if hasattr(self, 'buffer_timer'):
                self.buffer_timer.cancel()
        print("🧹 Buffer limpiado manualmente")

    # OPCIONAL: Método para obtener estado del buffer
    def get_buffer_status(self):
        """Obtiene el estado actual del buffer"""
        with self.buffer_lock:
            return {
                'buffer_content': self.input_buffer,
                'buffer_length': len(self.input_buffer),
                'last_input_time': self.last_input_time,
                'is_processing': self.processing_url,
                'time_since_last_input': time.time() - self.last_input_time if self.last_input_time > 0 else 0
            }
        


    def process_qr_data(self, qr_data):
        """Procesa los datos QR recibidos del escáner físico con validación mejorada"""
        try:
            # Limpiar y validar datos
            qr_data = qr_data.strip()
            
            # Verificar longitud mínima
            if len(qr_data) < 10:
                print(f"⚠️ Datos muy cortos, ignorando: {qr_data}")
                return
            
            # Verificar si ya fue escaneado (evitar duplicados)
            if qr_data in self.scanned_codes:
                print(f"⚠️ URL ya procesada anteriormente: {qr_data[:50]}...")
                return
            
            # Verificar si es una URL válida y completa
            if qr_data.startswith(('http://', 'https://')):
                # Validar que la URL esté completa
                from urllib.parse import urlparse
                try:
                    parsed = urlparse(qr_data)
                    if not parsed.netloc or len(parsed.netloc) < 5:
                        print(f"⚠️ URL malformada o incompleta: {qr_data}")
                        return
                except Exception as e:
                    print(f"⚠️ Error parseando URL: {e}")
                    return
                
                with self.lock:
                    # Agregar a la lista de escaneados
                    self.scanned_codes.append(qr_data)
                    
                    # Agregar entrada al log
                    log_entry = {
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'data': qr_data[:50] + "..." if len(qr_data) > 50 else qr_data,
                        'status': 'Procesando...',
                        'type': 'URL'
                    }
                    self.last_log_entries.append(log_entry)
                
                # Procesar la URL
                success = self.procesar_url(qr_data)
                
                with self.lock:
                    # Actualizar el estado en el log
                    if self.last_log_entries:
                        self.last_log_entries[-1]['status'] = 'Aceptado' if success else 'Error'
                
                if success:
                    self.play_success_sound()
                
                # Limpiar lista si es muy grande
                if len(self.scanned_codes) > 50:
                    self.scanned_codes = self.scanned_codes[-25:]
            else:
                print(f"⚠️ Datos no reconocidos como URL válida: {qr_data}")
                
        except Exception as e:
            print(f"❌ Error procesando datos QR: {e}")
    
    def extraer_titulo_pagina(self, soup):
        """Extrae el título de la página desde el elemento <p> en datos 1"""
        try:
            # Buscar el elemento <p> que contiene el título
            titulo_elem = soup.find('p')
            if titulo_elem:
                titulo = titulo_elem.get_text().strip()
                return titulo
            
            # Fallback: buscar en el title de la página
            title_elem = soup.find('title')
            if title_elem:
                return title_elem.get_text().strip()
                
            return "Sin título"
        except:
            return "Sin título"
    
    def extraer_info_horario(self, soup):
        """Extrae información del horario desde el HTML"""
        try:
            horario_info = {
                'titulo': self.extraer_titulo_pagina(soup),
                'materias': []
            }
            
            # Buscar tablas de horarios
            tablas = soup.find_all('table')
            
            for tabla in tablas:
                filas = tabla.find_all('tr')
                if len(filas) < 2:
                    continue
                
                # Buscar encabezados de días
                encabezados = []
                fila_header = filas[0]
                celdas_header = fila_header.find_all(['th', 'td'])
                encabezados = [celda.get_text().strip().lower() for celda in celdas_header]
                
                # Mapear días a índices
                dias_indices = {}
                dias_buscar = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes']
                for i, encabezado in enumerate(encabezados):
                    for dia in dias_buscar:
                        if dia in encabezado:
                            dia_clean = 'miercoles' if dia == 'miércoles' else dia
                            dias_indices[dia_clean] = i
                            break
                
                # Procesar filas de materias
                for fila in filas[1:]:
                    celdas = fila.find_all(['th', 'td'])
                    if len(celdas) < 4:
                        continue
                    
                    materia_info = {
                        'grupo': celdas[0].get_text().strip() if len(celdas) > 0 else '',
                        'materia': celdas[1].get_text().strip() if len(celdas) > 1 else '',
                        'profesor': celdas[3].get_text().strip() if len(celdas) > 3 else '',
                        'lunes': '',
                        'martes': '',
                        'miercoles': '',
                        'jueves': '',
                        'viernes': ''
                    }
                    
                    # Extraer horarios por día
                    for dia, indice in dias_indices.items():
                        if indice < len(celdas):
                            horario_dia = celdas[indice].get_text().strip()
                            materia_info[dia] = horario_dia if horario_dia else ''
                    
                    # Solo agregar si tiene información válida
                    if materia_info['materia'] and materia_info['grupo']:
                        horario_info['materias'].append(materia_info)
            
            return horario_info if horario_info['materias'] else None
            
        except Exception as e:
            print(f"Error extrayendo información del horario: {e}")
            return None

    def extraer_info_credencial(self, soup):
        """Extrae información de la credencial DAE incluyendo el grupo y la imagen del rostro"""
        try:
            credencial_info = {
                'boleta': '',
                'nombre': '',
                'curp': '',
                'escuela': '',
                'turno': '',
                'inscrito': 0,
                'grupo': ''
            }

            # Buscar elementos por clase específica
            elementos_por_clase = {
                'boleta': soup.find('div', class_='boleta'),
                'curp': soup.find('div', class_='curp'),
                'nombre': soup.find('div', class_='nombre'),
                'escuela': soup.find('div', class_='escuela'),
            }

            for campo, elemento in elementos_por_clase.items():
                if elemento:
                    texto = elemento.get_text().strip()
                    if texto:
                        credencial_info[campo] = texto

            # Buscar información de turno e inscripción
            divs_turno = soup.find_all('div', style=lambda x: x and '#199881' in x if x else False)
            for div in divs_turno:
                texto_div = div.get_text()
                html_turno = str(div)

                # Extraer estatus de inscripción
                if 'Inscrito' in texto_div and 'No inscrito' not in texto_div:
                    credencial_info['inscrito'] = 1
                elif 'No inscrito' in texto_div or 'Sin inscripción' in texto_div:
                    credencial_info['inscrito'] = 0

                # Extraer turno
                match_turno = re.search(r'Turno:\s*<b>([^<]+)</b>', html_turno)
                if match_turno:
                    credencial_info['turno'] = match_turno.group(1).strip()

            # Buscar el grupo en todo el HTML
            texto_completo = soup.get_text()
            patron_grupo = r'\b(\d[A-Z]{1,2}\d{1,2})\b'
            match_grupo = re.search(patron_grupo, texto_completo)
            if match_grupo:
                credencial_info['grupo'] = match_grupo.group(1)

            # Fallback
            if not any([credencial_info['boleta'], credencial_info['nombre']]):
                patrones = {
                    'boleta': r'boleta[:\s]*(\d{10})',
                    'nombre': r'nombre[:\s]*([A-ZÁÉÍÓÚÑ\s]+)',
                    'curp': r'curp[:\s]*([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]{2})',
                    'escuela': r'escuela[:\s]*([A-ZÁÉÍÓÚÑ\s\d]+)',
                    'turno': r'turno[:\s]*([A-ZÁÉÍÓÚÑ\s]+)'
                }

                for campo, patron in patrones.items():
                    if not credencial_info[campo]:
                        match = re.search(patron, texto_completo, re.IGNORECASE)
                        if match:
                            credencial_info[campo] = match.group(1).strip()

            # Limpiar datos
            for campo in credencial_info:
                if isinstance(credencial_info[campo], str):
                    credencial_info[campo] = re.sub(r'\s+', ' ', credencial_info[campo]).strip()

            # EXTRAER Y GUARDAR LA IMAGEN DEL ROSTRO
            try:
                divs_pic = soup.find_all('div', class_='pic')
                for div in divs_pic:
                    img = div.find('img')
                    if img and img.has_attr('src'):
                        src = img['src']
                        if src.startswith("data:image/jpeg;base64,"):
                            base64_data = src.split(',')[1]
                            if credencial_info['boleta']:
                                filename = f"static/image/{credencial_info['boleta']}.jpg"
                                os.makedirs(os.path.dirname(filename), exist_ok=True)

                                # Evitar sobrescribir si ya existe
                                if not os.path.exists(filename):
                                    with open(filename, "wb") as f:
                                        f.write(base64.b64decode(base64_data))
                                    print(f"✅ Imagen guardada como {filename}")
                                else:
                                    print(f"📁 Imagen ya existente: {filename}")

                                # Guardar ruta en la info
                                credencial_info['imagen_path'] = filename
                                break
            except Exception as img_error:
                print(f"⚠️ Error extrayendo imagen de rostro: {img_error}")

            return credencial_info if credencial_info['boleta'] or credencial_info['nombre'] else None

        except Exception as e:
            print(f"Error extrayendo información de credencial: {e}")
            return None

    def extraer_boleta(self, url):
        """Extrae el número de boleta de la URL"""
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            p_element = soup.find('p')

            if p_element:
                text = p_element.get_text(separator=' ', strip=True)
                start_index = text.find("Boleta:")
                
                if start_index != -1:
                    boleta_text = text[start_index:]
                    boleta = boleta_text.split()[1]
                    print(f'Número de boleta: {boleta}')
                    return boleta
            return None
        except Exception as e:
            print(f"Error extrayendo boleta: {e}")
            return None

# Agregamos el argumento 'boleta' a la definición
    def guardar_horario_bd(self, horario_info, url, boleta=None):
        """Guarda el horario en la base de datos y registra al alumno en la tabla del grupo seleccionado"""
        if not self.connection:
            print("❌ No hay conexión a la base de datos")
            return False
        
        # 1. OBTENER EL GRUPO SELECCIONADO REAL (El de la configuración)
        # Como inicializaste la clase con la BD del grupo, este es el dato "maestro"
        grupo_objetivo = self.db_config['database']
        
        cursor = self.connection.cursor()
        try:
            # --- GUARDADO DEL HORARIO (Tal cual viene en el SAES) ---
            query = """
            INSERT INTO horarios_saes (grupo, materia, profesor, lunes, martes, 
                                    miercoles, jueves, viernes, url_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            registros_insertados = 0

            for materia in horario_info['materias']:
                values = (
                    materia['grupo'], # Aquí guardamos el grupo que dice la materia (por si es recursamiento)
                    materia['materia'], 
                    materia['profesor'],
                    materia['lunes'], 
                    materia['martes'], 
                    materia['miercoles'],
                    materia['jueves'], 
                    materia['viernes'], 
                    url
                )
                cursor.execute(query, values)
                registros_insertados += 1
            
            self.connection.commit()
            print(f"✅ Horario guardado: {registros_insertados} materias")

            # Crear el horario grupal si no existe
            if registros_insertados >= 8:
                self._crear_horario_grupal(cursor, horario_info, url)

            # ---------------------------------------------------------
            # 2. NUEVA FUNCIONALIDAD: REGISTRO EN LA TABLA DEL GRUPO SELECCIONADO
            # ---------------------------------------------------------
            # Usamos 'grupo_objetivo' que es la variable segura del sistema
            if boleta and grupo_objetivo:
                print(f"🔄 Verificando registro de boleta {boleta} en grupo OFICIAL: {grupo_objetivo}...")
                self.registrar_alumno_en_grupo_saes(grupo_objetivo, boleta, url)

            return True
            
        except Error as e:
            print(f"❌ Error guardando horario: {e}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()

    def registrar_alumno_en_grupo_saes(self, nombre_grupo, boleta, url_saes):
            """Registra al alumno en la tabla maestra del grupo usando la columna url_saes"""
            conn_grupo = None
            try:
                # Conectamos a la BD del grupo seleccionado
                conn_grupo = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password=self.db_config['password'], 
                    database=nombre_grupo 
                )
                
                cursor_grupo = conn_grupo.cursor()

                # Aseguramos que la tabla exista (por precaución)
                cursor_grupo.execute(f"""
                    CREATE TABLE IF NOT EXISTS `{nombre_grupo}` (
                        boleta VARCHAR(20) PRIMARY KEY,
                        nombre VARCHAR(255),
                        curp VARCHAR(18),
                        escuela VARCHAR(255),
                        turno VARCHAR(50),
                        inscrito TINYINT(1) DEFAULT 0,
                        imagen_path TEXT,
                        url_origen TEXT,
                        url_saes TEXT,
                        abrio VARCHAR(10),
                        cerro VARCHAR(10)
                    )
                """)
                conn_grupo.commit()

                # Verificar si existe
                check_query = f"SELECT boleta FROM `{nombre_grupo}` WHERE boleta = %s"
                cursor_grupo.execute(check_query, (boleta,))
                resultado = cursor_grupo.fetchone()

                if not resultado:
                    # CREAR NUEVO: Usamos url_saes
                    print(f"➕ Alumno nuevo (SAES) en {nombre_grupo}.")
                    insert_query = f"""
                    INSERT INTO `{nombre_grupo}` (boleta, url_saes, inscrito) 
                    VALUES (%s, %s, 1)
                    """
                    cursor_grupo.execute(insert_query, (boleta, url_saes))
                    conn_grupo.commit()
                else:
                    # ACTUALIZAR EXISTENTE: Solo campo url_saes
                    print(f"🔄 Actualizando URL SAES para {boleta} en {nombre_grupo}.")
                    update_query = f"UPDATE `{nombre_grupo}` SET url_saes = %s WHERE boleta = %s"
                    cursor_grupo.execute(update_query, (url_saes, boleta))
                    conn_grupo.commit()

            except Error as e:
                print(f"❌ Error al registrar alumno en tabla de grupo: {e}")
            finally:
                if conn_grupo and conn_grupo.is_connected():
                    cursor_grupo.close()
                    conn_grupo.close()



    def _crear_horario_grupal(self, cursor, horario_info, url):
        """Crea la tabla de horario grupal y la llena solo con los días de la semana"""
        try:
            # Verificar si la tabla ya existe
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'Horario_Grupal'
            """)
            
            tabla_existe = cursor.fetchone()[0] > 0
            
            if not tabla_existe:
                # Crear la tabla Horario_Grupal solo con días de la semana
                crear_horario_grupal = """
                CREATE TABLE Horario_Grupal (
                    lunes VARCHAR(100),
                    martes VARCHAR(100),
                    miercoles VARCHAR(100),
                    jueves VARCHAR(100),
                    viernes VARCHAR(100)
                )
                """
                cursor.execute(crear_horario_grupal)
                print("✅ Tabla Horario_Grupal creada exitosamente")
            
            cursor.execute(""" Select * FROM Horario_Grupal""")
            filas = cursor.fetchall()

            if not filas:
                # Insertar solo los días de la semana en la tabla grupal
                query_grupal = """
                INSERT INTO Horario_Grupal (lunes, martes, miercoles, jueves, viernes)
                VALUES (%s, %s, %s, %s, %s)
                """
                
                registros_insertados_grupal = 0
                for materia in horario_info['materias']:
                    # Solo insertar si al menos un día tiene horario
                    if (materia['lunes'] or materia['martes'] or materia['miercoles'] or 
                        materia['jueves'] or materia['viernes']):
                        
                        values_grupales = (
                            materia['lunes'],
                            materia['martes'],
                            materia['miercoles'],
                            materia['jueves'],
                            materia['viernes']
                        )
                        cursor.execute(query_grupal, values_grupales)
                        registros_insertados_grupal += 1
                
                self.connection.commit()
                print(f"✅ Horario grupal guardado con {registros_insertados_grupal} registros de días")
            
            else:
                hay_texto = False
                for fila in filas:
                    for valor in fila:
                        if valor is not None and str(valor).strip() != "":
                            hay_texto = True
                            

                if hay_texto:
                    print("Horario grupal lleno")
                    pass

                else:
                    query_grupal = """
                    INSERT INTO Horario_Grupal (lunes, martes, miercoles, jueves, viernes)
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    
                    registros_insertados_grupal = 0
                    for materia in horario_info['materias']:
                        # Solo insertar si al menos un día tiene horario
                        if (materia['lunes'] or materia['martes'] or materia['miercoles'] or 
                            materia['jueves'] or materia['viernes']):
                            
                            values_grupales = (
                                materia['lunes'],
                                materia['martes'],
                                materia['miercoles'],
                                materia['jueves'],
                                materia['viernes']
                            )
                            cursor.execute(query_grupal, values_grupales)
                            registros_insertados_grupal += 1
                    
                    self.connection.commit()
                    print(f"✅ Horario grupal guardado con {registros_insertados_grupal} registros de días")

            self.connection.commit()
        except Exception as e:
            print(f"⚠️ Error creando/llenando horario grupal: {e}")
            self.connection.rollback()
            raise e  # Re-lanzar para que el método principal maneje el error

    def guardar_credencial_bd(self, credencial_info, url):
        """Guarda la credencial en una tabla específica del grupo, incluyendo imagen base64"""
        if not self.connection:
            print("❌ No hay conexión a la base de datos")
            return False

        # Crear tabla del grupo si no existe
        nombre_tabla = self.crear_tabla_grupo(credencial_info['grupo'])
        if not nombre_tabla:
            return False

        # Cargar imagen como base64 desde archivo
        imagen_base64 = None
        if credencial_info.get('boleta'):
            ruta_imagen = f"static/image/{credencial_info['boleta']}.jpg"
            if os.path.exists(ruta_imagen):
                try:
                    with open(ruta_imagen, "rb") as f:
                        imagen_base64 = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    print(f"⚠️ Error leyendo imagen para base64: {e}")

        cursor = self.connection.cursor()
        try:
            # Asegurarse de que la columna imagen_base64 exista
            cursor.execute(f"""
                ALTER TABLE `{nombre_tabla}` ADD COLUMN imagen_base64 LONGTEXT
            """)
            self.connection.commit()
        except Error as e:
            if "Duplicate column name" in str(e):
                pass  # Ya existe, no pasa nada
            else:
                print(f"⚠️ Error asegurando columna imagen_base64: {e}")

        try:
            # Usar INSERT ... ON DUPLICATE KEY UPDATE para evitar duplicados
            query = f"""
            INSERT INTO `{nombre_tabla}` (
                boleta, nombre, curp, escuela, turno, inscrito, imagen_path, imagen_base64, url_origen
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                nombre = VALUES(nombre),
                curp = VALUES(curp),
                escuela = VALUES(escuela),
                turno = VALUES(turno),
                inscrito = VALUES(inscrito),
                imagen_path = VALUES(imagen_path),
                imagen_base64 = VALUES(imagen_base64),
                url_origen = VALUES(url_origen)
            """

            values = (
                credencial_info['boleta'],
                credencial_info['nombre'],
                credencial_info['curp'],
                credencial_info['escuela'],
                credencial_info['turno'],
                credencial_info['inscrito'],
                credencial_info.get('imagen_path', ''),
                imagen_base64,
                url
            )

            cursor.execute(query, values)
            self.connection.commit()
            print(f"✅ Credencial con imagen base64 guardada en '{nombre_tabla}' - Boleta: {credencial_info['boleta']}")
            return True

        except Error as e:
            print(f"❌ Error guardando credencial: {e}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()


    def get_processing_stats(self):
        """Obtiene estadísticas de procesamiento"""
        if not self.connection:
            return None
        
        cursor = self.connection.cursor()
        try:
            stats = {
                'horarios_procesados': 0,
                'credenciales_procesadas': 0,
                'ultimo_procesamiento': None
            }
            
            cursor.execute("SELECT COUNT(*) FROM horarios_saes")
            stats['horarios_procesados'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT MAX(fecha_escaneado) FROM horarios_saes")
            ultimo_horario = cursor.fetchone()[0]
            
            if ultimo_horario:
                stats['ultimo_procesamiento'] = ultimo_horario.strftime("%Y-%m-%d %H:%M:%S")
            
            return stats
            
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return None
        finally:
            cursor.close()


    def ejecutar(self):
        """Ejecuta el lector de QR con escáner físico"""
        print("🚀 Iniciando lector de QR con escáner físico...")
        print("📖 Tipos soportados: SAES (horarios) y DAE (credenciales)")
        print("⌨️ Presiona Ctrl+C para salir")
        
        try:
            while self.running:
                # Mostrar estado del escáner
                status = self.get_scanner_status()
                print(f"📡 Estado del escáner: {status['status']} - Puerto: {status['port']}")
                
                # El escáner funciona en segundo plano a través del hilo _scanner_loop
                time.sleep(5)  # Mostrar estado cada 5 segundos
                
        except KeyboardInterrupt:
            print("\n👋 Deteniendo lector de QR...")
        
        finally:
            # Limpiar
            self.stop()
            if self.connection:
                self.connection.close()
                print("🔌 Conexión a base de datos cerrada")
            print("👋 Lector de QR finalizado")


def crear_bases_si_no_existen(bases_datos): 
    """Crea las bases de datos necesarias si no existen"""
    try:
        # Conexión sin especificar base de datos
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password= contra_db
        )
        cursor = connection.cursor()

        for bd in bases_datos:
            # Verificamos si la base ya existe
            cursor.execute(f"SHOW DATABASES LIKE '{bd}'")
            resultado = cursor.fetchone()
            if not resultado:
                cursor.execute(f"CREATE DATABASE {bd}")
                print(f"✅ Base de datos '{bd}' creada.")
            else:
                print(f"🔹 Base de datos '{bd}' ya existe.")
        
        # Crear base de datos adicionales
        for db_name in ['Pases_salida', 'Semestre', 'Suspensiones']:
            cursor.execute(f"SHOW DATABASES LIKE '{db_name}'")
            resultado = cursor.fetchone()
            if not resultado:
                cursor.execute(f"CREATE DATABASE {db_name}")
                print(f"✅ Base de datos '{db_name}' creada.")
        
        # Crear tabla modificaciones_temporales en Pases_salida
        try:
            cursor.execute("USE Pases_salida")
            pases = """
                    CREATE TABLE IF NOT EXISTS modificaciones_temporales (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    grupo VARCHAR(50),
                    dia_semana VARCHAR(255),
                    fecha_aplicacion VARCHAR(255),
                    hora_inicio VARCHAR(50),
                    hora_fin VARCHAR(50)
                    )
                    """
            cursor.execute(pases)
            print("✅ Tabla modificaciones_temporales creada.")
        except Error as e:
            print(f"🔹 Tabla modificaciones_temporales ya existe.")
        
        # Crear tabla semestre en Semestre
        try:
            cursor.execute("USE Semestre")
            semestre = """
                CREATE TABLE IF NOT EXISTS semestre (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    semestre INT,
                    grupo VARCHAR(50),
                    `1_2_TM` INT,
                    `3_4_CM` INT,
                    `3_4_AM` INT,
                    `3_4_MM` INT,
                    `3_4_IM` INT,
                    `3_4_PM` INT,
                    `3_4_EM` INT,
                    `3_4_LM` INT,
                    `5_6_CM` INT,
                    `5_6_AM` INT,
                    `5_6_MM` INT,
                    `5_6_IM` INT,
                    `5_6_PM` INT,
                    `5_6_EM` INT,
                    `5_6_LM` INT
                )
            """
            cursor.execute(semestre)
            print("✅ Tabla de semestre creada/verificada correctamente")

            # Funcion nueva que ps se planea poner un contador de cuantas veces entrar cada dia a la semana :)
            registros = """
                CREATE TABLE IF NOT EXISTS registros (
                    lunes INT,
                    martes INT,
                    miercoles INT,
                    jueves INT,
                    viernes INT
                )
                """
            cursor.execute(registros)
            print("✅ Tabla de registros creada/verificada correctamente")
            registros_salida = """
                CREATE TABLE IF NOT EXISTS registros_salida (
                    lunes INT,
                    martes INT,
                    miercoles INT,
                    jueves INT,
                    viernes INT
                )
                """
            cursor.execute(registros_salida)
            print("✅ Tabla de registros de salida creada/verificada correctamente")
        except Error as e:
            print(f"🔹 Error al crear la tabla semestre: {e}")


        # Crear tabla suspensiones_registro en Suspensiones
        try: 
            cursor.execute("USE Suspensiones")
            suspensiones = """
            CREATE TABLE IF NOT EXISTS suspensiones_registro (
            id INT AUTO_INCREMENT PRIMARY KEY,
            boleta INT NOT NULL,
            grupo VARCHAR(50),
            nombre_alumno VARCHAR(255),
            fecha_inicio DATE,
            fecha_fin DATE
            )
            """
            cursor.execute(suspensiones)
            print("✅ Tabla suspensiones creada correctamente")
        except Error as e:
            print(f"🔹 Tabla suspensiones ya existe.")
        
        cursor.close()
        connection.close()
    
    except Error as e:
        print("❌ Error al conectar o crear base de datos:", e)


# 1. PRIMERO DEFINIMOS LA FUNCIÓN (Afuera de todo para que siempre exista)
def inicializar_tablas_grupos(lista_grupos, password_db):
    """Crea los schemas y las tablas maestras de cada grupo al inicio"""
    print("\n🏗️  Verificando integridad de Schemas y Tablas de Grupos...")
    
    try:
        conexion = mysql.connector.connect(
            host="localhost", user="root", password=password_db
        )
        cursor = conexion.cursor()

        for grupo in lista_grupos:
            if grupo == "Pases_salida": continue 

            # 1. Crear Schema
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{grupo}`")
            except Error as e:
                print(f"❌ Error creando schema {grupo}: {e}")
                continue

            # 2. Crear Tabla Maestra y asegurar columna url_saes
            try:
                conn_grupo = mysql.connector.connect(
                    host="localhost", user="root", password=password_db, database=grupo
                )
                cur_grupo = conn_grupo.cursor()
                
                # Definición de la tabla CON la nueva columna url_saes
                tabla_sql = f"""
                CREATE TABLE IF NOT EXISTS `{grupo}` (
                    boleta VARCHAR(20) PRIMARY KEY,
                    nombre VARCHAR(255),
                    curp VARCHAR(18),
                    escuela VARCHAR(255),
                    turno VARCHAR(50),
                    inscrito TINYINT(1) DEFAULT 0,
                    imagen_path TEXT,
                    url_origen TEXT,     -- Este es para la Credencial (DAE)
                    url_saes TEXT,       -- ESTE ES EL NUEVO (Horario)
                    abrio VARCHAR(10),
                    cerro VARCHAR(10)
                )
                """
                cur_grupo.execute(tabla_sql)
                
                # --- TRUCO DE SEGURIDAD ---
                # Si la tabla ya existía de antes y no tiene 'url_saes', esto la agrega:
                try:
                    cur_grupo.execute(f"ALTER TABLE `{grupo}` ADD COLUMN url_saes TEXT")
                    print(f"  └── Columna 'url_saes' agregada a {grupo}")
                except Error as e:
                    # Si falla es porque ya existe (Duplicate column name), lo ignoramos
                    pass 
                # --------------------------

                conn_grupo.commit()
                cur_grupo.close()
                conn_grupo.close()
                
            except Error as e:
                print(f"❌ Error creando tabla interna para {grupo}: {e}")

        print("✅ Verificación de estructura de grupos completada.\n")
        cursor.close()
        conexion.close()

    except Error as e:
        print(f"❌ Error general en inicialización: {e}")

# 2. LUEGO HACEMOS LA LÓGICA DE OBTENER LOS GRUPOS (Tu bloque Try/Except original)
try:
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password= contra_db,
        database="Semestre"
    )
    cursor = conexion.cursor(dictionary=True)

    # Obtener todos los valores de la tabla 'semestre'
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

        # Mapear prefijos según semestre
        bloque_prefijo = {
            1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
            2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
        }

        prefijos = bloque_prefijo.get(semestre, bloque_prefijo[2]) 

        # Crear listas de grupos dinámicamente
        bases_datos = ["Pases_salida"]
        
        # Bloque 1_2
        if row['1_2_TM']:
            bases_datos.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
        # Bloque 3_4
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'3_4_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[tipo]}{i}" for i in range(1, count + 1)])
        # Bloque 5_6
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'5_6_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, count + 1)])

        print(f"ℹ️ Grupos disponibles para semestre {semestre}: {bases_datos}")

        if grupo_seleccionado in bases_datos:
            print(f"✅ El grupo '{grupo_seleccionado}' es válido para el semestre {semestre}")
        else:
            print(f"⚠️ El grupo '{grupo_seleccionado}' no está en la lista del semestre {semestre}")
    else:
        print("❌ No se encontró información en la tabla 'semestre'.")
        grupo_seleccionado = None
        semestre = 2
        bases_datos = []

    cursor.close()
    conexion.close()

except Error as e:
    print(f"❌ Error al conectar a la base de datos 'Semestre': {e}")
    grupo_seleccionado = None
    semestre = 2
    bases_datos = []


# 3. FINALMENTE LLAMAMOS A LA FUNCIÓN (Aquí ya es seguro)
if bases_datos:
    inicializar_tablas_grupos(bases_datos, contra_db)

# Configurar Flask
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'clave_secreta_segura'

# Configuración optimizada para Flask
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = False

verificador_registro = None

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('main_registro.html')


@app.route('/seleccionar_metodo', methods=['GET'])
def seleccionar_metodo():
    return render_template('seleccionar_metodo.html')


@app.route('/method', methods=['GET', 'POST'])
def method():

    if request.method == 'POST':
        # Verificar si viene del formulario de method
        if 'method' in request.form:
            metodo_seleccionado = request.form['method']

            session['metodo_seleccionado'] = metodo_seleccionado
            if metodo_seleccionado == 'manual':
                return redirect('/seleccionar_ciclo')
            elif metodo_seleccionado == 'automatico':
                return redirect('/seleccionar_grupo')



# Configuración de carpeta temporal para subir archivos
UPLOAD_FOLDER = 'uploads/qr_codes'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}

# Asegurarse de que existe la carpeta de uploads
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def decodificar_qr(ruta_imagen):
    """
    Decodifica un código QR de una imagen y extrae el link
    Retorna el link o None si no se pudo decodificar
    """
    try:
        # Intentar con OpenCV
        imagen = cv2.imread(ruta_imagen)
        if imagen is not None:
            qr_codes = decode(imagen)
            
            if qr_codes:
                for qr in qr_codes:
                    link = qr.data.decode('utf-8')
                    print(f"✅ QR decodificado: {link}")
                    return link
        
        # Si OpenCV no funciona, intentar con PIL
        imagen_pil = Image.open(ruta_imagen)
        qr_codes = decode(imagen_pil)
        
        if qr_codes:
            for qr in qr_codes:
                link = qr.data.decode('utf-8')
                print(f"✅ QR decodificado con PIL: {link}")
                return link
                
        print(f"⚠️ No se encontró QR en: {ruta_imagen}")
        return None
        
    except Exception as e:
        print(f"❌ Error decodificando QR en {ruta_imagen}: {e}")
        return None

def procesar_carpeta_qr(carpeta_path):
    """
    Procesa todos los archivos de imagen en una carpeta y extrae los links de los QR
    Retorna una lista de links encontrados
    """
    links = []
    archivos_procesados = 0
    
    print(f"🔍 Procesando carpeta: {carpeta_path}")
    
    # Listar todos los archivos en la carpeta
    archivos = sorted(os.listdir(carpeta_path))  # Ordenar para procesamiento consistente
    
    for filename in archivos:
        if allowed_file(filename):
            ruta_completa = os.path.join(carpeta_path, filename)
            print(f"📄 Procesando: {filename}")
            
            link = decodificar_qr(ruta_completa)
            if link:
                links.append(link)
                archivos_procesados += 1
    
    print(f"✅ Se procesaron {archivos_procesados} códigos QR")
    print(f"📋 Links encontrados: {len(links)}")
    
    return links


@app.route('/registro_automatico', methods=['GET', 'POST'])
def registro_automatico():
    """
    Ruta para el registro automático de QR codes usando la clase QRReaderWithDB
    """
    global verificador_registro, contra_db
    
    # Verificar que el verificador esté inicializado
    if verificador_registro is None:
        print("⚠️ verificador_registro no está inicializado")
        return redirect('/seleccionar_ciclo')
    
    if request.method == 'POST':
        # Caso 1: Finalizar proceso (igual que en /registro)
        finalizar = request.form.get('finalizar')
        if finalizar == 'true':
            try:
                conexion = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password=contra_db,
                    database="Semestre"
                )
                cursor = conexion.cursor()
                
                # Obtener el grupo
                cursor.execute("SELECT grupo FROM semestre LIMIT 1")
                resultado_grupo = cursor.fetchone()
                
                cursor.close()
                conexion.close()
                
                # Procesar el grupo obtenido
                if resultado_grupo:
                    grupo_seleccionado = resultado_grupo[0]
                    print(f"✅ Grupo seleccionado: {grupo_seleccionado}")
                    
                    conexion = mysql.connector.connect(
                        host="localhost",
                        user='root',
                        password=contra_db,
                        database=grupo_seleccionado
                    )
                    cursor = conexion.cursor()
                    
                    cursor.execute(f"UPDATE {grupo_seleccionado} SET inscrito = 1")
                    conexion.commit()
                    
                    cursor.execute(f"UPDATE {grupo_seleccionado} SET abrio = 0")
                    conexion.commit()
                    
                    cursor.execute(f"UPDATE {grupo_seleccionado} SET cerro = 0")
                    conexion.commit()
                    
                    cursor.close()
                    conexion.close()
                
                return redirect('/seleccionar_metodo')
                
            except Exception as e:
                print(f"❌ Error al finalizar el registro: {e}")
                return redirect('/seleccionar_metodo')
        
        # Caso 2: Procesar archivos QR (cuando se suben los archivos)
        # Verificar si se subieron archivos
        if 'qr_files' not in request.files:
            return jsonify({'error': 'No se enviaron archivos'}), 400
        
        files = request.files.getlist('qr_files')
        
        if not files or files[0].filename == '':
            return jsonify({'error': 'No se seleccionaron archivos'}), 400
        
        # Obtener el grupo seleccionado de la sesión
        grupo_seleccionado = session.get('grupo_seleccionado')
        if not grupo_seleccionado:
            return jsonify({'error': 'No se ha seleccionado un grupo'}), 400
        
        # Crear carpeta temporal para este proceso
        timestamp = int(time.time())
        carpeta_temp = os.path.join(UPLOAD_FOLDER, f'proceso_{timestamp}')
        os.makedirs(carpeta_temp, exist_ok=True)
        
        # Guardar todos los archivos
        print(f"📂 Guardando {len(files)} archivos...")
        for file in files:
            if file and allowed_file(file.filename):
                filename = file.filename
                filepath = os.path.join(carpeta_temp, filename)
                file.save(filepath)
                print(f"💾 Guardado: {filename}")
        
        # Procesar todos los QR y extraer links
        print("🔄 Iniciando decodificación de QR codes...")
        links = procesar_carpeta_qr(carpeta_temp)
        
        if not links:
            # Limpiar archivos temporales
            for filename in os.listdir(carpeta_temp):
                os.remove(os.path.join(carpeta_temp, filename))
            os.rmdir(carpeta_temp)
            
            return jsonify({
                'error': 'No se encontraron códigos QR válidos en los archivos',
                'archivos_procesados': len(files)
            }), 400
        
        # Registrar cada link uno por uno usando la clase QRReaderWithDB
        print(f"📝 Iniciando registro de {len(links)} links...")
        registros_exitosos = 0
        registros_fallidos = 0
        errores = []
        
        for idx, link in enumerate(links, 1):
            print(f"\n{'='*60}")
            print(f"🔄 Procesando link {idx}/{len(links)}")
            print(f"🔗 URL: {link[:80]}...")
            print(f"{'='*60}")
            
            try:
                # Usar el método process_qr_data del verificador_registro
                # Este método ya maneja toda la lógica de procesamiento
                verificador_registro.process_qr_data(link)
                
                # Esperar un momento para que se complete el procesamiento
                time.sleep(1)
                
                # Verificar si se procesó correctamente revisando los logs
                with verificador_registro.lock:
                    if verificador_registro.last_log_entries:
                        ultimo_log = verificador_registro.last_log_entries[-1]
                        if ultimo_log['status'] == 'Aceptado':
                            registros_exitosos += 1
                            print(f"✅ Registro {idx}/{len(links)} exitoso")
                        else:
                            registros_fallidos += 1
                            print(f"❌ Registro {idx}/{len(links)} falló")
                            errores.append(f"Link {idx}: {ultimo_log['status']}")
                    else:
                        registros_fallidos += 1
                        print(f"⚠️ No se pudo verificar el estado del registro {idx}")
                        errores.append(f"Link {idx}: No se pudo verificar estado")
                
                # Pausa entre registros para evitar sobrecarga
                time.sleep(2)
                
            except Exception as e:
                registros_fallidos += 1
                error_msg = f"Link {idx}: {str(e)}"
                errores.append(error_msg)
                print(f"❌ Error procesando link {idx}: {e}")
                time.sleep(1)
        
        # Limpiar archivos temporales
        print("\n🧹 Limpiando archivos temporales...")
        try:
            for filename in os.listdir(carpeta_temp):
                os.remove(os.path.join(carpeta_temp, filename))
            os.rmdir(carpeta_temp)
            print("✅ Archivos temporales eliminados")
        except Exception as e:
            print(f"⚠️ Error limpiando archivos temporales: {e}")
        
        # Imprimir resumen
        print(f"""
        ═══════════════════════════════════════
        📊 RESUMEN DEL PROCESO AUTOMÁTICO
        ═══════════════════════════════════════
        ✅ Registros exitosos: {registros_exitosos}
        ❌ Registros fallidos: {registros_fallidos}
        📋 Total de links: {len(links)}
        ═══════════════════════════════════════
        """)
        
        if errores:
            print("⚠️ Errores encontrados:")
            for error in errores:
                print(f"   - {error}")
        
        # Retornar resultado
        return jsonify({
            'success': True,
            'mensaje': 'Proceso completado',
            'registros_exitosos': registros_exitosos,
            'registros_fallidos': registros_fallidos,
            'total_links': len(links),
            'errores': errores if errores else None,
            'mostrar_finalizar': True  # Indica que debe mostrar el botón finalizar
        })
    
    # GET request - mostrar formulario de carga
    return render_template('registro_automatico.html')




# Actualizar la ruta /seleccionar_grupo para el método automático
@app.route('/seleccionar_grupo', methods=['GET', 'POST'])
def seleccionar_grupo():
    global bases_datos, verificador_registro, contra_db
    grupos = bases_datos
    
    if request.method == 'POST':
        if 'grupo' in request.form:
            grupo_seleccionado = request.form['grupo']
            print(f"🔧 Configurando grupo seleccionado (automático): {grupo_seleccionado}")
            session['grupo_seleccionado'] = grupo_seleccionado
            
            # Guardar en la BD temporal
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password=contra_db,
                database="Semestre"
            )
            cursor = conexion.cursor()
            
            cursor.execute("""
                UPDATE semestre SET grupo = %s
            """, (grupo_seleccionado,))
            print(f"✅ Grupo '{grupo_seleccionado}' guardado en la base de datos 'Semestre'.")
            conexion.commit()
            cursor.close()
            conexion.close()
            
            # Inicializar el verificador de registro con el grupo seleccionado
            db_config_registro = {
                'host': 'localhost',
                'user': 'root',
                'password': contra_db,
                'database': grupo_seleccionado
            }
            
            # Inicializar con escáner físico (puerto auto-detectado)
            # Para modo automático, no necesitamos el escáner físico
            verificador_registro = QRReaderWithDB(
                scanner_port=None,  # Sin escáner físico para modo automático
                db_config=db_config_registro
            )
            
            print("✅ Verificador de registro inicializado para modo automático")
            
            # Redirigir al registro automático
            return redirect('/registro_automatico')
    
    return render_template('seleccionar_grupo.html', grupos=grupos)

@app.route('/duda', methods=['GET'])
def duda():
    return render_template('duda.html')

@app.route('/seleccionar_ciclo', methods=['GET'])
def seleccionar_ciclo():
    global bases_datos
    grupos = bases_datos
    return render_template('seleccionar_ciclo.html', grupos=grupos)

@app.route('/configurar', methods=['GET', 'POST'])
def configurar():
    global bases_datos, verificador_registro
    grupos = bases_datos
    
    if request.method == 'POST':

        # Verificar si viene del formulario de grupo
        if 'grupo' in request.form:
            grupo_seleccionado = request.form['grupo']
            print(f"🔧 Configurando grupo seleccionado: {grupo_seleccionado}")
            session['grupo_seleccionado'] = grupo_seleccionado
            print(type(grupo_seleccionado))
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password= contra_db,
                database="Semestre" 
            )
            cursor = conexion.cursor()
            
            # Actualizar el registro existente con el grupo
            cursor.execute("""
                UPDATE semestre SET grupo = %s
            """, (grupo_seleccionado,))
            print(f"✅ Grupo '{grupo_seleccionado}' guardado en la base de datos 'Semestre'.")
            conexion.commit()
            cursor.close()
            conexion.close()

            # Inicializar el verificador de registro con el grupo seleccionado
            db_config_registro = {
                'host': 'localhost',
                'user': 'root',
                'password': 'P3l0n100j0t3$',
                'database': grupo_seleccionado
            }

            # Inicializar con escáner físico (puerto auto-detectado)
            verificador_registro = QRReaderWithDB(
                scanner_port=None,  # Auto-detectar puerto
                db_config=db_config_registro
            )

            return redirect('/registro')  

    # Para requests GET
    semestre = session.get('semestre')
    grupo_seleccionado = request.args.get('grupo')
    
    return render_template('seleccionar_ciclo.html', grupos=grupos, semestre=semestre, grupo_seleccionado=grupo_seleccionado)

@app.route('/registro', methods=['GET','POST'])
def registro():
    global verificador_registro
    
    if verificador_registro is None:
        return redirect('/seleccionar_ciclo')
    
    if request.method == 'POST':

        finalizar = request.form.get('finalizar')
        try: 
            if finalizar == 'true':
                conexion = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password= contra_db,
                    database="Semestre"
                )

                cursor = conexion.cursor()
                
                # Obtener el grupo
                cursor.execute("SELECT grupo FROM semestre LIMIT 1")
                resultado_grupo = cursor.fetchone()

                # Cerrar la conexión a la base de datos
                cursor.close()
                conexion.close()
                
                # Procesar el grupo obtenido
                if resultado_grupo:
                    grupo_seleccionado = resultado_grupo[0]  # Extraer el valor del grupo
                    print(f"✅ Grupo seleccionado: {grupo_seleccionado}")

                conexion = mysql.connector.connect(
                    host="localhost",
                    user = 'root',
                    password = contra_db,
                    database = grupo_seleccionado
                )
                cursor = conexion.cursor()

                cursor.execute(f"UPDATE {grupo_seleccionado} SET inscrito = 1")
                conexion.commit()

                cursor.execute(f"UPDATE {grupo_seleccionado} SET abrio = 0")
                conexion.commit()
                cursor.execute(f"UPDATE {grupo_seleccionado} SET cerro = 0")
                conexion.commit()
                cursor.close()
                conexion.close()


            return redirect('/seleccionar_ciclo')
        except Exception as e:  
            print(f"❌ Error al finalizar el registro: {e}")
            return redirect('/seleccionar_ciclo')
    return render_template('registro_scanner.html')


@app.route('/procesar_url', methods=['POST'])
def procesar_url():
    global verificador_registro
    
    if verificador_registro is None:
        return jsonify({
            'success': False,
            'message': 'Verificador no inicializado. Configura primero el ciclo escolar.'
        }), 400
    
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'message': 'URL no proporcionada en la solicitud'
            }), 400
        
        url = data['url'].strip()
        
        # VALIDACIONES MEJORADAS
        if not url:
            return jsonify({
                'success': False,
                'message': 'URL vacía'
            })
        
        if len(url) < 20:
            return jsonify({
                'success': False,
                'message': 'URL muy corta, posiblemente incompleta. Verifica el escaneo completo.'
            })
        
        if not url.startswith(('http://', 'https://')):
            return jsonify({
                'success': False,
                'message': 'URL no válida. Debe comenzar con http:// o https://'
            })
        
        # Verificar que sea SAES o DAE antes de procesar
        es_saes = verificador_registro.es_enlace_saes(url)
        es_dae = verificador_registro.es_enlace_dae(url)
        
        if not (es_saes or es_dae):
            return jsonify({
                'success': False,
                'message': 'URL no reconocida. Solo se procesan enlaces de SAES (horarios) o DAE (credenciales).'
            })
        
        print(f"🔍 Procesando URL {'SAES' if es_saes else 'DAE'}: {url}")
        
        # Procesar la URL
        success = verificador_registro.procesar_url(url)
        
        if success:
            tipo = 'horario' if es_saes else 'credencial'
            return jsonify({
                'success': True,
                'message': f'✅ {tipo.capitalize()} procesado y guardado correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No se pudo procesar la URL. Verifica que el contenido sea válido.'
            })
    
    except Exception as e:
        print(f"❌ Error en /procesar_url: {e}")
        return jsonify({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }), 500


@app.errorhandler(404)
def not_found(e):
    return render_template('404_registro.html'), 404

@app.route('/reset')
def reset():
    return render_template('reset.html')


@app.route('/confirmacion', methods=['POST'])
def confirmacion():
    # ✅ Paso 1: primera confirmación
    if 'confirmación' in request.form:
        confirmacion_valor = int(request.form.get('confirmación'))
        if confirmacion_valor == 1:
            session['confirmacion'] = True
            return render_template('reset.html', confirmacion=1)
        elif confirmacion_valor == 2:
            session.clear()
            return redirect('/')

    # ✅ Paso 2: segunda confirmación
    elif 'segunda_confirmación' in request.form:
        segunda_confirmacion_valor = int(request.form.get('segunda_confirmación'))
        if segunda_confirmacion_valor == 1 and session.get('confirmacion'):
            session['segunda_confirmacion'] = True
            return render_template('reset.html', confirmacion=1, segunda_confirmacion=1)
        else:
            session.clear()
            return redirect('/')

    # ✅ NUEVO PASO INTERMEDIO: Verificación de Contraseña
    elif 'password_input' in request.form:
        password = request.form.get('password_input')
        
        # Verificamos la contraseña hardcodeada
        if password == "P3l0n100j0t3$":
            session['contra_inicial'] = True
            # Al ser correcta, devolvemos 'contra_inicial=1' para desbloquear el siguiente paso en HTML
            return render_template('reset.html', confirmacion=1, segunda_confirmacion=1, contra_inicial=1)
        else:
            # Si es incorrecta, borramos sesión y mandamos al inicio
            session.clear()
            return redirect('/')

    # ✅ Paso 3: selección de semestre (Tu código existente ya protege esto con el if not session...)
    elif 'semestre' in request.form:
        if not session.get('contra_inicial'):
            return redirect('/')
        
        # ... (Resto de tu código del paso 3) ...

        semestre_valor = int(request.form.get('semestre'))
        session['semestre'] = semestre_valor  

        try:
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password= contra_db,
                database="Semestre"
            )
            cursor = conexion.cursor()
            cursor.execute("UPDATE semestre SET semestre = %s", (semestre_valor,))
            conexion.commit()
            cursor.close()
            conexion.close()
            print(f"✅ Semestre actualizado a: {semestre_valor}")
        except Exception as e:
            print(f"❌ Error al actualizar semestre: {e}")
            session.clear()
            return redirect('/')

        return render_template('reset.html', confirmacion=1, segunda_confirmacion=1, semestre=semestre_valor)

    # ✅ Paso 4: selección de grupos
    elif '1_2_TM' in request.form or '3_4_CM' in request.form:
        if not session.get('semestre'):
            return redirect('/')

        grupos_inputs = [
            "1_2_TM",
            "3_4_CM", "3_4_AM", "3_4_MM", "3_4_IM", "3_4_PM", "3_4_EM", "3_4_LM",
            "5_6_CM", "5_6_AM", "5_6_MM", "5_6_IM", "5_6_PM", "5_6_EM", "5_6_LM"
        ]

        grupos = {}
        try:
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password= contra_db,
                database="Semestre"
            )
            cursor = conexion.cursor()

            for grupo in grupos_inputs:
                valor = request.form.get(grupo)
                grupos[grupo] = int(valor) if valor and valor.isdigit() else 0
                cursor.execute(f"UPDATE semestre SET {grupo} = %s", (grupos[grupo],))
                print(f"📌 {grupo}: {grupos[grupo]}")

            conexion.commit()
            cursor.close()
            conexion.close()
            print("✅ Grupos actualizados correctamente.")
        except Exception as e:
            print(f"❌ Error al procesar los grupos: {e}")
            session.clear()
            return redirect('/')

        session['grupos'] = True
        return render_template('reset.html', confirmacion=1, segunda_confirmacion=1, semestre=1, grupos=1)

    # ❌ Si alguien entra directo a /confirmacion sin datos → al inicio
    return redirect('/')


@app.route('/segunda_confirmacion', methods=['POST'])
def segunda_confirmacion():
    if not session.get('grupos'):
        return redirect('/')

    contraseña = request.form.get('contraseña')
    if contraseña == 'P3l0n100j0t3$': # Contraseña correcta
        excluir = {'Pases_salida', 'Semestre', 'Suspensiones', 'sys', 'mysql', 'information_schema', 'performance_schema'}

        try:
            conexion = mysql.connector.connect(
                host='localhost',
                user='root',
                password= contra_db
            )
            cursor = conexion.cursor()
            cursor.execute("SHOW DATABASES")
            bases = cursor.fetchall()

            for (base,) in bases:
                if base not in excluir:
                    try:
                        cursor.execute(f"DROP DATABASE `{base}`")
                        print(f"✅ Base de datos '{base}' eliminada.")
                    except Exception as e:
                        print(f"❌ Error al eliminar '{base}': {e}")

            cursor.close()
            conexion.close()

        except Exception as error:
            print(f"❌ Error de conexión: {error}")
            session.clear()
            return redirect('/')
    else:
        print("❌ Contraseña incorrecta")
        session.clear()
        return redirect('/')

    # ✅ limpiar la sesión para que al refrescar no se quede en reset.html
    session.clear()
    return render_template('reset.html', confirmacion=1, segunda_confirmacion=1, borrado_exitoso=True)



@app.route('/admin_cambios', methods=['GET', 'POST'])
def admin_cambios():
    global bases_datos
    # Lista completa de bases de datos
    grupos = bases_datos


    horarios = []
    grupo_seleccionado = None
    dia_seleccionado = None

    if request.method == 'POST':
        grupo_seleccionado = request.form['grupo']
        dia_seleccionado = request.form['dia']
        fecha = date.today().isoformat()  # Fecha actual en formato ISOhttps://servicios.dae.ipn.mx/vcred/?h=9ad7b24bba72b7e060434c58465d65576ea67274102f203b1bfab95b1fabaaab
        
        horas = request.form.getlist('horas')

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password= contra_db,
            database="Pases_salida"  # ← base de datos = nombre del grupo
        )
        cursor = conexion.cursor()

        for hora in horas:
            inicio, fin = hora.split('-')
            cursor.execute("""
                INSERT INTO modificaciones_temporales (grupo, dia_semana, fecha_aplicacion, hora_inicio, hora_fin)
                VALUES (%s, %s, %s, %s, %s)
            """, (grupo_seleccionado, dia_seleccionado, fecha, inicio, fin))

        conexion.commit()
        cursor.close()
        conexion.close()

        return redirect('/admin_cambios')

    elif request.method == 'GET':
        dias_semana = {
            0: 'lunes',      # Lunes
            1: 'martes',     # Martes
            2: 'miercoles',  # Miércoles
            3: 'jueves',     # Jueves
            4: 'viernes',    # Viernes
            5: 'sabado',     # Sábado
            6: 'domingo'     # Domingo
        }
        dia_actual = datetime.now().weekday()
        dia_seleccionado = dias_semana.get(dia_actual, 'desconocido')
        grupo_seleccionado = request.args.get('grupo')

        if grupo_seleccionado and dia_seleccionado:
            try:
                conexion = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password= contra_db,
                    database=grupo_seleccionado  # ← base de datos = nombre del grupo
                )
                cursor = conexion.cursor()
                tabla_horario = "Horario_Grupal"

                query = f"""
                SELECT {dia_seleccionado}
                FROM `{tabla_horario}`
                WHERE {dia_seleccionado} IS NOT NULL AND {dia_seleccionado} != '' AND {dia_seleccionado} != '-'
                """
                cursor.execute(query)
                resultados = cursor.fetchall()

                horarios_vistos = set()
                for fila in resultados:
                    hora_raw = fila[0]
                    partes = hora_raw.strip().split(" - ")
                    if len(partes) == 2:
                        hora_inicio, hora_fin = partes
                        if (hora_inicio, hora_fin) not in horarios_vistos:
                            horarios.append((hora_inicio, hora_fin))
                            horarios_vistos.add((hora_inicio, hora_fin))

                horarios.sort()  # ordenar por hora de inicio

                cursor.close()
                conexion.close()

            except mysql.connector.Error as e:
                print(f"❌ Error conectando a la base de datos del grupo: {e}")

    return render_template(
        'admin_cambios.html',
        grupos=grupos,
        horarios=horarios,
        hoy=date.today().isoformat(),
        grupo_seleccionado=grupo_seleccionado,
        dia_seleccionado=dia_seleccionado
    )



@app.route('/suspension', methods=['GET'])
def suspender():
    global bases_datos
    grupos = bases_datos
    return render_template('suspension.html', grupos=grupos)


@app.route('/suspensiones', methods=['GET', 'POST'])
def suspensiones():
    global bases_datos
    grupos = bases_datos

    grupo_seleccionado = session.get('grupo_seleccionado')
    boleta_suspendida = session.get('boleta_suspendida')
    boletas = []

    if request.method == 'POST':
        print(request.form)  # 🔍 Muy útil
        if 'grupo' in request.form and 'boleta' not in request.form:
            grupo_seleccionado = request.form['grupo']
            session['grupo_seleccionado'] = grupo_seleccionado

            try:
                conexion = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password= contra_db,
                    database=grupo_seleccionado
                )
                cursor = conexion.cursor()
                cursor.execute(f"SELECT boleta FROM `{grupo_seleccionado}`")
                resultados = cursor.fetchall()
                cursor.close()
                conexion.close()
                boletas = [fila[0] for fila in resultados]
            except Exception as e:
                print(f"❌ Error al conectar o consultar: {e}")
                boletas = []

            return render_template('suspension.html', grupos=grupos, grupo_seleccionado=grupo_seleccionado, boletas=boletas)

        elif 'boleta' in request.form:
            boleta_suspendida = request.form['boleta']
            session['boleta_suspendida'] = boleta_suspendida
            grupo_seleccionado = session.get('grupo_seleccionado')
            fecha_inicio = request.form.get('fecha_inicio')
            fecha_fin = request.form.get('fecha_fin')



            try:
                conexion = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password= contra_db,
                    database=grupo_seleccionado
                )
                cursor = conexion.cursor()

                # Obtener nombre del alumno (asumiendo que está en la tabla principal)
                cursor.execute(f"SELECT nombre FROM `{grupo_seleccionado}` WHERE boleta = %s", (boleta_suspendida,))
                resultado = cursor.fetchone()
                nombre_alumno = resultado[0] if resultado else 'Desconocido'
                cursor.close()
                conexion.close()

            except Exception as e:
                print(f"❌ Error al insertar suspensión: {e}")

            try: 
                grupo_seleccionado = session.get('grupo_seleccionado')
                connection = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password= contra_db,
                )
                cursor = connection.cursor()

                usar = """ 
                    USE Suspensiones
                    """
                cursor.execute(usar)
                query = """
                    INSERT INTO suspensiones_registro (boleta, grupo, nombre_alumno, fecha_inicio, fecha_fin)
                    VALUES (%s, %s, %s, %s, %s)
                """
                values = (boleta_suspendida, grupo_seleccionado, nombre_alumno, fecha_inicio, fecha_fin)

                cursor.execute(query, values)
                connection.commit()

                cursor.close()
                connection.close()

            except Exception as e:
                print(f"❌ Error al insertar suspensión: {e}")

            return render_template('suspension.html', grupos=grupos, grupo_seleccionado=None, boletas=boletas, boleta_suspendida=None)

    # En caso de GET
    if grupo_seleccionado:
        try:
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password= contra_db,
                database=grupo_seleccionado
            )
            cursor = conexion.cursor()
            cursor.execute(f"SELECT boleta FROM `{grupo_seleccionado}`")
            resultados = cursor.fetchall()
            boletas = [fila[0] for fila in resultados]
            cursor.close()
            conexion.close()
        except Exception as e:
            print(f"❌ Error al obtener boletas en GET: {e}")

    return render_template('suspension.html', grupos=grupos, grupo_seleccionado=grupo_seleccionado, boletas=boletas, boleta_suspendida=boleta_suspendida)


@app.route('/grafica')
def mostrar_grafica():
    conexion = None
    cursor = None
    
    # Listas por defecto en ceros
    datos_entrada = [0, 0, 0, 0, 0]
    datos_salida = [0, 0, 0, 0, 0]
    
    etiquetas = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password=contra_db, 
            database="Semestre"
        )
        cursor = conexion.cursor()

        # --- CONSULTA 1: REGISTROS (ENTRADA) ---
        query_entrada = "SELECT lunes, martes, miercoles, jueves, viernes FROM registros LIMIT 1"
        cursor.execute(query_entrada)
        res_entrada = cursor.fetchall()
        
        if res_entrada:
            datos_entrada = list(res_entrada[0])

        # --- CONSULTA 2: REGISTROS_SALIDA ---
        query_salida = "SELECT lunes, martes, miercoles, jueves, viernes FROM registros_salida LIMIT 1"
        cursor.execute(query_salida)
        res_salida = cursor.fetchall()

        if res_salida:
            datos_salida = list(res_salida[0])

    except Error as e:
        print(f"❌ Error DB: {e}")
        return "Error en la base de datos", 500
        
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()

    # Enviamos AMBAS listas al template con nombres diferentes
    return render_template('grafica.html', 
                            labels=etiquetas, 
                            data_in=datos_entrada, 
                            data_out=datos_salida)



@app.route('/acceso_verificacion', methods=['GET', 'POST'])
def acceso_verificacion():
    try:
        # Asegúrate de usar la variable contra_db que ya tienes en tu código
        conexion = mysql.connector.connect(host="localhost", user="root", password=contra_db, database="Semestre")
        cursor = conexion.cursor(dictionary=True)
        
        # Crear la tabla y la columna si no existen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acceso (
                verificacion VARCHAR(255)
            )
        """)
        conexion.commit()

        if request.method == 'POST':
            data = request.json
            accion = data.get('accion')

            # --- FASE 1: Verificación de contraseña ---
            if accion == 'verificar_password':
                if data.get('password') == "C16_4dm1n_4cC3s0":
                    cursor.execute("SELECT verificacion FROM acceso LIMIT 1")
                    fila = cursor.fetchone()
                    
                    estado_actual = "vacio"
                    if fila and fila['verificacion']:
                        texto_descifrado = descifrar_texto(fila['verificacion'])
                        if texto_descifrado == "Acceso_concedido":
                            estado_actual = "concedido"
                            
                    return jsonify({"status": "success", "estado": estado_actual})
                else:
                    return jsonify({"status": "error", "mensaje": "Contraseña incorrecta"})

            # --- FASE 2: Subir cambios ---
            elif accion == 'actualizar_acceso':
                nuevo_estado = data.get('estado')
                
                # TRUNCATE borra todos los registros y previene que haya más de 1 fila por error
                cursor.execute("TRUNCATE TABLE acceso")
                
                if nuevo_estado == 'conceder':
                    texto_cifrado = cifrar_texto("Acceso_concedido")
                    cursor.execute("INSERT INTO acceso (verificacion) VALUES (%s)", (texto_cifrado,))
                
                conexion.commit()
                return jsonify({"status": "success"})
                
    except Error as e:
        print(f"Error de BD: {e}")
        return jsonify({"status": "error", "mensaje": "Error de conexión a la base de datos"})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conexion' in locals() and conexion.is_connected(): conexion.close()

    return render_template('verificacion.html')


if __name__ == '__main__':
    # Crear bases de datos necesarias
    if 'bases_datos' in globals():
        crear_bases_si_no_existen(bases_datos)
    print("🚀 Iniciando panel de administración en la red...")
    
    # Cambiamos el puerto aquí a 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
"""
Codigo en mysql para agregar una base de datos nueva 
CREATE DATABASE 4IM1;  --Cambiar el grupo 

"""



