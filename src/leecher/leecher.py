import socket
import os
import hashlib
import ast
import threading
import time

# Parámetros de configuración del Leecher
TRACKER_PORT = 8000         # Puerto del tracker al que el leecher se conecta
SEEDER_PORT = 6000          # Puerto donde el seeder principal escucha para enviar archivos
LEECHER_SERVER_PORT = 6001  # Puerto donde este leecher escuchará para servir chunks (mini-seeder)

# La dirección IP del tracker y, por extensión, la IP de la máquina actual
# que el leecher usará para registrarse y conectarse a otros peers.
TARGET_IP = "127.0.0.1"

# Directorio donde se almacenarán los chunks descargados.
CHUNK_DIR = "chunks_leecher"
os.makedirs(CHUNK_DIR, exist_ok=True) # Asegura que el directorio exista

# Variable global para almacenar los checksums una vez descargados del seeder inicial.
DOWNLOADED_CHECKSUMS = {}
ORIGINAL_FILENAME = None  # Para almacenar el nombre original del archivo

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

# ******* CORRECCIÓN CLAVE AQUÍ *******
# Función para descargar el archivo `checksums.txt` desde el SEEDER principal.
# Ahora toma el puerto del seeder como argumento.
def download_checksums_from_seeder(seeder_ip, seeder_port):
    global ORIGINAL_FILENAME
    print(f"Intentando descargar checksums.txt desde {seeder_ip}:{seeder_port}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((seeder_ip, seeder_port)) # Conecta al seeder usando su puerto CORRECTO
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
                parts = line.strip().split()
                if parts[0] == "ORIGINAL_FILENAME" and len(parts) > 1:
                    # Extraer el nombre original del archivo
                    ORIGINAL_FILENAME = parts[1]
                    print(f"Nombre original del archivo: {ORIGINAL_FILENAME}")
                else:
                    # Los checksums normales tienen formato "nombre_chunk hash_checksum"
                    if len(parts) == 2:
                        name, hashval = parts
                        checksums[name] = hashval
        
        # Asigna los checksums leídos a la variable global.
        global DOWNLOADED_CHECKSUMS
        DOWNLOADED_CHECKSUMS = checksums
        return checksums
    except Exception as e:
        print(f"Error al descargar o procesar checksums.txt desde {seeder_ip}:{seeder_port}: {e}")
        return {} # Retorna un diccionario vacío en caso de error
    finally:
        s.close() # Asegura que el socket se cierre.

# Función para verificar un chunk descargado comparando su checksum calculado
# con el checksum esperado (obtenido del archivo checksums.txt).
def verify_chunk(path, expected_checksum):
    actual = calculate_sha256(path)
    return actual == expected_checksum

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
def download_chunk(peer_ip, peer_port, chunk_name, expected_checksum):
    print(f"Descargando {chunk_name} desde {peer_ip}:{peer_port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chunk_path = os.path.join(CHUNK_DIR, chunk_name)
    try:
        s.connect((peer_ip, peer_port)) # Conecta al peer que tiene el chunk.
        s.sendall(chunk_name.encode())  # Solicita el chunk por su nombre.
        
        with open(chunk_path, 'wb') as f:
            while True:
                data = s.recv(4096) # Recibe datos en bloques de 4KB.
                if not data:
                    break # Fin de la descarga.
                f.write(data) # Escribe los datos en el archivo.
        
        print(f"Descargado {chunk_name} desde {peer_ip}:{peer_port}")

        # Después de la descarga, verifica la integridad del chunk.
        if verify_chunk(chunk_path, expected_checksum):
            print(f"Chunk {chunk_name} verificado correctamente.")
        else:
            print(f"Chunk {chunk_name} está corrupto. Eliminando y reintentando si es posible.")
            os.remove(chunk_path) # Borra el archivo corrupto.
    except Exception as e:
        print(f"Error al descargar o verificar {chunk_name} desde {peer_ip}:{peer_port}: {e}")
        # Si el archivo se creó pero la descarga falló, intenta limpiar.
        if os.path.exists(chunk_path):
            os.remove(chunk_path)
    finally:
        s.close() # Asegura que el socket se cierre.

# Función para reconstruir el archivo completo a partir de los chunks descargados.
def reconstruct_file():
    # Crear directorio "RecursosCompartidos" si no existe
    shared_dir = os.path.join(os.getcwd(), "RecursosCompartidos")
    os.makedirs(shared_dir, exist_ok=True)
    
    # Usar el nombre original del archivo si está disponible, o un nombre por defecto
    base_filename = ORIGINAL_FILENAME if ORIGINAL_FILENAME else "received_file.mp4"
    
    # Comprobar si el archivo ya existe para evitar sobrescritura
    output_filename = base_filename
    counter = 1
    
    while os.path.exists(os.path.join(shared_dir, output_filename)):
        name, ext = os.path.splitext(base_filename)
        output_filename = f"{name}_{counter}{ext}"
        counter += 1
    
    output_path = os.path.join(shared_dir, output_filename)
    print(f"Reconstruyendo archivo en {output_path}...")
    
    # Obtiene una lista de todos los archivos de chunk en el directorio CHUNK_DIR.
    # Filtra por aquellos que comienzan con "part_" y se aseguran de que existan y sean válidos.
    chunk_files = [
        fname for fname in os.listdir(CHUNK_DIR)
        if fname.startswith("part_") and os.path.exists(os.path.join(CHUNK_DIR, fname)) and \
           fname in DOWNLOADED_CHECKSUMS and verify_chunk(os.path.join(CHUNK_DIR, fname), DOWNLOADED_CHECKSUMS[fname])
    ]

    # Ordena los chunks numéricamente (part_0, part_1, etc.)
    # La función lambda extrae el número del nombre del chunk para la ordenación.
    sorted_chunks = sorted(chunk_files, key=lambda x: int(x.split('_')[1]))
    
    # Calcular el tamaño total para mostrar progreso
    total_size = sum(os.path.getsize(os.path.join(CHUNK_DIR, chunk)) for chunk in sorted_chunks)
    print(f"Reconstruyendo archivo de {total_size/(1024*1024*1024):.2f} GB")
    
    reconstruction_successful = False
    try:
        # Usar un buffer grande para mejorar el rendimiento
        BUFFER_SIZE = 4 * 1024 * 1024  # 4MB buffer
        bytes_written = 0
        start_time = time.time()
        
        with open(output_path, 'wb') as f:
            for chunk_name in sorted_chunks:
                chunk_full_path = os.path.join(CHUNK_DIR, chunk_name)
                try:
                    chunk_size = os.path.getsize(chunk_full_path)
                    with open(chunk_full_path, 'rb') as chunk:
                        # Leer y escribir en bloques grandes
                        while data := chunk.read(BUFFER_SIZE):
                            f.write(data)
                            bytes_written += len(data)
                            
                    # Mostrar progreso cada 100MB
                    if bytes_written % (100 * 1024 * 1024) < chunk_size:
                        elapsed = time.time() - start_time
                        percent = (bytes_written / total_size) * 100
                        speed = bytes_written / (1024 * 1024 * elapsed) if elapsed > 0 else 0
                        remaining = (total_size - bytes_written) / (bytes_written / elapsed) if bytes_written > 0 and elapsed > 0 else 0
                        print(f"Progreso: {bytes_written/(1024*1024*1024):.2f}GB/{total_size/(1024*1024*1024):.2f}GB ({percent:.1f}%) - {speed:.2f}MB/s - ETA: {remaining/60:.1f}min")
                        
                except Exception as e:
                    print(f"Error al leer el chunk {chunk_name} durante la reconstrucción: {e}")
        
        end_time = time.time()
        total_elapsed = end_time - start_time
        final_speed = total_size / (1024 * 1024 * total_elapsed) if total_elapsed > 0 else 0
        print(f"Archivo reconstruido en {total_elapsed:.1f} segundos ({final_speed:.2f}MB/s)")
        
        # Intentar establecer permisos de lectura/escritura para todos los usuarios
        try:
            # En sistemas Windows, esto hace el archivo más accesible
            import stat
            os.chmod(output_path, stat.S_IREAD | stat.S_IWRITE | 0o666)
        except Exception as e:
            print(f"Advertencia al establecer permisos: {e}")
            
        print(f"Archivo reconstruido exitosamente como {output_filename} en la carpeta RecursosCompartidos.")
        print(f"Tamaño final: {os.path.getsize(output_path)/(1024*1024*1024):.2f} GB")
        reconstruction_successful = True
    except Exception as e:
        print(f"Error al crear el archivo reconstruido: {e}")
        
    return reconstruction_successful

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
# Escucha en su propio puerto (`LEECHER_SERVER_PORT = 6001`) para servir chunks a otros.
def leecher_peer_server(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("", port))
        s.listen(5)
        print(f"Mini-seeder del leecher activo en el puerto {port}")

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
def register_as_seeder(peer_ip, port, chunks):
    print(f"Registrando como mini-seeder en el tracker {TARGET_IP}:{TRACKER_PORT} con {len(chunks)} chunks...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((TARGET_IP, TRACKER_PORT)) # Conecta al tracker.
        # Construye el mensaje de registro: "REGISTER IP:PUERTO chunk1 chunk2 ..."
        message = f"REGISTER {peer_ip}:{port} " + " ".join(chunks)
        s.sendall(message.encode()) # Envía el mensaje.
        response = s.recv(1024).decode() # Recibe la respuesta del tracker.
        print(f"Respuesta del tracker al registro: {response}")
    except Exception as e:
        print(f"Error al registrar como mini-seeder en el tracker: {e}")
    finally:
        s.close() # Cierra el socket.

# Función principal que inicia el proceso del Leecher.
def start_leecher():
    # Crear y anunciar el directorio de recursos compartidos
    shared_dir = os.path.join(os.getcwd(), "RecursosCompartidos")
    os.makedirs(shared_dir, exist_ok=True)
    print(f"Los archivos descargados se guardarán en: {os.path.abspath(shared_dir)}")
    
    # Utilizar puerto 0 para que el SO asigne un puerto disponible automáticamente
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))  # El 0 hace que el SO asigne un puerto libre
    dynamic_port = s.getsockname()[1]  # Obtiene el puerto asignado
    s.close()  # Cerramos este socket, será reabierto por leecher_peer_server()
    
    print(f"Usando puerto: {dynamic_port} para este leecher")
    
    # Usamos el puerto dinámico en vez de la constante global
    threading.Thread(target=lambda: leecher_peer_server(dynamic_port), daemon=True).start()
    
    # Dar un pequeño tiempo para que el mini-seeder inicie.
    time.sleep(1)

    # 2. Descubre los peers disponibles a través del tracker.
    peers = discover_peers()
    if not peers:
        print("No se encontraron peers en el tracker. No se puede iniciar la descarga.")
        return

    # 3. Descarga el archivo de checksums desde el seeder inicial.
    checksums = {}
    seeder_found = False
    for peer_info in peers:
        # El peer_info estará en formato "IP:PUERTO". Extraemos la IP y el puerto.
        peer_ip, peer_port_str = peer_info.split(':')
        peer_port = int(peer_port_str)
        
        # Identificamos el seeder principal por su IP y el puerto del seeder (6000).
        if peer_ip == TARGET_IP and peer_port == SEEDER_PORT: 
            checksums = download_checksums_from_seeder(peer_ip, peer_port) 
            if checksums:
                seeder_found = True
                break
    
    if not seeder_found or not checksums:
        print("No se pudo obtener checksums de ningún peer o el seeder principal no está activo.")
        return

    # 4. Descarga los chunks que faltan.
    chunks_to_download = []
    for chunk_name, expected_checksum in checksums.items():
        chunk_path = os.path.join(CHUNK_DIR, chunk_name)
        if not os.path.exists(chunk_path) or not verify_chunk(chunk_path, expected_checksum):
            chunks_to_download.append((chunk_name, expected_checksum))

    print(f"Chunks a descargar: {len(chunks_to_download)}")
    for chunk_name, expected_checksum in chunks_to_download:
        download_chunk(TARGET_IP, SEEDER_PORT, chunk_name, expected_checksum)

    # 5. Obtiene la lista de chunks que el leecher ha descargado y tiene completos y verificados.
    downloaded_chunks = [
        fname for fname in os.listdir(CHUNK_DIR)
        if fname.startswith("part_") and os.path.exists(os.path.join(CHUNK_DIR, fname)) and \
           fname in DOWNLOADED_CHECKSUMS and verify_chunk(os.path.join(CHUNK_DIR, fname), DOWNLOADED_CHECKSUMS[fname])
    ]
    print(f"Chunks descargados y verificados listos para compartir: {downloaded_chunks}")

    # 6. Registra al leecher (ahora un mini-seeder) en el tracker con los chunks que tiene.
    # Usa el puerto dinámico en lugar del puerto fijo
    register_as_seeder(TARGET_IP, dynamic_port, downloaded_chunks)

    # 7. Reconstruye el archivo completo a partir de los chunks descargados.
    reconstruct_file()

    print("Proceso de leecher completado.")


# Punto de entrada principal del script.
if __name__ == "__main__":
    start_leecher() # Inicia el leecher
