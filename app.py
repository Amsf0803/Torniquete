from flask import request, redirect, Flask, Response, render_template, jsonify, url_for, flash, session
import cv2
import threading
import numpy as np
from pyzbar import pyzbar
import pygame
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, date
import mysql.connector
from mysql.connector import Error
import random
import serial
import time



intento = 0
while True:
    try:
        arduino = serial.Serial(port='/dev/ttyUSB0', baudrate=9600, timeout=1)
        print("✅ Conexión con Arduino establecida correctamente")
        print(f"Puerto: {intento}")
        break
    except serial.SerialException as e:
        print(f"❌ Error al conectar con Arduino: {e}")
        intento += 1
        if intento >= 5:
            print("❌ No se pudo conectar con Arduino después de varios intentos")
            arduino = None
            break



""" 
Prueba de conexión con Arduino

while True:
    opcion = input("Envia 1 para encender o 2 para apagar led: ")
    if opcion == '1':
        arduino.write(b'1')
    elif opcion == '2':
        arduino.write(b'0')
    else:
        print("Opción no válida")

Codigo en el arduino:

int led =7;
void setup() {
    pinMode(led, OUTPUT); 
    Serial.begin(9600);  
}
void loop() {
    if (Serial.available()) {          
        char comando = Serial.read();     
        if (comando == '1') {             
        digitalWrite(led, HIGH);         
        } else if (comando == '0') {      
        digitalWrite(led, LOW);          
        }
    }
}

"""


