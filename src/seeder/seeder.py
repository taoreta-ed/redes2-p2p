#seeder.py
import socket
import os
import time

# Parámetros de configuración
TRACKER_PORT = 8000  # Puerto en el que escucha el tracker
PEER_PORT = 6000  # Puerto donde el seeder escuchará para enviar los archivos
DISCOVERY_PORT = 7000  # Puerto para el descubrimiento de peers
VIDEO_FILE = r'./src/test.jpg'  # El archivo que vamos a compartir

# Crear directorio para los chunks
CHUNK_DIR = "chunks"
os.makedirs(CHUNK_DIR, exist_ok=True)

# Función para dividir el archivo en chunks
def split_file(filepath):
    parts = []
    with open(filepath, 'rb') as f:
        index = 0
        while chunk := f.read(10 * 1024 * 1024):  # Tamaño de 10MB por chunk
            part_name = f"part_{index}"
            with open(os.path.join(CHUNK_DIR, part_name), 'wb') as p:
                p.write(chunk)
            parts.append(part_name)
            index += 1
    return parts

# Función para registrar el seeder en el tracker
def register_peer(peer_ip, file_list):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", TRACKER_PORT))  # Conectar al tracker
    registration_message = f"REGISTER {peer_ip} " + " ".join(file_list)
    s.sendall(registration_message.encode())  # Enviar el registro al tracker
    response = s.recv(1024).decode()
    print(response)
    s.close()

# Función para enviar un chunk al cliente
def handle_client(conn):
    part_name = conn.recv(1024).decode()  # Recibe el nombre del chunk solicitado
    path = os.path.join(CHUNK_DIR, part_name)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            while data := f.read(4096):
                conn.sendall(data)  # Envia el chunk al cliente
    conn.close()

# Función del servidor del seeder: escucha y acepta conexiones
def peer_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", PEER_PORT))  # Escucha en el puerto PEER_PORT
    s.listen(10)
    print(f"Seeder escuchando en el puerto {PEER_PORT}")
    
    while True:
        conn, addr = s.accept()
        print(f"Conexión establecida con {addr}")
        handle_client(conn)  # Manejar la conexión del cliente (enviar el chunk solicitado)

# Función principal del Seeder
def start_seeder():
    # Dividir el archivo en chunks
    parts = split_file(VIDEO_FILE)

    # Registrar el seeder en el tracker
    peer_ip = "localhost"  # Cambia esto a tu IP si estás usando una red diferente
    register_peer(peer_ip, parts)  # Registrar en el tracker

    # Iniciar el servidor del seeder
    peer_server()

if __name__ == "__main__":
    start_seeder()  # Inicia el seeder
