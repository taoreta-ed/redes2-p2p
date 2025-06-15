import socket
import os

# Parámetros de configuración
TRACKER_PORT = 8000  # Puerto en el que escucha el tracker
PEER_PORT = 6001  # Puerto donde el leecher escuchará para recibir los archivos
DISCOVERY_PORT = 7000  # Puerto para el descubrimiento de peers

# Crear directorio para los chunks
CHUNK_DIR = "chunks"
os.makedirs(CHUNK_DIR, exist_ok=True)

# Función para descubrir peers a través del tracker
def discover_peers():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", TRACKER_PORT))  # Conectar al tracker
    s.sendall(b"DISCOVER")  # Solicitar lista de peers disponibles
    data = s.recv(1024).decode()  # Recibir la lista de peers
    peers = data.split(",")  # Convertir la respuesta en una lista de peers
    print(f"Peers encontrados: {peers}")
    s.close()
    return peers

# Función para descargar un chunk de otro peer (seeder)
def download_chunk(peer_ip, chunk_name):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((peer_ip, PEER_PORT))  # Conectar al peer
    s.sendall(chunk_name.encode())  # Solicitar el chunk
    path = os.path.join(CHUNK_DIR, chunk_name)
    with open(path, 'wb') as f:
        while data := s.recv(4096):  # Recibir los datos
            f.write(data)
    print(f"Descargado {chunk_name} desde {peer_ip}")
    s.close()

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
    peers = discover_peers()  # Obtener los peers disponibles

    for peer_ip in peers:
        chunks = get_peer_chunks(peer_ip)  # Obtener la lista de chunks de cada peer
        
        # Descargar cada chunk desde el peer
        for chunk_name in chunks:
            download_chunk(peer_ip, chunk_name)  # Descargar el chunk

    # Una vez descargados todos los chunks, reconstruir el archivo completo
    reconstruct_file()
    print("El archivo ha sido reconstruido correctamente.")

if __name__ == "__main__":
    start_leecher()  # Inicia el leecher