class QRHorarioVerificador:
    def __init__(self, camera_index=0, db_config=None, bases_datos=None):
        """
        Inicializa el verificador de horarios por QR para web
        """
        

        # Configuración de cámara
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Control de threading
        self.lock = threading.Lock()
        self.running = True
        
        # Lista para evitar duplicados y logs
        self.scanned_codes = []
        self.last_log_entries = []

        self.resultado_mochila_por_boleta = {} 
        # Configuración de base de datos
        if db_config is None:
            self.db_config = {
                'host': 'localhost',
                'user': 'root',
                'password': 'P3l0n100j0t3$'  # CAMBIAR POR TU PASSWORD
            }
        else:
            self.db_config = db_config
        # Lista de bases de datos a verificar
        if bases_datos is None:
            self.bases_datos = [
                '2TM1', '2TM2', '2TM3', '2TM4', '2TM5', '2TM6', '2TM7', '2TM8', '2TM9', '2TM10',
                '2TM11', '2TM12', '2TM13', '2TM14', '2TM15', '2TM16', '2TM17', '2TM18', '2TM19', '2TM20',
                '4CM1', '4CM2', '6CM1', '6CM2',
                '4MM1', '4MM2', '4MM3', '4MM4', '6MM1', '6MM2', '6MM3', '6MM4',
                '4IM1', '6IM1', '4PM1', '6PM1',
                '4EM1', '4EM2', '4EM3', '6EM1', '6EM2', '6EM3',
                '4LM1', '4LM2', '4LM3', '4LM4', '6LM1', '6LM2', '6LM3', '6LM4',
                '4AM1', '4AM2', '6AM1', '6AM2'
            ]
        else:
            self.bases_datos = bases_datos
        
        # Mapeo de días
        self.dias_semana = {
            0: 'lunes',      # Lunes
            1: 'martes',     # Martes
            2: 'miercoles',  # Miércoles
            3: 'jueves',     # Jueves
            4: 'viernes',    # Viernes
            5: 'sabado',     # Sábado
            6: 'domingo'     # Domingo
        }
        
        #Registro de excel
        

        # Inicializar audio
        self.audio_azteca()
    
    def audio_azteca(self):
        """Inicializa el sistema de audio"""
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.audio_activo = True
            print("✅ Sistema de audio inicializado correctamente")
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
        """Reproduce sonido de éxito (horario encontrado)"""
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
        """Reproduce sonido de error (horario no encontrado)"""
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
            r'.*vcred/\?h=.*',
            r'.*dae.*cred.*',
        ]
        return any(re.search(patron, url, re.IGNORECASE) for patron in patrones_dae)
    
    def extraer_boleta_de_url(self, url):
        """Extrae el número de boleta desde la URL de DAE"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            print("🌐 Solicitando página del QR...")
            response = requests.get(url, headers=headers, timeout=10)
            print("✅ Página recibida, extrayendo boleta...")

            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Método principal: buscar elemento por clase 'boleta'
            boleta_element = soup.find('div', class_='boleta')
            if boleta_element:
                boleta_text = boleta_element.get_text().strip()
                numeros = re.findall(r'\d{10}', boleta_text)
                if numeros:
                    return numeros[0]
            
            # Método alternativo: buscar en todo el HTML
            texto_completo = soup.get_text()
            
            # Buscar patrón "Boleta: XXXXXXXXXX"
            patron_boleta = r'boleta[:\s]*(\d{10})'
            match_boleta = re.search(patron_boleta, texto_completo, re.IGNORECASE)
            if match_boleta:
                return match_boleta.group(1)
            
            # Método adicional: buscar cualquier secuencia de 10 dígitos
            numeros_10_digitos = re.findall(r'\b\d{10}\b', texto_completo)
            if numeros_10_digitos:
                return numeros_10_digitos[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Error extrayendo boleta de URL: {e}")
            return None

    def buscar_tabla_horario(self, boleta):
        """Busca la tabla del horario en las bases de datos disponibles - SOLO RETORNA LA BASE DE DATOS"""
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
                    print(f"✅ Tabla '{boleta}' encontrada en base de datos '{base_datos}'")
                    cursor.close()
                    connection.close()
                    return base_datos  # SOLO retornar la base de datos, no consultar inscrito aquí
                
                cursor.close()
                connection.close()
                
            except Error as e:
                print(f"⚠️ Error verificando base de datos '{base_datos}': {e}")
                continue
        
        print(f"❌ No se encontró tabla para la boleta '{boleta}' en ninguna base de datos")
        return None

    def obtener_horario_dia(self, boleta, base_datos, dia):
        """Obtiene el horario específico del día para una boleta"""
        try:
            db_config_temp = self.db_config.copy()
            db_config_temp['database'] = base_datos
            
            connection = mysql.connector.connect(**db_config_temp)
            cursor = connection.cursor()
            
            query = f"""
            SELECT materia, profesor, {dia}
            FROM `{boleta}`
            WHERE {dia} IS NOT NULL AND {dia} != '' AND {dia} != '-'
            ORDER BY {dia}
            """
            
            cursor.execute(query)
            resultados = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            if resultados:
                horarios_dia = []
                for materia, profesor,horario in resultados:
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

    def get_inscrito(self, boleta, grupo):
        """Devuelve el valor de inscrito (0,1,2) o None si no existe - MÉTODO LIMPIO"""
        try:
            conexion = mysql.connector.connect(
                host="localhost",
                user="root",
                password="P3l0n100j0t3$",
                database=grupo
            )
            cursor = conexion.cursor()

            query = f"SELECT inscrito FROM {grupo} WHERE boleta = %s LIMIT 1"
            cursor.execute(query, (boleta,))
            resultado = cursor.fetchone()

            cursor.close()
            conexion.close()

            if resultado:
                return resultado[0]  # puede ser 0, 1 o 2
            else:
                return None
        except mysql.connector.Error as e:
            print(f"❌ Error en get_inscrito: {e}")
            return None

    def procesar_credencial_qr(self, url):
        """Procesa una credencial QR de DAE - CORREGIDO"""
        print(f"\n🔍 Procesando credencial DAE...")

        boleta = self.extraer_boleta_de_url(url)
        if not boleta:
            print("❌ No se pudo extraer el número de boleta")
            self.play_error_sound()
            return False

        # Buscar la base de datos que contiene la tabla del alumno
        base_datos_encontrada = self.buscar_tabla_horario(boleta)
        if not base_datos_encontrada:
            print("❌ No se encontró horario para esta boleta")
            self.play_error_sound()
            return {
                "boleta": boleta,  # Devolver la boleta aunque no se encuentre
                "status": "Error",
                "puede_entrar": False,
                "puede_salir": False,
                "mensaje": "No se pudo procesar QR",
                "horarios": []
            }

        # Consultar el valor de inscrito de forma independiente
        inscrito_valor = self.get_inscrito(boleta, base_datos_encontrada)
        
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
                    print(f"✅ Tabla '{boleta}' encontrada en base de datos '{base_datos}'")
                    query = f"""
                    SELECT boleta, nombre, inscrito
                    FROM {base_datos}.{base_datos}
                    WHERE boleta = '{boleta}'
                    """
                    cursor.execute(query)
                    resultado = cursor.fetchone()

                    if resultado:
                        boleta_db, nombre, inscrito_db = resultado  # Usar variable local
                        if inscrito_db == 1:
                            print(f"✅ Credencial '{boleta}' válida")

                            # Obtener estado de acceso/salida - PASAR EL VALOR DE INSCRITO
                            estado = self.obtener_estado_acceso_salida(boleta, inscrito_valor=inscrito_db)
                            puede_entrar = estado["acceso"]
                            puede_salir = estado["salir"]

                            # Registrar en Excel solo si hay entrada o salida permitida
                            if puede_entrar or puede_salir:
                                self.registrar_acceso_excel(boleta, nombre, base_datos, puede_entrar, puede_salir)
                            else:
                                print("⏳ Aún no es hora de entrada ni salida")

                        elif inscrito_db == 0:
                            print(f"❌ Credencial '{boleta}' no válida")
                    else:
                        print("No se encontró la boleta en la base de datos.")

                cursor.close()
                connection.close()

            except Error as e:
                print(f"⚠️ Error verificando base de datos '{base_datos}': {e}")

        # Obtener día actual
        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')
        
        print(f"📅 Día actual: {dia_nombre}")
        
        # Verificar si es fin de semana
        if dia_actual >= 5:
            print("🏖️ Es fin de semana - No hay clases programadas")
            self.play_error_sound()
            return False
        
        # Obtener horario del día
        horarios_dia = self.obtener_horario_dia(boleta, base_datos_encontrada, dia_nombre)
        
        if not horarios_dia:
            print(f"❌ No hay clases programadas para {dia_nombre}")
            self.play_error_sound()
            return False
        
        # Reproducir sonido de éxito
        self.play_success_sound()
        return True
    


    def detectar_qr(self, frame):
        """Detecta códigos QR en el frame"""
        codigos = pyzbar.decode(frame)
        
        for codigo in codigos:
            try:
                contenido = codigo.data.decode('utf-8')
                
                if contenido in self.scanned_codes:
                    continue
                
                if contenido.startswith(('http://', 'https://')) and self.es_enlace_dae(contenido):
                    print(f"\n📱 Credencial DAE detectada!")
                    
                    # Reproducir sonido de escaneo
                    self.play_scan_sound()
                    
                    self.scanned_codes.append(contenido)
                    
                    # Procesar credencial y crear log
                    resultado = self.procesar_credencial_qr(contenido)

                    if not resultado or not isinstance(resultado, dict):
                        continue  # o puedes hacer un log o print
                    
                    log_entry = {
                        "id": len(self.last_log_entries) + 1,
                        "boleta": resultado['boleta'],
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": resultado['status'],
                        "puede_entrar": resultado['puede_entrar'],
                        "puede_salir": resultado['puede_salir'],
                        "mensaje": resultado['mensaje'],
                        "horarios": resultado['horarios']
                    }
                    
                    with self.lock:
                        self.last_log_entries.append(log_entry)
                        if len(self.last_log_entries) > 10:
                            self.last_log_entries.pop(0)
                    
                    if len(self.scanned_codes) > 20:
                        self.scanned_codes = self.scanned_codes[-10:]
                
                elif contenido.startswith(('http://', 'https://')):
                    print(f"⚠️ QR detectado pero no es una credencial DAE válida")
                
                puntos = codigo.polygon
                if len(puntos) == 4:
                    pts = np.array([[punto.x, punto.y] for punto in puntos], np.int32)
                    color = (0, 255, 0) if self.es_enlace_dae(contenido) else (0, 255, 255)
                    cv2.polylines(frame, [pts], True, color, 2)
                
                x, y, w, h = codigo.rect
                texto = "Credencial DAE" if self.es_enlace_dae(contenido) else "QR Detectado"
                color = (0, 255, 0) if self.es_enlace_dae(contenido) else (0, 255, 255)
                cv2.putText(frame, texto, (x, y - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
            except UnicodeDecodeError:
                print("❌ Error decodificando QR")
                continue
        
        return frame
    
    def get_frame(self):
        """Obtiene frame de la cámara con detección de QR"""
        with self.lock:
            ret, frame = self.cap.read()
            if not ret:
                return None
            
            # Agregar información en pantalla
            cv2.putText(frame, "Verificador de Horarios", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Dia: {self.dias_semana.get(datetime.now().weekday(), 'N/A')}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), 
                       (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Detectar QR en el frame
            frame = self.detectar_qr(frame)
            
            return frame
    
    def generate_frames(self):
        """Genera frames para streaming de video"""
        while self.running:
            frame = self.get_frame()
            if frame is None:
                continue
                
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    def get_log_entries(self):
        """Obtiene las entradas del log"""
        with self.lock:
            return self.last_log_entries.copy()
    
    def stop(self):
        """Detiene el verificador"""
        self.running = False
        if self.cap.isOpened():
            self.cap.release()
    


    def boleta(self, url):
        """Obtiene el número de boleta del usuario"""
        boleta = self.extraer_boleta_de_url(url)
        return boleta 



    def obtener_estado_acceso_salida(self, boleta, inscrito_valor=None):
        """Verifica si el usuario está inscrito y controla acceso/salida - CORREGIDO"""
        acceso = False
        salir = False

        base_datos = self.buscar_tabla_horario(boleta)
        if not base_datos:
            return {"acceso": acceso, "salir": salir}

        # Si no se pasa inscrito_valor, consultarlo de forma limpia
        if inscrito_valor is None:
            inscrito = self.get_inscrito(boleta, base_datos)
        else:
            inscrito = inscrito_valor

        if inscrito != 1:
            print(f"El usuario con boleta {boleta} no está inscrito (valor={inscrito})")
            return {"acceso": acceso, "salir": salir}

        dia_actual = datetime.now().weekday()
        dia_nombre = self.dias_semana.get(dia_actual, 'desconocido')

        horarios_dia = self.obtener_horario_dia(boleta, base_datos, dia_nombre)
        if not horarios_dia:
            return {"acceso": acceso, "salir": salir}

        primera_info, ultima_info = self.obtener_primera_y_ultima_hora(horarios_dia)
        if not (primera_info and ultima_info):
            return {"acceso": acceso, "salir": salir}

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

        if inscrito == 1:
            # Verificar pase temporal
            try:
                conexion_pase = mysql.connector.connect(
                    host=self.db_config['host'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    database="Pases_salida"
                )
                cursor_pase = conexion_pase.cursor(dictionary=True)

                grupo_actual = base_datos

                cursor_pase.execute("""
                    SELECT hora_inicio, hora_fin
                    FROM modificaciones_temporales
                    WHERE grupo = %s
                """, (grupo_actual,))
                pase = cursor_pase.fetchone()
                print(f"Pase temporal encontrado: {pase}")
                cursor_pase.close()
                conexion_pase.close()

                # Conexión al grupo actual
                conexion_repit = mysql.connector.connect(
                    host=self.db_config['host'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    database=f"{grupo_actual}"
                )
                cursor_repit = conexion_repit.cursor(dictionary=True)

                # ======================
                # Checar si ya abrió
                # ======================
                consulta_check_a = f"""
                    SELECT abrio FROM {grupo_actual}
                    WHERE boleta = %s
                """
                cursor_repit.execute(consulta_check_a, (boleta,))
                resultado_a = cursor_repit.fetchone()

                bloquear_a = 0
                if resultado_a:
                    abrio_actual = int(resultado_a["abrio"]) if resultado_a["abrio"] is not None else 0  
                    if abrio_actual == 1:
                        bloquear_a = 1
                        print("Esta bloqueado (entrada)")
                    else:
                        bloquear_a = 0
                        print("Esta desbloqueado (entrada)")

                consulta_a = f"""
                    UPDATE {grupo_actual}
                    SET abrio = 1
                    WHERE boleta = %s
                """

                # ======================
                # Checar si ya cerró
                # ======================
                consulta_check_b = f"""
                    SELECT cerro FROM {grupo_actual}
                    WHERE boleta = %s
                """
                cursor_repit.execute(consulta_check_b, (boleta,))
                resultado_b = cursor_repit.fetchone()

                bloquear_b = 0
                if resultado_b:
                    cerro_actual = int(resultado_b["cerro"]) if resultado_b["cerro"] is not None else 0  
                    if cerro_actual == 1:
                        bloquear_b = 1
                        print("Esta bloqueado (salida)")
                    else:
                        bloquear_b = 0
                        print("Esta desbloqueado (salida)")

                consulta_b = f"""
                    UPDATE {grupo_actual}
                    SET cerro = 1
                    WHERE boleta = %s
                """

                # ======================
                # Lógica con pase temporal
                # ======================

                if pase:
                    hora_inicio_pase_time = datetime.strptime(str(pase['hora_inicio']), "%H:%M").time()
                    hora_fin_pase_time = datetime.strptime(str(pase['hora_fin']), "%H:%M").time()

                    hora_inicio_pase = datetime.combine(hoy, hora_inicio_pase_time)
                    hora_fin_pase = datetime.combine(hoy, hora_fin_pase_time)

                    hora_salida_minima = hora_inicio_pase - timedelta(minutes=15)

                    # Evaluar acceso y salida con pase
                    if hora_entrada_minima <= ahora <= hora_salida_minima:
                        if bloquear_a == 0:
                            acceso = True
                            try:
                                arduino.write(b'2')  # Enviar señal de acceso al Arduino
                                cursor_repit.execute(consulta_a, (boleta,))
                                conexion_repit.commit()
                                time.sleep(1.5)
                                arduino.write(b'0')
                            except Exception as e:
                                print(f"Error al enviar señal de acceso al Arduino: {e}")

                    if ahora >= hora_salida_minima:
                        if bloquear_b == 0:
                            salir = True
                            try:
                                arduino.write(b'2')  # Enviar señal de salida al Arduino
                                cursor_repit.execute(consulta_b, (boleta,))
                                conexion_repit.commit()
                                time.sleep(1.5)
                                arduino.write(b'0')
                            except Exception as e:
                                print(f"Error al enviar señal de salida al Arduino: {e}")

                    cursor_repit.close()
                    conexion_repit.close()
                    return {"acceso": acceso, "salir": salir, "bloquear_a": bloquear_a, "bloquear_b": bloquear_b}


            except mysql.connector.Error as e:
                print(f"Error pase temporal: {e}")

            # ======================
            # Sin pase temporal (horario normal)
            # ======================
            if hora_entrada_minima <= ahora <= hora_salida_dt:

                    if bloquear_a == 0:
                        acceso = True
                        try:
                            arduino.write(b'2')
                            cursor_repit.execute(consulta_a, (boleta,))
                            conexion_repit.commit()
                            time.sleep(1.5)
                            arduino.write(b'0')
                        except Exception as e:
                            print(f"Error al enviar señal de entrada al Arduino: {e}")

            if ahora >= hora_salida_minima:
                    if bloquear_b ==0:
                        salir = True
                        try:
                            arduino.write(b'2')
                            cursor_repit.execute(consulta_b, (boleta,))
                            conexion_repit.commit()
                            time.sleep(1.5)
                            arduino.write(b'0')
                        except Exception as e:
                            print(f"Error al enviar señal de salida al Arduino: {e}")

            cursor_repit.close()
            conexion_repit.close()
            pass


        else:
            print("El usuario no está inscrito, no puede acceder ni salir.")
            acceso = False
            salir = False
            return {"acceso": acceso, "salir": salir}
        
        return {"acceso": acceso, "salir": salir, "bloquear_a": bloquear_a, "bloquear_b": bloquear_b}



    def operacion_mochila(self, boleta):
        """Devuelve True o False solo una vez por boleta, con probabilidad controlada"""
        if boleta not in self.resultado_mochila_por_boleta:
            self.resultado_mochila_por_boleta[boleta] = random.choices(
                [True, False],
                weights=[1, 0]  # Ajusta aquí el balance True es que te toca revision false que no por ende el false tendra mas probabilidad de aparecer
            )[0] #Si los valores de weights es 0.2 , 0.8: Un 20% de probabilidad de que te toque revision y un 80% de probabilidad de que no
        
        return self.resultado_mochila_por_boleta[boleta]



# Configurar Flask
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'clave_secreta_segura'  # Necesaria para usar sesiones

# Configuración de la base de datos
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'P3l0n100j0t3$'  # CAMBIAR POR TU PASSWORD
}



try:
    # Conectar a la base de datos 'Semestre'
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password="P3l0n100j0t3$",
        database="Semestre"
    )

    cursor = conexion.cursor()

    # Obtener el valor del semestre
    cursor.execute("SELECT semestre FROM semestre LIMIT 1")
    resultado_semestre = cursor.fetchone()
    
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
        
        # Validar que el grupo esté en la lista correspondiente al semestre
        if resultado_semestre:
            semestre = int(resultado_semestre[0])
            
            if semestre == 1:
                bases_datos = [
                    '1TM1', '1TM2', '1TM3', '1TM4', '1TM5', '1TM6', '1TM7', '1TM8', '1TM9', '1TM10',
                    '1TM11', '1TM12', '1TM13', '1TM14', '1TM15', '1TM16', '1TM17', '1TM18', '1TM19', '1TM20',
                    '3CM1', '3CM2', '5CM1', '5CM2',
                    '3MM1', '3MM2', '3MM3', '3MM4', '5MM1', '5MM2', '5MM3', '5MM4',
                    '3IM1', '5IM1', '3PM1',
                    '3EM1', '3EM2', '3EM3', '5EM1', '5EM2', '5EM3',
                    '3LM1', '3LM2', '3LM3', '3LM4', '5LM1', '5LM2', '5LM3', '5LM4',
                    '3AM1', '3AM2', '5AM1', '5AM2',
                    'Pases_salida'
                ]
            elif semestre == 2:
                bases_datos = [
                    '2TM1', '2TM2', '2TM3', '2TM4', '2TM5', '2TM6', '2TM7', '2TM8', '2TM9', '2TM10',
                    '2TM11', '2TM12', '2TM13', '2TM14', '2TM15', '2TM16', '2TM17', '2TM18', '2TM19', '2TM20',
                    '4CM1', '4CM2', '6CM1', '6CM2',
                    '4MM1', '4MM2', '4MM3', '4MM4', '6MM1', '6MM2', '6MM3', '6MM4',
                    '4IM1', '6IM1', '4PM1', '6PM1',
                    '4EM1', '4EM2', '4EM3', '6EM1', '6EM2', '6EM3',
                    '4LM1', '4LM2', '4LM3', '4LM4', '6LM1', '6LM2', '6LM3', '6LM4',
                    '4AM1', '4AM2', '6AM1', '6AM2',
                    'Pases_salida'
                ]
            else:
                print("❌ Semestre desconocido:", semestre)
                bases_datos = []
            
            # Validar que el grupo seleccionado esté en la lista del semestre
            if grupo_seleccionado in bases_datos:
                print(f"✅ El grupo '{grupo_seleccionado}' es válido para el semestre {semestre}")
            else:
                print(f"⚠️ El grupo '{grupo_seleccionado}' no está en la lista del semestre {semestre}")
        else:
            print("❌ No se encontró el valor del semestre.")
            bases_datos = []
    else:
        print("❌ No se encontró el grupo en la base de datos.")
        grupo_seleccionado = None

except Error as e:
    print(f"❌ Error al conectar a la base de datos 'Semestre': {e}")
    resultado_semestre = None
    resultado_grupo = None
    grupo_seleccionado = None
    semestre = 2

# Puedes imprimir o usar la lista
print("Bases de datos cargadas:", bases_datos)



# Crear instancia del verificador
verificador = QRHorarioVerificador(
    camera_index=0,  # Cambiar según tu cámara
    db_config=db_config,
    bases_datos=bases_datos
)


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
        return render_template('index.html', foto=None, boleta=None, inscrito=None, acceso=False, salir=False)

    boleta = verificador.extraer_boleta_de_url(url)

    if not boleta:
        return render_template('index.html', foto=None, boleta=None, inscrito=None, error="No se pudo extraer la boleta del QR.", acceso=False, salir=False, operacion_mochila=False)

    # CONSULTAR INSCRITO DE FORMA INDEPENDIENTE
    base_datos_encontrada = verificador.buscar_tabla_horario(boleta)
    inscrito = None
    if base_datos_encontrada:
        inscrito = verificador.get_inscrito(boleta, base_datos_encontrada)
    
    estado = verificador.obtener_estado_acceso_salida(boleta, inscrito_valor=inscrito)
    acceso = estado.get('acceso', False)
    salir = estado.get('salir', False)
    operacion_mochila = verificador.operacion_mochila(boleta)
    bloquear_a = estado.get('bloquear_a', 0)
    bloquear_b = estado.get('bloquear_b', 0)
    
    print(f"Bloquear A: {bloquear_a}, Bloquear B: {bloquear_b}")
    print(f"Operación mochila para boleta {boleta}: {operacion_mochila}")
    print(f"Estado acceso: {acceso}, Estado salida: {salir}")
    print(f"Inscrito: {inscrito}")
    
    return render_template('index.html', boleta=boleta, inscrito=inscrito, acceso=acceso, salir=salir, operacion_mochila=operacion_mochila, bloquear_a=bloquear_a, bloquear_b=bloquear_b)


@app.route('/last_scan')
def last_scan():
    with verificador.lock:
        if verificador.scanned_codes:
            # Regresa la última URL escaneada válida
            return jsonify({"url": verificador.scanned_codes[-1]})
        else:
            return jsonify({"url": None})


@app.route('/video_feed')
def video_feed():
    """Stream de video"""
    return Response(verificador.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')



@app.route('/get_updates')
def get_updates():
    """API para obtener actualizaciones del log"""
    return jsonify(verificador.get_log_entries())

@app.route('/clear_logs')
def clear_logs():
    """API para limpiar logs"""
    with verificador.lock:
        verificador.last_log_entries.clear()
        verificador.scanned_codes.clear()
    return jsonify({"message": "Logs limpiados"})


@app.route('/stats')
def stats():
    """API para obtener estadísticas"""
    with verificador.lock:
        total_scans = len(verificador.last_log_entries)
        accepted = len([entry for entry in verificador.last_log_entries if entry['status'] == 'Aceptado'])
        denied = total_scans - accepted
        
        return jsonify({
            'total_scans': total_scans,
            'accepted': accepted,
            'denied': denied,
            'current_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'current_day': verificador.dias_semana.get(datetime.now().weekday(), 'N/A')
        })

@app.route('/main')
def main():
    """Página principal"""
    return render_template('main.html')


if __name__ == "__main__":
    try:
        print("🚀 Iniciando servidor Flask...")
        print("📱 Abrir en: http://localhost:5000")
        print(f"🎥 Usando cámara índice: 2")
        print(f"🗄️ Bases de datos configuradas: {len(bases_datos)}")
        print("📋 Funcionalidades disponibles:")
        print("   - Detección de QR en tiempo real")
        print("   - Verificación de horarios")
        print("   - Log de accesos")
        print("   - Sonidos de confirmación")
        print("   - Interface web")
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Cerrando aplicación...")
    finally:
        verificador.stop()



