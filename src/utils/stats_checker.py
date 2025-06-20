import socket
import sys
import time
import ast

# Dirección IP y puerto del tracker
TRACKER_IP = "127.0.0.1"
TRACKER_PORT = 8000

def get_tracker_stats():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((TRACKER_IP, TRACKER_PORT))
        s.sendall(b"STATS")
        
        data = s.recv(4096).decode()
        try:
            stats = ast.literal_eval(data)
            print("\n=== ESTADÍSTICAS DEL TRACKER ===")
            print(f"Conexiones activas: {stats['active_connections']}")
            print(f"Total histórico de conexiones: {stats['total_connections']}")
            print(f"Peers registrados: {stats['registered_peers']}")
            print(f"Total chunks compartidos: {stats['total_chunks']}")
            print("==============================\n")
        except Exception as e:
            print(f"Error al procesar estadísticas: {e}")
            print(f"Datos recibidos: {data}")
    
    except Exception as e:
        print(f"Error al conectar con el tracker: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    try:
        # Si se especifica un modo de monitoreo continuo
        if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
            interval = 5  # segundos entre actualizaciones
            if len(sys.argv) > 2:
                try:
                    interval = int(sys.argv[2])
                except ValueError:
                    pass
                
            print(f"Monitoreando estadísticas del tracker cada {interval} segundos. Presiona Ctrl+C para salir.")
            try:
                while True:
                    get_tracker_stats()
                    time.sleep(interval)
            except KeyboardInterrupt:
                print("\nMonitoreo finalizado.")
        else:
            # Consulta única
            get_tracker_stats()
    except Exception as e:
        print(f"Error: {e}")