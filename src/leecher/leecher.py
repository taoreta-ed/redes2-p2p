import socket
import os
import hashlib
import ast 

# Parámetros de configuración
TRACKER_PORT = 8000  # Puerto en el que escucha el tracker
PEER_PORT = 6000  # Puerto donde el leecher escuchará para recibir los archivos
DISCOVERY_PORT = 7000  # Puerto para el descubrimiento de peers

# Crear directorio para los chunks
CHUNK_DIR = "chunks"
os.makedirs(CHUNK_DIR, exist_ok=True)

#Funcion para calcular sha-256
def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

#Funcion para descargar el archivo de checksums desde un peer
def download_checksums(peer_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((peer_ip, PEER_PORT))
    s.sendall(b"checksums.txt")  # Pedimos el archivo de checksums
    path = os.path.join(CHUNK_DIR, "checksums.txt")
    with open(path, 'wb') as f:
        while data := s.recv(4096):
            f.write(data)
    s.close()

    # Cargar los checksums en diccionario
    checksums = {}
    with open(path, 'r') as f:
        for line in f:
            name, hashval = line.strip().split()
            checksums[name] = hashval
    return checksums

# Función para verificar un chunk descargado comparando su checksum
def verify_chunk(path, expected_checksum):
    actual = calculate_sha256(path)
    return actual == expected_checksum

# Función para descubrir peers a través del tracker
def discover_peers():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", TRACKER_PORT))  # Conectar al tracker
    s.sendall(b"DISCOVER")  # Solicitar lista de peers disponibles
    data = s.recv(1024).decode()  # Recibir la lista de peers
    peers = ast.literal_eval(data)  # Convierte el string a lista real
    print(f"Peers encontrados: {peers}")
    s.close()
    return peers

# Función para descargar un chunk de otro peer (seeder)
def download_chunk(peer_ip, chunk_name, expected_checksum):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((peer_ip, PEER_PORT))
    s.sendall(chunk_name.encode())
    path = os.path.join(CHUNK_DIR, chunk_name)
    with open(path, 'wb') as f:
        while data := s.recv(4096):
            f.write(data)
    print(f"Descargado {chunk_name} desde {peer_ip}")
    s.close()

    if verify_chunk(path, expected_checksum):
        print(f"Chunk {chunk_name} verificado correctamente.")
    else:
        print(f"Chunk {chunk_name} está corrupto. Intenta descargar de nuevo.")
        os.remove(path)  # Borra el archivo corrupto

# Función para reconstruir el archivo descargado
def reconstruct_file():
    with open("received_video.mp4", 'wb') as f:
        for chunk_name in os.listdir(CHUNK_DIR):
            with open(os.path.join(CHUNK_DIR, chunk_name), 'rb') as chunk:
                f.write(chunk.read())  # Escribir cada chunk en el archivo final

# Función para conectar al tracker y obtener la lista de chunks disponibles por peer
def get_peer_chunks(peer_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((peer_ip, TRACKER_PORT))  # Conexión al tracker o al Seeder para obtener los chunks
    s.sendall(f"GET_CHUNKS {peer_ip}".encode())  # Solicitar los chunks disponibles para ese peer
    chunk_list = s.recv(1024).decode()
    chunks = chunk_list.split(",")  # Convertir la respuesta en una lista de chunks disponibles
    s.close()
    return chunks

# Función principal del Leecher
def start_leecher():
    peers = discover_peers()

    for peer_ip in peers:
        download_checksums(peer_ip)  # Obtenemos el archivo de checksums y sus hashes

        #lee los archivos linea por linea y guarda los datos en un diccionario
        checksums = {}
        with open(os.path.join(CHUNK_DIR, "checksums.txt"), 'r') as f:
            for line in f:
                name, hashval = line.strip().split()
                checksums[name] = hashval

        # Obtenemos los nombres de los chunks a descargar
        chunks = checksums.keys()

        #para cada chunk verifica que ya lo tiene para no volverlo a descargar, verifica que su hash sea correcto
        for chunk_name in chunks:
            if not os.path.exists(os.path.join(CHUNK_DIR, chunk_name)):
                download_chunk(peer_ip, chunk_name, checksums[chunk_name])

    # Una vez descargados todos los chunks, reconstruir el archivo completo
    reconstruct_file()
    print("Archivo reconstruido exitosamente.")

if __name__ == "__main__":
    start_leecher()  # Inicia el leecher
