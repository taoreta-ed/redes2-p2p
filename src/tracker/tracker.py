import socket
import threading
import time
import os

# Parámetros de configuración
TRACKER_PORT = 8000  # Puerto en el que escucha el tracker
DISCOVERY_PORT = 7000  # Puerto para el descubrimiento de peers
peers = {}  # Diccionario para almacenar la lista de peers activos y sus archivos

# Función para manejar las conexiones de los clientes (peers)
def handle_client(conn):
    try:
        data = conn.recv(1024).decode()  # Recibe el tipo de solicitud (descubrimiento o lista de archivos)
        print(f"Solicitud recibida: {data}")
        
        if data == "DISCOVER":
            # Enviar lista de peers disponibles
            available_peers = list(peers.keys())
            conn.sendall(str(available_peers).encode())
            print(f"Enviando lista de peers: {available_peers}")
        
        elif data.startswith("REGISTER"):
            # Registro de un nuevo peer
            peer_info = data.split()[1]  # Peer formato: "IP:PORT"
            file_list = data.split()[2:]  # Archivos que ofrece este peer
            peers[peer_info] = file_list
            print(f"Nuevo peer registrado: {peer_info} con archivos: {file_list}")
            conn.sendall(b"Peer registrado correctamente.")
        
        else:
            conn.sendall(b"Comando no reconocido.")
    
    except Exception as e:
        print(f"Error al manejar la solicitud del cliente: {e}")
        conn.sendall(b"Error en la solicitud.")
    
    finally:
        conn.close()

# Función para escuchar y aceptar conexiones entrantes (trackear peers)
def tracker_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", TRACKER_PORT))  # Escucha en el puerto TRACKER_PORT
    s.listen(10)
    print(f"Tracker escuchando en el puerto {TRACKER_PORT}")
    
    while True:
        conn, addr = s.accept()
        print(f"Conexión establecida con {addr}")
        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

# Función para descubrir peers a través del tracker (utilizando UDP)
def discover_peers():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Habilitar broadcast
    s.settimeout(3)  # Tiempo de espera para respuesta

    # Enviar un mensaje de descubrimiento de peer en la red local
    s.sendto(b"DISCOVER", ("<broadcast>", DISCOVERY_PORT))  # Enviar mensaje de broadcast UDP
    
    peers = set()  # Conjunto de peers encontrados

    try:
        while True:
            data, addr = s.recvfrom(1024)  # Espera respuesta de peers
            if data == b"PEER_ACK":  # Respuesta de un peer
                peers.add(addr[0])  # Guardar la IP del peer que respondió
    except socket.timeout:
        pass  # Si no se reciben respuestas en el tiempo establecido

    return list(peers)

# Función para registrar un peer en el tracker
def register_peer(peer_ip, file_list):
    # Conectarse al tracker para registrar el peer
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", TRACKER_PORT))  # Conexión al tracker
    registration_message = f"REGISTER {peer_ip} " + " ".join(file_list)
    s.sendall(registration_message.encode())
    response = s.recv(1024).decode()
    print(response)
    s.close()

# Función para ejecutar el tracker
def start_tracker():
    # Iniciar el servidor del tracker
    threading.Thread(target=tracker_server, daemon=True).start()

    # Espera indefinida para que el tracker siga funcionando
    while True:
        time.sleep(1)

if __name__ == "__main__":
    start_tracker()
