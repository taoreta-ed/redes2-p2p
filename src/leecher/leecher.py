import socket
import threading
import time
import os
import hashlib

# Parámetros de configuración
PEER_PORT = 6000  # Puerto en el que escucha el servidor
DISCOVERY_PORT = 7000  # Puerto para el descubrimiento de peers
CHUNK_SIZE = 10 * 1024 * 1024  # Tamaño de cada chunk (10MB)
CHUNK_DIR = "chunks"  # Directorio donde se almacenarán los chunks
OUTPUT_FILE = "5GB_file.bin"  # Archivo final donde se ensamblarán los chunks
TRACKER_IP = "127.0.0.1"  # IP del tracker
TRACKER_PORT = 8000  # Puerto del tracker para registrar el peer

# Crear directorio para los chunks
os.makedirs(CHUNK_DIR, exist_ok=True)

# Función para calcular el hash de un archivo
def calculate_hash(filepath, hash_type='sha256'):
    """Calcula el hash del archivo usando el tipo especificado (MD5, SHA1, SHA256)."""
    hash_func = hashlib.new(hash_type)
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            hash_func.update(chunk)
    return hash_func.hexdigest()

# Función para manejar las conexiones de los clientes (servidor)
def handle_client(conn):
    part_name = conn.recv(1024).decode()  # Recibe el nombre del chunk solicitado
    path = os.path.join(CHUNK_DIR, part_name)
    
    # Envía el chunk al cliente si existe
    if os.path.exists(path):
        with open(path, 'rb') as f:
            while data := f.read(4096):
                conn.sendall(data)  # Envía el chunk al cliente
    conn.close()

# Función del servidor: escucha y acepta conexiones (para recibir)
def peer_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", PEER_PORT))  # Escucha en el puerto PEER_PORT
    s.listen(10)
    print(f"Servidor TCP escuchando en el puerto {PEER_PORT}")
    
    while True:
        conn, addr = s.accept()
        print(f"Conexión establecida con {addr}")
        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()  # Maneja la conexión en un hilo separado

# Función para recibir un chunk de otro peer (cliente) y agregarlo al archivo final
def receive_chunk(peer_ip, chunk_name, output_filepath):
    path = os.path.join(CHUNK_DIR, chunk_name)
    
    # Verifica si el chunk ya está descargado, si no, lo descarga
    if os.path.exists(path):
        return

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer_ip, PEER_PORT))  # Se conecta al peer en el puerto especificado
        s.sendall(chunk_name.encode())  # Envía el nombre del chunk que desea descargar

        # Guardar el chunk descargado
        with open(path, 'wb') as f:
            while data := s.recv(4096):  # Recibe los datos
                f.write(data)
        print(f"Descargado {chunk_name} desde {peer_ip}")
        s.close()
    except Exception as e:
        print(f"Error al descargar {chunk_name} de {peer_ip}: {e}")

    # Ahora agregar el chunk al archivo final
    with open(output_filepath, 'ab') as final_file:
        with open(path, 'rb') as chunk_file:
            final_file.write(chunk_file.read())  # Escribe el chunk en el archivo final

    # Eliminar el chunk temporal después de agregarlo al archivo final
    os.remove(path)

# Función para descubrir otros peers en la red local usando UDP
def discover_peers():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Habilitar broadcast
    s.settimeout(3)  # Tiempo de espera para respuesta

    # Enviar un mensaje de descubrimiento de peer en la red local
    s.sendto(b"DISCOVER", ("<broadcast>", DISCOVERY_PORT))
    
    peers = set()  # Conjunto de peers encontrados

    try:
        while True:
            data, addr = s.recvfrom(1024)  # Espera respuesta de peers
            if data == b"PEER_ACK":  # Respuesta de un peer
                peers.add(addr[0])  # Guardar la IP del peer que respondió
    except socket.timeout:
        pass  # Si no se reciben respuestas en el tiempo establecido

    return list(peers)

# Función para responder a los mensajes de descubrimiento
def respond_discovery():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", DISCOVERY_PORT))  # Escuchar en el puerto de descubrimiento

    while True:
        data, addr = s.recvfrom(1024)
        if data == b"DISCOVER":  # Si se recibe un mensaje de descubrimiento
            print(f"[DISCOVERY] Peer {addr[0]} encontrado")
            s.sendto(b"PEER_ACK", addr)  # Responder al peer con un ACK

# Función para ejecutar el Leecher
def start_leecher():
    # Iniciar el servidor que estará escuchando
    threading.Thread(target=peer_server, daemon=True).start()

    # Iniciar el servidor de descubrimiento en un hilo separado
    threading.Thread(target=respond_discovery, daemon=True).start()

    # Esperar a que el servidor esté listo
    time.sleep(1)

    # Búsqueda de peers
    peers = []
    print("Buscando peers en la red local...")

    while not peers:
        peers = discover_peers()
        if not peers:
            print("No se encontraron peers, esperando...")
            time.sleep(5)

    print(f"Peers encontrados: {peers}")

    # Descargar los chunks que faltan desde otros peers
    for peer_ip in peers:
        for chunk_name in range(0, 100):  # Cambia el rango si es necesario
            chunk_name = f"part_{chunk_name}"
            receive_chunk(peer_ip, chunk_name, OUTPUT_FILE)

    print("Proceso de descarga y distribución de chunks completado.")

if __name__ == "__main__":
    start_leecher()  # Inicia el Leecher para recibir los archivos
