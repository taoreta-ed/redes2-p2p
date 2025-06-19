import socket
import threading
import time

# Puerto donde el tracker escucha conexiones de nuevos peers.
TRACKER_PORT = 8000

# Diccionario que mapea "IP:PUERTO" a una lista de archivos/chunks que el peer ofrece.
peers = {}

def handle_client(conn, addr):
    try:
        data = conn.recv(1024).decode()
        print(f"Solicitud de {addr[0]}:{addr[1]}: {data}")

        if data == "DISCOVER":
            # Envía la lista de todos los peers conocidos.
            peer_list = list(peers.keys())
            
            # Si hay muchos peers, enviarlo en bloques para evitar problemas
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
                file_list = parts[2:] # Lista de archivos/chunks que el peer ofrece
                peers[peer_info] = file_list # Agrega/actualiza el peer en el diccionario
                print(f"Nuevo peer registrado: {peer_info} con archivos: {file_list}")
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
        conn.close() # Cierra la conexión después de manejar la solicitud.

def start_tracker():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("", TRACKER_PORT)) # Escucha en todas las interfaces de red.
        s.listen(10)              # Permite hasta 10 conexiones pendientes.
        print(f"Tracker escuchando en el puerto {TRACKER_PORT}")
        
        # Bucle principal para aceptar nuevas conexiones.
        while True:
            conn, addr = s.accept()
            print(f"Conexión aceptada de {addr[0]}:{addr[1]}")
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
