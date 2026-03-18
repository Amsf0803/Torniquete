import asyncio
import evdev
from evdev import ecodes
import socket
import json
import os
import time
import threading # <-- Importante para no trabar la lectura

# --- RUTAS FÍSICAS ---
RUTA_FISICA_IZQ = '/dev/input/by-path/pci-0000:00:1a.0-usbv2-0:1.1:1.1-event-kbd'
RUTA_FISICA_DER = '/dev/input/by-path/pci-0000:00:1a.0-usbv2-0:1.3:1.1-event-kbd'

HOST_DESTINO = '201.66.195.124' 
PUERTO_DESTINO = 65432
TIEMPO_COOLDOWN = 3.0 

# --- MAPA DE TECLAS AVANZADO (NORMAL vs SHIFT) ---
MAPA_NORMAL = {
    ecodes.KEY_A: 'a', ecodes.KEY_B: 'b', ecodes.KEY_C: 'c', ecodes.KEY_D: 'd',
    ecodes.KEY_E: 'e', ecodes.KEY_F: 'f', ecodes.KEY_G: 'g', ecodes.KEY_H: 'h',
    ecodes.KEY_I: 'i', ecodes.KEY_J: 'j', ecodes.KEY_K: 'k', ecodes.KEY_L: 'l',
    ecodes.KEY_M: 'm', ecodes.KEY_N: 'n', ecodes.KEY_O: 'o', ecodes.KEY_P: 'p',
    ecodes.KEY_Q: 'q', ecodes.KEY_R: 'r', ecodes.KEY_S: 's', ecodes.KEY_T: 't',
    ecodes.KEY_U: 'u', ecodes.KEY_V: 'v', ecodes.KEY_W: 'w', ecodes.KEY_X: 'x',
    ecodes.KEY_Y: 'y', ecodes.KEY_Z: 'z', ecodes.KEY_1: '1', ecodes.KEY_2: '2',
    ecodes.KEY_3: '3', ecodes.KEY_4: '4', ecodes.KEY_5: '5', ecodes.KEY_6: '6',
    ecodes.KEY_7: '7', ecodes.KEY_8: '8', ecodes.KEY_9: '9', ecodes.KEY_0: '0',
    ecodes.KEY_MINUS: '-', ecodes.KEY_EQUAL: '=', ecodes.KEY_SLASH: '/',
    ecodes.KEY_DOT: '.', ecodes.KEY_SEMICOLON: ';', ecodes.KEY_COMMA: ',',
    ecodes.KEY_SPACE: ' '
}

MAPA_SHIFT = {
    ecodes.KEY_A: 'A', ecodes.KEY_B: 'B', ecodes.KEY_C: 'C', ecodes.KEY_D: 'D',
    ecodes.KEY_E: 'E', ecodes.KEY_F: 'F', ecodes.KEY_G: 'G', ecodes.KEY_H: 'H',
    ecodes.KEY_I: 'I', ecodes.KEY_J: 'J', ecodes.KEY_K: 'K', ecodes.KEY_L: 'L',
    ecodes.KEY_M: 'M', ecodes.KEY_N: 'N', ecodes.KEY_O: 'O', ecodes.KEY_P: 'P',
    ecodes.KEY_Q: 'Q', ecodes.KEY_R: 'R', ecodes.KEY_S: 'S', ecodes.KEY_T: 'T',
    ecodes.KEY_U: 'U', ecodes.KEY_V: 'V', ecodes.KEY_W: 'W', ecodes.KEY_X: 'X',
    ecodes.KEY_Y: 'Y', ecodes.KEY_Z: 'Z', 
    ecodes.KEY_1: '!', ecodes.KEY_2: '@', ecodes.KEY_3: '#', ecodes.KEY_4: '$',
    ecodes.KEY_5: '%', ecodes.KEY_6: '^', ecodes.KEY_7: '&', ecodes.KEY_8: '*',
    ecodes.KEY_9: '(', ecodes.KEY_0: ')',
    ecodes.KEY_MINUS: '_',   
    ecodes.KEY_EQUAL: '+', 
    ecodes.KEY_SLASH: '?',   
    ecodes.KEY_DOT: '>', ecodes.KEY_SEMICOLON: ':', ecodes.KEY_COMMA: '<'
}

