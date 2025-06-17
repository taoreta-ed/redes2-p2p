import socket
import threading
import time
import os
import ast

# Parámetros de configuración del Tracker
TRACKER_PORT = 8000     # Puerto en el que el tracker escucha conexiones TCP de peers
DISCOVERY_PORT = 7000   # Puerto para el descubrimiento de peers (UDP Broadcast, aunque en este código solo se usa para ACK de peers)

# Diccionario global para almacenar la información de los peers registrados.
# La clave es "IP:PUERTO" y el valor es una lista de los archivos (chunks) que ofrece ese peer.
peers = {}

# Dirección IP donde el tracker escuchará. 
# Vacío ("") significa que escucha en todas las interfaces de red disponibles.
TRACKER_HOST = "" 

# Función para manejar las conexiones individuales de los clientes (peers).
# Se ejecuta en un hilo separado para no bloquear el servidor principal.
def handle_client(conn, addr):
    try:
        # Recibe la solicitud del cliente. El cliente envía un comando como "REGISTER" o "DISCOVER".
        data = conn.recv(1024).decode().strip()
        print(f"Solicitud recibida de {addr[0]}:{addr[1]}: '{data}'")

        if data == "DISCOVER":
            # Si la solicitud es "DISCOVER", el tracker devuelve una lista de los peers registrados.
            # Convertimos las claves del diccionario `peers` (que son "IP:PUERTO") a una lista.
            available_peers = list(peers.keys())
            # Enviamos la lista convertida a string. Se necesita `ast.literal_eval` en el cliente para parsearla.
            conn.sendall(str(available_peers).encode())
            print(f"Enviando lista de peers a {addr[0]}:{addr[1]}: {available_peers}")

        elif data.startswith("REGISTER"):
            # Si la solicitud es "REGISTER", un peer está intentando registrarse.
            # El mensaje esperado es "REGISTER IP:PUERTO archivo1 archivo2 ..."
            parts = data.split()
            if len(parts) >= 2:
                peer_info = parts[1] # "IP:PUERTO" del peer
                file_list = parts[2:] # Lista de archivos/chunks que el peer ofrece
                peers[peer_info] = file_list # Agrega/actualiza el peer en el diccionario
                print(f"Nuevo peer registrado: {peer_info} con archivos: {file_list}")
                conn.sendall(b"Peer registrado correctamente.")
            else:
                conn.sendall(b"Formato de registro incorrecto.")
        
        elif data.startswith("GET_CHUNKS"):
            # Solicitud para obtener los chunks de un peer específico.
            # Aunque este tracker solo almacena qué peers tienen qué archivos, no distribuye la información de chunks específicos.
            # Podría ser una mejora futura para devolver los chunks asociados a un peer.
            # Actualmente, la lógica del `leecher` y `seeder` asume que el `leecher` descarga de un `seeder` directamente.
            peer_to_query = data.split()[1]
            if peer_to_query in peers:
                # Si el peer existe, envía sus archivos (chunks) separados por comas.
                conn.sendall(",".join(peers[peer_to_query]).encode())
            else:
                conn.sendall(b"Peer no encontrado.")

        else:
            # Comando no reconocido.
            conn.sendall(b"Comando no reconocido.")
    
    except Exception as e:
        print(f"Error al manejar la solicitud del cliente {addr[0]}:{addr[1]}: {e}")
        # En caso de error, el servidor puede enviar un mensaje de error al cliente.
        try:
            conn.sendall(b"Error en la solicitud.")
        except socket.error:
            pass # Ignorar si la conexión ya está cerrada o rota
    
    finally:
        # Asegurarse de cerrar la conexión con el cliente.
        conn.close()
        print(f"Conexión con {addr[0]}:{addr[1]} cerrada.")

# Función principal del servidor del tracker. Escucha conexiones entrantes.
def tracker_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Vincula el socket a la dirección y puerto especificados.
        s.bind((TRACKER_HOST, TRACKER_PORT))
        # Empieza a escuchar conexiones. El número 10 es el tamaño de la cola de conexiones pendientes.
        s.listen(10)
        print(f"Tracker escuchando en {TRACKER_HOST}:{TRACKER_PORT}")
        
        while True:
            # Acepta una nueva conexión entrante. `conn` es un nuevo objeto socket para la comunicación
            # y `addr` es la dirección del cliente (IP, Puerto).
            conn, addr = s.accept()
            print(f"Conexión establecida con {addr[0]}:{addr[1]}")
            # Inicia un nuevo hilo para manejar la conexión del cliente, permitiendo que el servidor
            # acepte nuevas conexiones mientras procesa la actual. `daemon=True` hace que el hilo
            # se cierre automáticamente cuando el programa principal termina.
            threading.Thread(target=handle_client, args=(conn, addr,), daemon=True).start()
    except Exception as e:
        print(f"Error al iniciar o ejecutar el servidor del tracker: {e}")
    finally:
        s.close() # Asegurarse de cerrar el socket del servidor si hay un error o al finalizar.

# Función para iniciar el tracker.
def start_tracker():
    # El tracker se ejecuta en un hilo separado para que el `main.py` pueda continuar
    # después de iniciarlo (aunque en tu `main.py` solo se espera y luego se cierra).
    # Sin embargo, el servidor principal del tracker (dentro de `tracker_server`) tiene un bucle `while True`,
    # por lo que mantendrá el proceso del tracker vivo.
    threading.Thread(target=tracker_server, daemon=True).start()

    # Este bucle `while True` en el hilo principal del tracker mantiene el script en ejecución.
    # Si se quitara, el script terminaría inmediatamente después de lanzar el hilo del servidor.
    while True:
        time.sleep(1) # Espera 1 segundo para no consumir CPU innecesariamente.

# Cuando el script se ejecuta directamente (no importado como módulo), inicia el tracker.
if __name__ == "__main__":
    start_tracker()
