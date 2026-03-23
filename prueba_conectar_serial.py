import socket
import json

HOST = '0.0.0.0'  # Escucha en todas las interfaces de red
PORT = 65432      # El mismo puerto que en el emisor

def iniciar_servidor():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Servidor escuchando en el puerto {PORT}...")
        
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024)
                if not data:
                    continue
                
                try:
                    # Decodificamos el JSON recibido
                    mensaje = json.loads(data.decode('utf-8'))
                    
                    # --- AQUÍ TU LÓGICA ---
                    url = mensaje.get('texto')
                    es_izq = mensaje.get('lado_izquierdo')
                    
                    origen = "IZQUIERDA" if es_izq else "DERECHA"
                    print(f"Recibido de {origen}: URL -> {url}")
                    
                    # Ejemplo de uso de la variable bool
                    if mensaje['lado_izquierdo']:
                        print(">> Procesando como entrada prioritaria (Lado Izquierdo)")
                    
                except json.JSONDecodeError:
                    print("Error al decodificar JSON")

if __name__ == "__main__":
    iniciar_servidor()