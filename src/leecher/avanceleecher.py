import socket
import os
import hashlib
import ast 
import threading
import shutil
from tqdm import tqdm

# Parámetros de configuración
TRACKER_PORT = 8000  # Puerto en el que escucha el tracker
PEER_PORT = 6001  # Puerto donde el leecher escuchará para recibir los archivos
CHUNCK_DIR = "chunks"
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
    s.connect(("8.12.0.166", TRACKER_PORT))  # Conectar al tracker
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
        chunk_files = [f for f in os.listdir(CHUNK_DIR) if f.startswith("part_")]
        for chunk_name in sorted(chunk_files, key=lambda x: int(x.split('_')[1])):
            with open(os.path.join(CHUNK_DIR, chunk_name), 'rb') as chunk:
                f.write(chunk.read())
    print("Archivo reconstruido exitosamente.")


# Función para conectar al tracker y obtener la lista de chunks disponibles por peer
def get_peer_chunks(peer_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((peer_ip, TRACKER_PORT))  # Conexión al tracker o al Seeder para obtener los chunks
    s.sendall(f"GET_CHUNKS {peer_ip}".encode())  # Solicitar los chunks disponibles para ese peer
    chunk_list = s.recv(1024).decode()
    chunks = chunk_list.split(",")  # Convertir la respuesta en una lista de chunks disponibles
    s.close()
    return chunks

# Mini seeder: otro peer se conecta y pide un chunk, esta funcion verifica que exista, si es asi, lo abre y lo envía por sockets al peer, de lo contrario, da un mensaje de error
def handle_client(conn):
    chunk_name = conn.recv(1024).decode()
    path = os.path.join(CHUNK_DIR, chunk_name)
    #verifica si el chunk existe
    if os.path.exists(path):
        with open(path, 'rb') as f:
            while data := f.read(4096):
                conn.sendall(data)
    else:
        conn.sendall(b"ERROR: Chunk no encontrado.")
    conn.close()

#Lanza un servidor TCP, el cual permite que se puedan compartir varios chuncks a la vez, incluso mientras esta descargando
def peer_server():
    # Crea un socket TCP para el mini-seeder
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Asigna el socket al puerto 6000
    s.bind(("", PEER_PORT))
    # Escucha conexiones entrantes
    s.listen(5)
    print(f"Mini-seeder activo en el puerto {PEER_PORT}")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()


# Función para registrar al leecher como mini-seeder en el tracker
def register_as_seeder(peer_ip, chunks):
    #se conecta al tracker 
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("8.12.0.166", TRACKER_PORT))
        message = f"REGISTER {peer_ip} " + " ".join(chunks)
        s.sendall(message.encode())
        response = s.recv(1024).decode()
        print(f"Registrado como mini-seeder en tracker: {response}")
    except Exception as e:
        print(f"Error al registrar como mini-seeder: {e}")
    finally:
        s.close()


# Función principal del Leecher
def start_leecher():
    shutil.rmtree(CHUNK_DIR, ignore_errors=True)
    os.makedirs(CHUNK_DIR, exist_ok=True)

    # Iniciar el servidor mini-seeder en un hilo paralelo
    threading.Thread(target=peer_server, daemon=True).start()

    peers = discover_peers()

    for peer_ip in peers:
        if peer_ip == "8.12.0.166":
            # Descarga archivo de checksums del Seeder
            checksums = download_checksums(peer_ip)
            break
    else:
        print("No se pudo obtener checksums de ningún peer.")
        return

   # Mostrar barra de progreso al descargar
    total_chunks = len(checksums)
    downloaded_chunks = 0
    downloaded_size = 0

    with tqdm(total=total_chunks, desc="Descargando", unit="chunk") as bar:
        for chunk_name, expected_checksum in checksums.items():
            path = os.path.join(CHUNK_DIR, chunk_name)

            already_existed = os.path.exists(path)

            if not already_existed:
                download_chunk(peer_ip, chunk_name, expected_checksum)

            if os.path.exists(path):
                chunk_size = os.path.getsize(path)
                downloaded_size += chunk_size
                mb_total = downloaded_size / (1024 * 1024)
                bar.set_postfix_str(f"{mb_total:.2f} MB descargados")

                if not already_existed:
                    bar.update(1)



    # Obtiene la lista de chunks descargados
    downloaded_chunks = [
        fname for fname in os.listdir(CHUNK_DIR)
        if fname.startswith("part_")
    ]

    # Registra al mini-seeder en el tracker
    register_as_seeder("8.12.0.166", downloaded_chunks)

    reconstruct_file()




if _name_ == "_main_":
    start_leecher()  # Inicia el leecher