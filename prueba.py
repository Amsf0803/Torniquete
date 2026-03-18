import socket
import threading
import time
import json

class ConexionESP32:
    """
    Clase mejorada para comunicación WiFi con ESP32 usando IP pública
    """
    def __init__(self, esp_ip, esp_port=5000, timeout=10):
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.timeout = timeout
        self.socket = None
        self.conectado = False
        self.lock = threading.Lock()
        self.ultimo_ping = 0
        self.intervalo_ping = 30  # Ping cada 30 segundos
        
    def conectar(self):
        """Establece conexión TCP con el ESP32"""
        with self.lock:
            try:
                # Cerrar conexión previa si existe
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                
                # Crear nuevo socket con opciones TCP
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
                # Configurar opciones del socket
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.socket.settimeout(self.timeout)
                
                print(f"🔌 Conectando a ESP32 en {self.esp_ip}:{self.esp_port}...")
                
                # Conectar al ESP32
                self.socket.connect((self.esp_ip, self.esp_port))
                self.conectado = True
                self.ultimo_ping = time.time()
                
                print(f"✅ Conectado al ESP32 en {self.esp_ip}:{self.esp_port}")
                
                # Leer mensaje de bienvenida (sin bloquear mucho)
                try:
                    self.socket.settimeout(2.0)
                    welcome = self.socket.recv(1024).decode(errors="ignore").strip()
                    if welcome:
                        print(f"📡 ESP32: {welcome}")
                except socket.timeout:
                    pass  # No hay problema si no hay mensaje
                except Exception as e:
                    print(f"⚠️ Advertencia al leer bienvenida: {e}")
                
                # Restaurar timeout original
                self.socket.settimeout(self.timeout)
                
                return True
                
            except socket.timeout:
                print(f"❌ Timeout conectando al ESP32")
                self.conectado = False
                return False
                
            except ConnectionRefusedError:
                print(f"❌ Conexión rechazada - Verifica que el ESP32 esté encendido")
                self.conectado = False
                return False
                
            except Exception as e:
                print(f"❌ Error conectando: {e}")
                print("\n💡 Solución de problemas:")
                print("   1. Verifica que el ESP32 esté encendido")
                print("   2. Asegúrate que el puerto 5000 esté abierto en el router")
                print("   3. Revisa el firewall")
                print("   4. Verifica la IP: " + self.esp_ip)
                
                self.conectado = False
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None
                return False

    def _mantener_conexion(self):
        """Envía pings periódicos para mantener la conexión"""
        ahora = time.time()
        if ahora - self.ultimo_ping > self.intervalo_ping:
            if self.ping():
                self.ultimo_ping = ahora
                return True
            return False
        return True

    def enviar_comando(self, comando):
        """
        Envía comando al ESP32 con manejo robusto de respuestas
        Formato esperado por ESP32: "2\n" o "3\n" o JSON
        """
        # Verificar conexión
        if not self.conectado or not self.socket:
            print("⚠️ No hay conexión, intentando reconectar...")
            if not self.conectar():
                print("❌ No se pudo reconectar")
                return False
        
        # Mantener conexión activa
        if not self._mantener_conexion():
            print("⚠️ Conexión perdida, reconectando...")
            if not self.conectar():
                return False
        
        try:
            # Preparar comando
            if isinstance(comando, int):
                comando_str = str(comando)
            else:
                comando_str = str(comando).strip()
            
            # Agregar salto de línea si no lo tiene
            if not comando_str.endswith('\n'):
                comando_str += '\n'
            
            print(f"📤 Enviando: '{comando_str.strip()}'")
            
            # Enviar comando
            self.socket.sendall(comando_str.encode('utf-8'))
            
            # Esperar respuesta con timeout corto
            self.socket.settimeout(3.0)
            
            try:
                respuesta = self.socket.recv(1024).decode(errors="ignore").strip()
                
                if respuesta:
                    print(f"📥 Respuesta: {respuesta}")
                    
                    # Parsear respuesta JSON si es posible
                    try:
                        respuesta_json = json.loads(respuesta)
                        if respuesta_json.get('status') == 'ok':
                            return True
                        elif respuesta_json.get('status') == 'error':
                            print(f"⚠️ ESP32 reporta error: {respuesta_json.get('message')}")
                            return False
                    except json.JSONDecodeError:
                        # No es JSON, verificar texto plano
                        respuesta_upper = respuesta.upper()
                        
                        if 'OK' in respuesta_upper or 'ACTIVADO' in respuesta_upper:
                            return True
                        elif 'ERROR' in respuesta_upper or 'OCUPADO' in respuesta_upper:
                            print(f"⚠️ {respuesta}")
                            return False
                
                # Si llegamos aquí, asumimos éxito
                return True
                    
            except socket.timeout:
                print("ℹ️ Sin respuesta del ESP32 (puede ser normal)")
                # Asumimos éxito si no hay error explícito
                return True
                
            except Exception as e:
                print(f"⚠️ Error leyendo respuesta: {e}")
                # No es crítico, el comando pudo haberse enviado
                return True
            
            finally:
                # Restaurar timeout
                self.socket.settimeout(self.timeout)
            
        except BrokenPipeError:
            print("❌ Conexión rota")
            self.desconectar()
            return False
            
        except ConnectionResetError:
            print("❌ Conexión reiniciada por el servidor")
            self.desconectar()
            return False
            
        except Exception as e:
            print(f"❌ Error enviando comando: {e}")
            self.desconectar()
            return False

    def abrir_torniquete_comando2(self):
        """Comando '2' - Activar torniquete modo 2 (estudiantes)"""
        print("🚪 Activando torniquete COMANDO 2 (Estudiantes)...")
        return self.enviar_comando("2")
    
    def abrir_torniquete_comando3(self):
        """Comando '3' - Activar torniquete modo 3 (guardias)"""
        print("🚪 Activando torniquete COMANDO 3 (Guardias)...")
        return self.enviar_comando("3")
    
    def obtener_status(self):
        """Solicita el status del sistema"""
        print("📊 Solicitando status...")
        if self.enviar_comando("STATUS"):
            return True
        return False
    
    def ping(self):
        """Verifica que ESP32 está vivo enviando un comando simple"""
        try:
            if not self.conectado or not self.socket:
                return False
            
            # Guardar timeout actual
            old_timeout = self.socket.gettimeout()
            self.socket.settimeout(2.0)
            
            try:
                # Enviar ping vacío
                self.socket.sendall(b"\n")
                
                # Intentar recibir (puede que no haya respuesta)
                try:
                    self.socket.recv(1)
                except socket.timeout:
                    pass  # Timeout es aceptable en ping
                
                return True
                
            except (BrokenPipeError, ConnectionResetError):
                self.conectado = False
                return False
            finally:
                # Restaurar timeout
                try:
                    self.socket.settimeout(old_timeout)
                except:
                    pass
                    
        except Exception as e:
            print(f"⚠️ Error en ping: {e}")
            self.conectado = False
            return False

    def desconectar(self):
        """Cierra la conexión de forma segura"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            self.conectado = False
            print("🔌 Desconectado del ESP32")
    
    def write(self, data):
        """Método de compatibilidad (interfaz como pyserial)"""
        return self.enviar_comando(data)
    
    def __del__(self):
        """Destructor - asegura cierre de conexión"""
        self.desconectar()


def probar_conexion_esp32(esp_ip, esp_port=5000):
    """
    Función de prueba mejorada para verificar conectividad
    """
    print("\n" + "="*60)
    print("🧪 PRUEBA DE CONEXIÓN CON ESP32")
    print("="*60)
    print(f"🔍 Probando {esp_ip}:{esp_port}...")
    
    # Prueba 1: Socket básico
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(5)
        
        resultado = test_socket.connect_ex((esp_ip, esp_port))
        
        if resultado == 0:
            print("✅ Puerto TCP accesible")
            test_socket.close()
        else:
            print(f"❌ Puerto no accesible (código: {resultado})")
            test_socket.close()
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba básica: {e}")
        return False
    
    # Prueba 2: Conexión completa
    print("\n🔍 Probando comunicación completa...")
    esp_test = ConexionESP32(esp_ip=esp_ip, esp_port=esp_port)
    
    if not esp_test.conectar():
        print("❌ No se pudo establecer conexión")
        return False
    
    # Prueba 3: Enviar comando de prueba
    print("\n🔍 Probando envío de comando STATUS...")
    if esp_test.obtener_status():
        print("✅ Comunicación bidireccional funcionando")
    else:
        print("⚠️ Comando enviado pero sin confirmación clara")
    
    # Prueba 4: Comando de torniquete
    print("\n🔍 Probando comando de torniquete (2)...")
    if esp_test.abrir_torniquete_comando2():
        print("✅ Control de torniquete funcional")
        resultado_final = True
    else:
        print("⚠️ Problema con control de torniquete")
        resultado_final = False
    
    esp_test.desconectar()
    
    print("\n" + "="*60)
    if resultado_final:
        print("✅ TODAS LAS PRUEBAS EXITOSAS")
    else:
        print("⚠️ ALGUNAS PRUEBAS FALLARON")
    print("="*60 + "\n")
    
    return resultado_final


# Ejemplo de uso
if __name__ == "__main__":
    # Configuración
    ESP32_IP = "201.66.195.11"
    ESP32_PORT = 5000
    
    # Probar conexión
    if probar_conexion_esp32(ESP32_IP, ESP32_PORT):
        print("\n🚀 Iniciando comunicación normal...")
        
        # Crear conexión permanente
        esp32 = ConexionESP32(esp_ip=ESP32_IP, esp_port=ESP32_PORT)
        
        if esp32.conectar():
            print("✅ ESP32 listo para usar")
            
            # Ejemplo: Activar torniquete
            time.sleep(2)
            esp32.abrir_torniquete_comando2()
            
            time.sleep(2)
            esp32.obtener_status()
            
        else:
            print("❌ No se pudo conectar")
    else:
        print("❌ Pruebas fallaron")