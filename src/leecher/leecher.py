import socket
import os
import hashlib
import ast
import threading
import time

# Parámetros de configuración del Leecher
TRACKER_PORT = 8000         # Puerto del tracker al que el leecher se conecta
PEER_PORT = 6001            # Puerto donde el leecher escuchará para servir chunks (mini-seeder)
DISCOVERY_PORT = 7000       # Puerto para el descubrimiento de peers (UDP, aunque no completamente implementado en el flujo principal)

# La dirección IP del tracker y, por extensión, la IP de la máquina actual
# que el leecher usará para registrarse y conectarse a otros peers.
TARGET_IP = "8.12.0.166" 

# Directorio donde se almacenarán los chunks descargados.
CHUNK_DIR = "chunks_leecher" # Cambiado a 'chunks_leecher' para evitar colisiones con el seeder
os.makedirs(CHUNK_DIR, exist_ok=True) # Asegura que el directorio exista

# Variable para almacenar los checksums una vez descargados del seeder inicial
# Esto es esencial para la verificación de integridad.
DOWNLOADED_CHECKSUMS = {}

# Función para calcular el hash SHA-256 de un archivo dado.
# Utilizado para verificar la integridad de los chunks descargados.
def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    # Abre el archivo en modo binario para leer los bytes.
    with open(file_path, 'rb') as f:
        # Lee el archivo en bloques de 8192 bytes (8KB).
        while chunk := f.read(8192):
            sha256.update(chunk) # Actualiza el hash con cada bloque.
    return sha256.hexdigest() # Retorna el hash hexadecimal.

