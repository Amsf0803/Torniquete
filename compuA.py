import asyncio
import evdev
from evdev import ecodes
import socket
import json
import os


RUTA_FISICA_IZQ = '/dev/input/by-path/pci-0000:06:00.4-usbv2-0:1:1.1-event-kbd'
RUTA_FISICA_DER = '/dev/input/by-path/pci-0000:07:00.4-usbv2-0:1:1.1-event-kbd'

# Configuración de Red - Cambiar según corresponda
HOST_DESTINO = '192.168.1.50' 
PUERTO_DESTINO = 65432

# Mapa de teclas q ps el escaner puede llegar a enviar
key_map = {
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
    ecodes.KEY_DOT: '.', ecodes.KEY_SEMICOLON: ':',ecodes.KEY_ENTER: 'ENTER'
}


def enviar_datos(payload):
    try:
        # Timeout corto para no bloquear si la otra PC está apagada
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2) 
        s.connect((HOST_DESTINO, PUERTO_DESTINO))
        mensaje = json.dumps(payload)
        s.sendall(mensaje.encode('utf-8'))
        s.close()
        print(f"✅ Enviado: {mensaje}")
    except Exception as e:
        print(f"⚠️ Error enviando a {HOST_DESTINO}: {e}")

async def leer_escaner(ruta_by_path, es_izquierdo):
    """
    Intenta conectarse al dispositivo por su ruta física.
    Si se desconecta, reintenta automáticamente.
    """
    nombre_lado = "IZQUIERDA" if es_izquierdo else "DERECHA"
    
    while True:
        try:
            # evdev resuelve automáticamente el link simbólico by-path -> eventX
            dispositivo = evdev.InputDevice(ruta_by_path)
            dispositivo.grab() # Opcional: toma control exclusivo
            print(f"🟢 {nombre_lado} CONECTADO: {dispositivo.name}")
            
            buffer = ""
            
            # Bucle de lectura de eventos
            async for event in dispositivo.async_read_loop():
                if event.type == ecodes.EV_KEY and event.value == 1:
                    key_code = event.code
                    char = key_map.get(key_code, '')
                    
                    if char == 'ENTER':
                        if buffer:
                            payload = {
                                "lado_izquierdo": es_izquierdo,
                                "lado_derecho": not es_izquierdo,
                                "texto": buffer
                            }
                            print(f"Escaneado en {nombre_lado}: {buffer}")
                            enviar_datos(payload)
                            buffer = ""
                    else:
                        # Si es un caracter válido, lo agregamos
                        if len(str(char)) == 1: 
                            buffer += char
                            
        except FileNotFoundError:
            print(f"Waiting... Escáner {nombre_lado} no detectado en el puerto USB.")
            await asyncio.sleep(3) # Esperar 3 seg antes de revisar si ya lo conectaron
        except OSError:
            print(f"🔴 Escáner {nombre_lado} desconectado. Reintentando...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error inesperado en {nombre_lado}: {e}")
            await asyncio.sleep(2)

async def main():
    print("--- INICIANDO SISTEMA DE ESCANEO DUAL (BY-PATH) ---")
    # Verificamos que las rutas existan antes de empezar para avisar al usuario
    if not os.path.exists(RUTA_FISICA_IZQ):
        print(f"⚠️ AVISO: No detecto nada en el puerto IZQUIERDO: {RUTA_FISICA_IZQ}")
    if not os.path.exists(RUTA_FISICA_DER):
        print(f"⚠️ AVISO: No detecto nada en el puerto DERECHO: {RUTA_FISICA_DER}")

    await asyncio.gather(
        leer_escaner(RUTA_FISICA_IZQ, True),
        leer_escaner(RUTA_FISICA_DER, False)
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApagando sistema...")