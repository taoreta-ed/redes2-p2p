import socket
import threading
import time
import random

# Puerto donde el tracker escucha conexiones de nuevos peers.
TRACKER_PORT = 8000

# Diccionario que mapea "IP:PUERTO" a una lista de archivos/chunks que el peer ofrece.
peers = {}

# Variables para el contador de conexiones
active_connections = 0
connection_lock = threading.Lock()  # Para acceso seguro a la variable desde múltiples hilos
total_connections = 0  # Total histórico de conexiones

def handle_client(conn, addr):
    global active_connections, total_connections
    
    # Incrementar contadores al iniciar una nueva conexión
    with connection_lock:
        active_connections += 1
        total_connections += 1
        current_active = active_connections
        current_total = total_connections
    
    print(f"Nueva conexión de {addr[0]}:{addr[1]} | Activas: {current_active} | Total histórico: {current_total}")
    
    try:
        data = conn.recv(1024).decode()
        print(f"Solicitud de {addr[0]}:{addr[1]}: {data}")

        if data == "DISCOVER":
            # Limitar la cantidad de peers devueltos para evitar respuestas enormes
            peer_list = list(peers.keys())
            
            # Si hay demasiados peers, enviar un subconjunto (máximo 20 peers aleatorios)
            if len(peer_list) > 20:
                peer_list = random.sample(peer_list, 20)
                print(f"Enviando muestra aleatoria de 20 peers (de un total de {len(peers)}) a {addr[0]}:{addr[1]}")
            
            # Enviar la respuesta en bloques
            response = str(peer_list).encode()
            
            # Enviar en bloques de 4KB
            total_sent = 0
            while total_sent < len(response):
                sent = conn.send(response[total_sent:total_sent + 4096])
                if sent == 0:
                    raise RuntimeError("Socket connection broken")
                total_sent += sent
            
            print(f"Enviada lista de {len(peer_list)} peers ({len(response)} bytes) a {addr[0]}:{addr[1]}")
        
        elif data.startswith("REGISTER"):
            # El mensaje esperado es "REGISTER IP:PUERTO archivo1 archivo2 ..."
            parts = data.split()
            if len(parts) >= 2:
                peer_info = parts[1] # "IP:PUERTO" del peer
                
                # Limitar la cantidad de chunks por peer para evitar mensajes enormes
                file_list = parts[2:100] if len(parts) > 100 else parts[2:] # Máximo 98 chunks
                
                peers[peer_info] = file_list # Agrega/actualiza el peer en el diccionario
                print(f"Nuevo peer registrado: {peer_info} con {len(file_list)} chunks")
                conn.sendall(b"Peer registrado correctamente.")
            else:
                conn.sendall(b"Formato de registro incorrecto.")
        
        elif data.startswith("GET_CHUNKS"):
            # Solicitud para obtener los chunks de un peer específico.
            peer_to_query = data.split()[1]
            if peer_to_query in peers:
                # Si el peer existe, envía sus archivos (chunks) separados por comas.
                conn.sendall(",".join(peers[peer_to_query]).encode())
            else:
                conn.sendall(b"Peer no encontrado.")
        
        # Agregar un nuevo comando para solicitar peers que tengan un chunk específico
        elif data.startswith("FIND_CHUNK"):
            chunk_name = data.split()[1]
            peers_with_chunk = []
            
            for peer_info, chunks in peers.items():
                if chunk_name in chunks:
                    peers_with_chunk.append(peer_info)
            
            conn.sendall(str(peers_with_chunk).encode())
            print(f"Enviada lista de {len(peers_with_chunk)} peers con el chunk {chunk_name}")
            
        # Nuevo comando para obtener las estadísticas de conexiones
        elif data == "STATS":
            with connection_lock:
                stats = {
                    "active_connections": active_connections,
                    "total_connections": total_connections,
                    "registered_peers": len(peers),
                    "total_chunks": sum(len(chunks) for chunks in peers.values())
                }
            conn.sendall(str(stats).encode())
            print(f"Enviando estadísticas al cliente {addr[0]}:{addr[1]}")

        else:
            # Comando no reconocido.
            conn.sendall(b"Comando no reconocido.")
    
    except Exception as e:
        print(f"Error al manejar la solicitud del cliente {addr[0]}:{addr[1]}: {e}")
        try:
            conn.sendall(b"Error en la solicitud.")
        except socket.error:
            pass
    
    finally:
        # Decrementar contador al finalizar la conexión
        with connection_lock:
            active_connections -= 1
            current_active = active_connections
        
        print(f"Conexión cerrada con {addr[0]}:{addr[1]} | Conexiones activas: {current_active}")
        conn.close() # Cierra la conexión después de manejar la solicitud.

# Función para mostrar periódicamente estadísticas en la consola del tracker
def stats_monitor():
    while True:
        time.sleep(10)  # Actualizar cada 10 segundos
        with connection_lock:
            print(f"\n--- ESTADÍSTICAS DEL TRACKER ---")
            print(f"Conexiones activas: {active_connections}")
            print(f"Total de conexiones: {total_connections}")
            print(f"Peers registrados: {len(peers)}")
            print(f"Total chunks compartidos: {sum(len(chunks) for chunks in peers.values())}")
            print(f"---------------------------\n")

def start_tracker():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Permitir reutilización del socket para evitar errores "Address already in use"
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        s.bind(("", TRACKER_PORT)) # Escucha en todas las interfaces de red.
        s.listen(50)              # Aumentado a 50 conexiones pendientes.
        print(f"Tracker escuchando en el puerto {TRACKER_PORT}")
        
        # Iniciar hilo para mostrar estadísticas periódicamente
        stats_thread = threading.Thread(target=stats_monitor, daemon=True)
        stats_thread.start()
        
        # Bucle principal para aceptar nuevas conexiones.
        while True:
            conn, addr = s.accept()
            # Inicia un nuevo hilo para manejar la conexión, para no bloquear el tracker.
            threading.Thread(target=handle_client, args=(conn, addr,), daemon=True).start()
    
    except KeyboardInterrupt:
        print("Tracker detenido por el usuario.")
    except Exception as e:
        print(f"Error en el tracker: {e}")
    finally:
        s.close() # Asegura que el socket se cierre.

if __name__ == "__main__":
    start_tracker() # Inicia el tracker.