def enviar_datos_sync(payload):
    """Envío en segundo plano para no frenar la lectura"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2) 
        s.connect((HOST_DESTINO, PUERTO_DESTINO))
        mensaje = json.dumps(payload)
        s.sendall(mensaje.encode('utf-8'))
        s.close()
        texto = payload['texto']
        print(f"✅ Enviado: ...{texto[-15:]} (Longitud: {len(texto)})") 
    except Exception as e:
        print(f"⚠️ Error red: {e}")

async def leer_escaner(ruta_by_path, es_izquierdo):
    nombre_lado = "IZQ" if es_izquierdo else "DER"
    ultimo_escaneo = 0
    
    while True:
        try:
            dispositivo = evdev.InputDevice(ruta_by_path)
            dispositivo.grab()
            print(f"🟢 LISTO: {nombre_lado}")
            
            buffer = [] 
            shift_presionado = False 
            
            async for event in dispositivo.async_read_loop():
                # 1. COOLDOWN
                if time.time() - ultimo_escaneo < TIEMPO_COOLDOWN:
                    buffer = []
                    continue

                if event.type == ecodes.EV_KEY:
                    # Gestionar estado del SHIFT
                    if event.code in [ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT]:
                        shift_presionado = (event.value == 1 or event.value == 2) 
                        continue

                    if event.value == 1: # Solo al presionar tecla
                        key_code = event.code
                        
                        if key_code == ecodes.KEY_ENTER:
                            if len(buffer) > 0:
                                url_temp = "".join(buffer)
                                
                                # --- PARCHE: UNIR CÓDIGOS FRAGMENTADOS ---
                                if "saes.cecyt16" in url_temp.lower() and len(url_temp) < 100:
                                    print("⚠️ Fragmento SAES detectado, uniendo con la siguiente parte...")
                                    continue # Ignoramos este Enter y seguimos sumando al buffer
                                # -----------------------------------------
                                
                                url = url_temp
                                
                                # --- ARMADO Y ENVÍO DEL JSON ---
                                payload = {
                                    'escaner': nombre_lado,
                                    'texto': url
                                }
                                # Enviamos en un hilo para que el escáner siga leyendo rapidísimo
                                hilo_envio = threading.Thread(target=enviar_datos_sync, args=(payload,))
                                hilo_envio.daemon = True
                                hilo_envio.start()
                                # ---------------------------------------
                                
                                ultimo_escaneo = time.time()
                                buffer = []
                            else:
                                buffer = [] 
                        else:
                            # 2. LÓGICA DE MAPEO
                            if shift_presionado:
                                char = MAPA_SHIFT.get(key_code)
                            else:
                                char = MAPA_NORMAL.get(key_code)
                                
                            if char:
                                buffer.append(char)
                            
        except FileNotFoundError:
            await asyncio.sleep(5)
        except OSError:
            print(f"🔴 {nombre_lado} desconectado")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error {nombre_lado}: {e}")
            await asyncio.sleep(2)

async def main():
    print("--- LECTOR DE ALTA VELOCIDAD Y ENSAMBLAJE (DUAL SCANNER) ---")
    if not os.path.exists(RUTA_FISICA_IZQ): print("⚠️ Faltan rutas IZQ")
    if not os.path.exists(RUTA_FISICA_DER): print("⚠️ Faltan rutas DER")

    await asyncio.gather(
        leer_escaner(RUTA_FISICA_IZQ, True),
        leer_escaner(RUTA_FISICA_DER, False)
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass