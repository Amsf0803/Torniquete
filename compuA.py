import asyncio
import evdev
from evdev import ecodes
import socket
import json
import os
import time

# --- RUTAS FÍSICAS ---
# Asegúrate de que estas sean las correctas que obtuviste antes
RUTA_FISICA_IZQ = '/dev/input/by-path/pci-0000:00:1a.0-usbv2-0:1.1:1.1-event-kbd'
RUTA_FISICA_DER = '/dev/input/by-path/pci-0000:00:1a.0-usbv2-0:1.3:1.1-event-kbd'

HOST_DESTINO = '201.66.195.124' 
PUERTO_DESTINO = 65432
TIEMPO_COOLDOWN = 3.0 

# --- MAPA DE TECLAS AVANZADO (NORMAL vs SHIFT) ---
# Esto soluciona que falte el "?" o salgan caracteres raros

# Teclas cuando NO presionas Shift
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

# Teclas cuando SÍ presionas Shift (Vital para el URL del IPN)
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
    ecodes.KEY_MINUS: '_',   # <--- Importante
    ecodes.KEY_EQUAL: '+', 
    ecodes.KEY_SLASH: '?',   # <--- AQUÍ ESTÁ EL PROBLEMA DEL '?'
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
        # Imprimimos solo los últimos caracteres para verificar integridad
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
            
            buffer = [] # Usamos lista que es más rápido que concatenar strings
            shift_presionado = False 
            
            async for event in dispositivo.async_read_loop():
                # 1. COOLDOWN
                if time.time() - ultimo_escaneo < TIEMPO_COOLDOWN:
                    buffer = []
                    continue

                if event.type == ecodes.EV_KEY:
                    # Gestionar estado del SHIFT (Izquierdo o Derecho)
                    if event.code in [ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT]:
                        shift_presionado = (event.value == 1 or event.value == 2) # 1=Press, 2=Hold
                        continue

                    if event.value == 1: # Solo al presionar tecla
                        key_code = event.code
                        
                        if key_code == ecodes.KEY_ENTER:
                            # Al dar ENTER, procesamos todo el paquete
                            texto_final = "".join(buffer)
                            
                            if len(texto_final) > 10: # Filtro de ruido
                                print(f"🚀 {nombre_lado} ESCANEADO COMPLETO!")
                                
                                payload = {
                                    "lado_izquierdo": es_izquierdo,
                                    "lado_derecho": not es_izquierdo,
                                    "texto": texto_final
                                }
                                
                                # Enviar en hilo aparte (NO BLOQUEANTE)
                                loop = asyncio.get_running_loop()
                                loop.run_in_executor(None, enviar_datos_sync, payload)
                                
                                ultimo_escaneo = time.time()
                                buffer = []
                            else:
                                buffer = [] # Enter vacío limpia
                        else:
                            # 2. LOGICA DE MAPEO (VELOCIDAD PURA)
                            # No hay prints aquí, solo guardado en memoria
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
    print("--- LECTOR DE ALTA VELOCIDAD (BUFFER FIX) ---")
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