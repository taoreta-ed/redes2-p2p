import socket
import os
import time
import hashlib
import threading

# Parámetros de configuración del Seeder
TRACKER_PORT = 8000         # Puerto del tracker al que el seeder se conectará para registrarse
PEER_PORT = 6000            # Puerto donde el seeder escuchará conexiones de otros peers
DISCOVERY_PORT = 7000       # Puerto para el descubrimiento de peers (UDP, no usado directamente en el flujo TCP)

# La dirección IP que el seeder usará para registrarse en el tracker y para escuchar conexiones.
TARGET_IP = "8.12.0.166" 

# Ruta al archivo de video/imagen que se va a compartir.
# Es importante que esta ruta sea correcta y el archivo exista.
VIDEO_FILE = './src/seeder/frieren.jpeg' 
# VIDEO_FILE = r'D:\REDES-2\Proyecto\redes2-p2p\src\5GB_file.bin' # Ejemplo de archivo grande

# Directorio donde se almacenarán los chunks del archivo original.
CHUNK_DIR = "chunks_seeder" # Cambiado a 'chunks_seeder' para evitar colisiones con el leecher
os.makedirs(CHUNK_DIR, exist_ok=True) # Asegura que el directorio de chunks exista.

# Función para calcular el hash SHA-256 de un archivo dado.
# Es crucial para verificar la integridad de los chunks en el lado del leecher.
def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192): # Lee el archivo en bloques de 8KB.
            sha256.update(chunk)     # Actualiza el objeto hash con cada bloque.
    return sha256.hexdigest()        # Retorna el hash hexadecimal completo.

# Función para dividir el archivo original en chunks más pequeños.
# También calcula el checksum SHA-256 para cada chunk y los guarda.
def split_file(filepath):
    parts = []      # Lista para almacenar los nombres de los chunks creados.
    checksums = {}  # Diccionario para almacenar los checksums (nombre_chunk: hash).

    print(f"Dividiendo archivo {filepath} en chunks...")
    if not os.path.exists(filepath):
        print(f"Error: El archivo {filepath} no se encontró.")
        return []

    try:
        with open(filepath, 'rb') as f:
            index = 0
            # Lee el archivo en chunks de 10 MB (10 * 1024 * 1024 bytes).
            while chunk := f.read(20 * 1024 * 1024):
                part_name = f"part_{index}"
                part_path = os.path.join(CHUNK_DIR, part_name)
                
                # Guarda cada chunk en un nuevo archivo dentro del CHUNK_DIR.
                with open(part_path, 'wb') as p:
                    p.write(chunk)

                # Calcula el SHA-256 del chunk recién guardado.
                checksum = calculate_sha256(part_path)
                checksums[part_name] = checksum # Almacena el checksum.
                parts.append(part_name)         # Añade el nombre del chunk a la lista.
                index += 1
        print(f"Archivo dividido en {index} chunks.")

        # Guarda todos los checksums en un archivo `checksums.txt` en el CHUNK_DIR.
        # Este archivo será descargado por los leechers para verificar la integridad.
        checksums_filepath = os.path.join(CHUNK_DIR, "checksums.txt")
        with open(checksums_filepath, 'w') as f:
            for name, chksum in checksums.items():
                f.write(f"{name} {chksum}\n")
        print(f"Checksums guardados en {checksums_filepath}")

    except Exception as e:
        print(f"Error al dividir el archivo: {e}")
        return [] # Retorna una lista vacía si falla la división.

    return parts # Retorna la lista de nombres de los chunks.

# Función para registrar el seeder en el tracker.
# Informa al tracker sobre su IP:PUERTO y los archivos (chunks) que ofrece.
def register_peer(peer_ip, peer_port, file_list):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Conecta al tracker.
        print(f"Registrando seeder en tracker {TARGET_IP}:{TRACKER_PORT}...")
        s.connect((TARGET_IP, TRACKER_PORT)) 
        # Construye el mensaje de registro: "REGISTER IP:PUERTO archivo1 archivo2 ..."
        registration_message = f"REGISTER {peer_ip}:{peer_port} " + " ".join(file_list)
        s.sendall(registration_message.encode()) # Envía el mensaje de registro.
        response = s.recv(2048).decode()         # Recibe la respuesta del tracker.
        print(f"Respuesta del tracker al registro: {response}")
    except Exception as e:
        print(f"Error al registrar el seeder en el tracker: {e}")
    finally:
        s.close() # Asegura que el socket se cierre.

# Función para manejar las solicitudes entrantes de chunks de otros peers.
# Se ejecuta en un hilo separado por cada conexión para no bloquear el servidor.
def handle_client_request(conn, addr):
    try:
        # Recibe el nombre del chunk solicitado por el cliente.
        part_name = conn.recv(2048).decode().strip() 
        print(f"Solicitud de chunk '{part_name}' de {addr[0]}:{addr[1]}")
        
        # Construye la ruta completa al chunk en el directorio local.
        path = os.path.join(CHUNK_DIR, part_name)
        
        if os.path.exists(path):
            with open(path, 'rb') as f:
                # Lee el chunk en bloques y lo envía al cliente.
                while data := f.read(5120):
                    conn.sendall(data) 
            print(f"Enviado {part_name} a {addr[0]}:{addr[1]}")
        else:
            # Si el chunk no existe, envía un mensaje de error.
            conn.sendall(b"ERROR: Archivo no encontrado")
            print(f"Chunk '{part_name}' no encontrado para {addr[0]}:{addr[1]}")
    except Exception as e:
        print(f"Error al manejar la solicitud del cliente {addr[0]}:{addr[1]}: {e}")
    finally:
        conn.close() # Cierra la conexión después de atender la solicitud.

# Función principal del servidor del seeder.
# Escucha conexiones entrantes en el PEER_PORT para servir chunks.
def peer_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Vincula el socket a todas las interfaces de red en el PEER_PORT.
        s.bind(("", PEER_PORT)) 
        s.listen(10) # Permite hasta 10 conexiones pendientes en la cola.
        print(f"Seeder escuchando en el puerto {PEER_PORT}")
        
        while True:
            # Acepta una nueva conexión entrante.
            conn, addr = s.accept()
            print(f"Conexión establecida con {addr[0]}:{addr[1]}")
            # Inicia un nuevo hilo para manejar la solicitud, permitiendo que el servidor
            # acepte nuevas conexiones mientras el chunk se envía.
            threading.Thread(target=handle_client_request, args=(conn, addr,), daemon=True).start()
    except Exception as e:
        print(f"Error al iniciar el servidor del seeder: {e}")
    finally:
        s.close() # Asegura que el socket del servidor se cierre.

# Función principal que inicia el proceso del Seeder.
def start_seeder():
    # 1. Divide el archivo de video/imagen en chunks y genera sus checksums.
    parts = split_file(VIDEO_FILE)
    if not parts:
        print("No se pudieron generar chunks. Abortando seeder.")
        return

    # 2. Registra el seeder en el tracker con la lista de chunks que ofrece.
    # Usa la IP objetivo y el puerto del seeder.
    register_peer(TARGET_IP, PEER_PORT, parts) 

    # 3. Inicia el servidor del seeder, que estará escuchando para servir los chunks.
    # Este bucle `peer_server()` es bloqueante y se ejecuta indefinidamente.
    peer_server()

# Punto de entrada principal del script.
if __name__ == "__main__":
    start_seeder() # Inicia el seeder.
