import socket
import threading
import time
import os
import random

# Parámetros de configuración
PEER_PORT = 6000 + random.randint(0, 1000)  # Puerto aleatorio para el Seeder
CHUNK_SIZE = 10 * 1024 * 1024  # Tamaño de cada chunk (10MB)
CHUNK_DIR = "chunks"  # Directorio donde se almacenarán los chunks
VIDEO_FILE = "5GB_file.bin"  # Archivo a dividir y compartir
TRACKER_IP = "127.0.0.1"  # IP del tracker
TRACKER_PORT = 8000  # Puerto del tracker para registrar el peer

# Crear directorio para los chunks
os.makedirs(CHUNK_DIR, exist_ok=True)

# Función para dividir el archivo en chunks
def split_file(filepath):
    parts = []
    with open(filepath, 'rb') as f:
        index = 0
        while chunk := f.read(CHUNK_SIZE):
            part_name = f"part_{index}"
            with open(os.path.join(CHUNK_DIR, part_name), 'wb') as p:
                p.write(chunk)
            parts.append(part_name)
            index += 1
    return parts

# Función para enviar un chunk a otro peer (cliente)
def send_chunk(peer_ip, part_name):
    path = os.path.join(CHUNK_DIR, part_name)
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer_ip, PEER_PORT))  # Se conecta al peer en el puerto PEER_PORT
        s.sendall(part_name.encode())  # Envía el nombre del chunk que desea enviar

        # Enviar el chunk
        with open(path, 'rb') as f:
            while data := f.read(4096):
                s.sendall(data)
        print(f"Enviado {part_name} a {peer_ip}")
        s.close()
    except Exception as e:
        print(f"Error al enviar {part_name} a {peer_ip}: {e}")

# Función para descubrir otros peers en la red local usando UDP
def discover_peers():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Habilitar broadcast
    s.settimeout(3)  # Tiempo de espera para respuesta

    # Enviar un mensaje de descubrimiento de peer en la red local
    s.sendto(b"DISCOVER", ("<broadcast>", 7000))
    
    peers = set()  # Conjunto de peers encontrados

    try:
        while True:
            data, addr = s.recvfrom(1024)  # Espera respuesta de peers
            if data == b"PEER_ACK":  # Respuesta de un peer
                peers.add(addr[0])  # Guardar la IP del peer que respondió
    except socket.timeout:
        pass  # Si no se reciben respuestas en el tiempo establecido

    return list(peers)

# Función para registrar el peer en el tracker
def register_peer():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TRACKER_IP, TRACKER_PORT))  # Conexión al tracker
    file_list = ["part_" + str(i) for i in range(len(split_file(VIDEO_FILE)))]  # Archivos disponibles
    register_message = f"REGISTER {TRACKER_IP} " + " ".join(file_list)
    s.sendall(register_message.encode())  # Enviar registro al tracker
    response = s.recv(1024).decode()  # Recibir respuesta
    print(response)
    s.close()

# Función para ejecutar el Seeder
def start_seeder():
    # Dividir el archivo en chunks
    parts = split_file(VIDEO_FILE)

    # Registrar el Seeder en el tracker
    register_peer()

    # Esperar a que el servidor esté listo para escuchar conexiones
    time.sleep(1)

    # Buscar peers para enviar los chunks
    peers = []
    print("Buscando peers en la red local...")

    while not peers:
        peers = discover_peers()
        if not peers:
            print("No se encontraron peers, esperando...")
            time.sleep(5)

    print(f"Peers encontrados: {peers}")

    # Enviar los chunks a los peers encontrados
    for peer_ip in peers:
        for part_name in parts:
            send_chunk(peer_ip, part_name)

    print("Proceso de envío de chunks completado.")

if __name__ == "__main__":
    start_seeder()  # Inicia el Seeder y empieza a compartir el archivo