# Función para descargar el archivo `checksums.txt` de un peer (generalmente el seeder inicial).
def download_checksums(peer_ip):
    print(f"Intentando descargar checksums.txt desde {peer_ip}:{PEER_PORT}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((peer_ip, PEER_PORT)) # Conecta al seeder.
        s.sendall(b"checksums.txt")     # Solicita el archivo de checksums.
        
        path = os.path.join(CHUNK_DIR, "checksums.txt")
        # Abre el archivo localmente en modo binario de escritura para guardar los checksums.
        with open(path, 'wb') as f:
            while True:
                data = s.recv(4096) # Recibe datos en bloques de 4KB.
                if not data:
                    break # Si no hay más datos, la descarga ha terminado.
                f.write(data) # Escribe los datos en el archivo.
        print(f"Descargado checksums.txt a {path}")

        # Cargar los checksums en el diccionario global DOWNLOADED_CHECKSUMS
        checksums = {}
        with open(path, 'r') as f:
            for line in f:
                # Cada línea tiene el formato "nombre_chunk hash_checksum".
                name, hashval = line.strip().split()
                checksums[name] = hashval
        
        # Asigna los checksums leídos a la variable global.
        global DOWNLOADED_CHECKSUMS
        DOWNLOADED_CHECKSUMS = checksums
        return checksums
    except Exception as e:
        print(f"Error al descargar o procesar checksums.txt desde {peer_ip}: {e}")
        return {} # Retorna un diccionario vacío en caso de error
    finally:
        s.close() # Asegura que el socket se cierre.

# Función para verificar un chunk descargado comparando su checksum calculado
# con el checksum esperado (obtenido del archivo checksums.txt).
def verify_chunk(path, expected_checksum):
    if not os.path.exists(path):
        print(f"Error de verificación: El archivo {path} no existe.")
        return False
    actual_checksum = calculate_sha256(path)
    return actual_checksum == expected_checksum

# Función para descubrir peers contactando al tracker.
def discover_peers():
    print(f"Conectando al tracker en {TARGET_IP}:{TRACKER_PORT} para descubrir peers...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peers_list = []
    try:
        s.connect((TARGET_IP, TRACKER_PORT)) # Conecta al tracker.
        s.sendall(b"DISCOVER")             # Solicita la lista de peers disponibles.
        data = s.recv(1024).decode()       # Recibe la lista de peers como string.
        peers_list = ast.literal_eval(data) # Convierte el string a una lista de Python.
        print(f"Peers encontrados: {peers_list}")
    except Exception as e:
        print(f"Error al descubrir peers desde el tracker: {e}")
    finally:
        s.close() # Asegura que el socket se cierre.
    return peers_list

# Función para descargar un chunk específico de otro peer (seeder o mini-seeder).
def download_chunk(peer_ip, chunk_name, expected_checksum):
    print(f"Descargando {chunk_name} desde {peer_ip}:{PEER_PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chunk_path = os.path.join(CHUNK_DIR, chunk_name)
    try:
        s.connect((peer_ip, PEER_PORT)) # Conecta al peer que tiene el chunk.
        s.sendall(chunk_name.encode())  # Solicita el chunk por su nombre.
        
        with open(chunk_path, 'wb') as f:
            while True:
                data = s.recv(4096) # Recibe datos en bloques.
                if not data:
                    break # Fin de la descarga.
                f.write(data) # Escribe los datos en el archivo local.
        
        print(f"Descargado {chunk_name} desde {peer_ip}")

        # Después de la descarga, verifica la integridad del chunk.
        if verify_chunk(chunk_path, expected_checksum):
            print(f"Chunk {chunk_name} verificado correctamente.")
            # Si el chunk es válido, registramos este leecher como un seeder para este chunk.
            # Esto convierte al leecher en un mini-seeder.
            # No lo hacemos aquí directamente para no saturar el tracker, se hará al final de start_leecher.
        else:
            print(f"Chunk {chunk_name} está corrupto. Eliminando y reintentando si es posible.")
            os.remove(chunk_path) # Borra el archivo corrupto.
            # Aquí podrías añadir lógica para reintentar la descarga de otro peer o del mismo.
    except Exception as e:
        print(f"Error al descargar o verificar {chunk_name} desde {peer_ip}: {e}")
        # Si el archivo se creó pero la descarga falló, intenta limpiar.
        if os.path.exists(chunk_path):
            os.remove(chunk_path)
    finally:
        s.close() # Asegura que el socket se cierre.

# Función para reconstruir el archivo completo a partir de los chunks descargados.
def reconstruct_file(output_filename="received_frieren.jpeg"):
    output_path = os.path.join(os.getcwd(), output_filename) # Guarda en el directorio actual
    print(f"Reconstruyendo archivo en {output_path}...")
    with open(output_path, 'wb') as f:
        # Obtiene una lista de todos los archivos de chunk en el directorio CHUNK_DIR.
        chunk_files = [fname for fname in os.listdir(CHUNK_DIR) if fname.startswith("part_")]
        
        # Ordena los chunks numéricamente (part_0, part_1, etc.)
        # La función lambda extrae el número del nombre del chunk para la ordenación.
        for chunk_name in sorted(chunk_files, key=lambda x: int(x.split('_')[1])):
            chunk_full_path = os.path.join(CHUNK_DIR, chunk_name)
            try:
                with open(chunk_full_path, 'rb') as chunk:
                    f.write(chunk.read()) # Lee y escribe el contenido de cada chunk.
            except Exception as e:
                print(f"Error al leer el chunk {chunk_name} durante la reconstrucción: {e}")
                # Podrías decidir si abortar la reconstrucción o saltar este chunk.
                # Aquí, simplemente imprime el error y continúa.
    print("Archivo reconstruido exitosamente.")

# Esta función maneja las solicitudes entrantes de otros leechers/seeders
# que quieren descargar un chunk de este mini-seeder (el leecher actual).
def handle_incoming_chunk_request(conn, addr):
    try:
        chunk_name = conn.recv(1024).decode().strip() # Recibe el nombre del chunk solicitado.
        print(f"Solicitud de chunk '{chunk_name}' de {addr[0]}:{addr[1]}")
        
        path = os.path.join(CHUNK_DIR, chunk_name)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                while data := f.read(4096):
                    conn.sendall(data) # Envía el chunk en bloques.
            print(f"Enviado {chunk_name} a {addr[0]}:{addr[1]}")
        else:
            # Si el chunk solicitado no existe localmente, envía un mensaje de error.
            conn.sendall(b"ERROR: Chunk no encontrado.")
            print(f"Chunk '{chunk_name}' no encontrado para {addr[0]}:{addr[1]}")
    except Exception as e:
        print(f"Error al manejar la solicitud de chunk entrante de {addr[0]}:{addr[1]}: {e}")
    finally:
        conn.close() # Cierra la conexión después de enviar/manejar la solicitud.

# La función `peer_server` del leecher, que permite que actúe como un mini-seeder.
# Escucha en su propio puerto (`PEER_PORT = 6001`) para servir chunks a otros.
def peer_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("", PEER_PORT)) # Escucha en todas las interfaces de red en PEER_PORT.
        s.listen(5)             # Permite hasta 5 conexiones pendientes.
        print(f"Mini-seeder del leecher activo en el puerto {PEER_PORT}")

        while True:
            # Acepta nuevas conexiones entrantes.
            conn, addr = s.accept()
            # Inicia un nuevo hilo para manejar cada solicitud entrante, para no bloquear el servidor.
            threading.Thread(target=handle_incoming_chunk_request, args=(conn, addr,), daemon=True).start()
    except Exception as e:
        print(f"Error al iniciar el servidor mini-seeder del leecher: {e}")
    finally:
        s.close() # Cierra el socket del servidor si hay un error o al finalizar.

# Función para registrar al leecher como un mini-seeder en el tracker.
# Informa al tracker qué chunks tiene disponibles para compartir.
def register_as_seeder(peer_ip, chunks):
    print(f"Registrando como mini-seeder en el tracker {TARGET_IP}:{TRACKER_PORT} con {len(chunks)} chunks...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((TARGET_IP, TRACKER_PORT)) # Conecta al tracker.
        # Construye el mensaje de registro: "REGISTER IP:PUERTO chunk1 chunk2 ..."
        message = f"REGISTER {peer_ip}:{PEER_PORT} " + " ".join(chunks)
        s.sendall(message.encode()) # Envía el mensaje.
        response = s.recv(1024).decode() # Recibe la respuesta del tracker.
        print(f"Respuesta del tracker al registro: {response}")
    except Exception as e:
        print(f"Error al registrar como mini-seeder en el tracker: {e}")
    finally:
        s.close() # Cierra el socket.

# Función principal que inicia el proceso del Leecher.
def start_leecher():
    # 1. Inicia el servidor mini-seeder en un hilo paralelo.
    # Esto permite que el leecher descargue mientras simultáneamente comparte los chunks que ya tiene.
    threading.Thread(target=peer_server, daemon=True).start()
    
    # Dar un pequeño tiempo para que el mini-seeder inicie.
    time.sleep(1)

    # 2. Descubre los peers disponibles a través del tracker.
    peers = discover_peers()
    if not peers:
        print("No se encontraron peers en el tracker. No se puede iniciar la descarga.")
        return

    # 3. Descarga el archivo de checksums desde el seeder inicial (asumimos que es 8.12.0.166).
    # En un escenario más robusto, se buscaría un peer que ofrezca `checksums.txt`.
    checksums = {}
    seeder_found = False
    for peer_info in peers:
        # El peer_info estará en formato "IP:PUERTO". Extraemos la IP.
        peer_ip, _ = peer_info.split(':')
        if peer_ip == TARGET_IP: # Asumiendo que el seeder principal está en la misma IP objetivo.
            checksums = download_checksums(peer_ip)
            if checksums:
                seeder_found = True
                break
    
    if not seeder_found or not checksums:
        print("No se pudo obtener checksums de ningún peer o el seeder principal no está activo.")
        return

    # 4. Descarga los chunks que faltan.
    # Itera sobre los checksums para saber qué chunks se necesitan y cuáles son sus hashes esperados.
    chunks_to_download = []
    for chunk_name, expected_checksum in checksums.items():
        chunk_path = os.path.join(CHUNK_DIR, chunk_name)
        # Si el chunk no existe localmente o está corrupto, lo añade a la lista de descarga.
        if not os.path.exists(chunk_path) or not verify_chunk(chunk_path, expected_checksum):
            chunks_to_download.append((chunk_name, expected_checksum))

    # Podrías implementar una lógica para descargar de múltiples peers si están disponibles,
    # en lugar de siempre del mismo `TARGET_IP`.
    print(f"Chunks a descargar: {len(chunks_to_download)}")
    for chunk_name, expected_checksum in chunks_to_download:
        # Por simplicidad, siempre intenta descargar del `TARGET_IP` (seeder principal).
        # En un sistema P2P real, buscarías qué peer tiene este chunk.
        download_chunk(TARGET_IP, chunk_name, expected_checksum)

    # 5. Obtiene la lista de chunks que el leecher ha descargado y tiene completos.
    downloaded_chunks = [
        fname for fname in os.listdir(CHUNK_DIR)
        if fname.startswith("part_") and os.path.exists(os.path.join(CHUNK_DIR, fname)) and \
           fname in DOWNLOADED_CHECKSUMS and verify_chunk(os.path.join(CHUNK_DIR, fname), DOWNLOADED_CHECKSUMS[fname])
    ]
    print(f"Chunks descargados y verificados listos para compartir: {downloaded_chunks}")

    # 6. Registra al leecher (ahora un mini-seeder) en el tracker con los chunks que tiene.
    register_as_seeder(TARGET_IP, downloaded_chunks)

    # 7. Reconstruye el archivo completo a partir de los chunks descargados.
    reconstruct_file()

    print("Proceso de leecher completado.")


# Punto de entrada principal del script.
if __name__ == "__main__":
    start_leecher() # Inicia el leecher
