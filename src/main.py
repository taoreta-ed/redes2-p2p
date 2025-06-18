import socket
import subprocess
import time
import sys
import os

# Puertos que vamos a verificar para los servicios P2P
TRACKER_PORT = 8000  # Puerto para el servidor del tracker
SEEDER_PORT = 6000   # Puerto para el servidor del seeder
LEECHER_PORT = 6001  # Puerto para el servidor del leecher (como mini-seeder)

# Ruta absoluta donde están los scripts. Es importante que estas rutas sean correctas
# con respecto a la ubicación donde se ejecuta main.py.
TRACKER_SCRIPT = r'tracker/tracker.py'
SEEDER_SCRIPT = r'.seeder/seeder.py'
LEECHER_SCRIPT = r'leecher/leecher.py'

# La dirección IP a la que los clientes (seeder/leecher) se conectarán para el tracker
# y entre ellos. Has cambiado 'localhost' a esta IP específica.
TARGET_IP = "127.0.0.1"

# Función para verificar si un puerto está abierto en una dirección IP específica.
# Esto es útil para saber si un servicio ya se está ejecutando.
def check_port(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)  # Tiempo de espera para la conexión
    try:
        s.connect((ip, port))
        s.close()
        return True  # El puerto está ocupado
    except (socket.timeout, socket.error):
        return False # El puerto está libre
    finally:
        s.close()

# Función para ejecutar un script Python como un proceso separado.
# Esto permite que el tracker, seeder y leecher se ejecuten concurrentemente.
def run_script(script_path):
    if not os.path.exists(script_path):
        print(f"Error: El script no existe en la ruta especificada: {script_path}")
        return False
    try:
        # sys.executable asegura que el script se ejecute con el mismo intérprete Python
        # que está ejecutando main.py
        subprocess.Popen([sys.executable, script_path])
        print(f"Ejecutando {script_path}...")
        return True
    except Exception as e:
        print(f"Error al ejecutar {script_path}: {e}")
        return False

# Función principal para coordinar el inicio de los componentes de la aplicación P2P.
def main():
    print("Verificando puertos...\n")

    # === Verificación e inicio del Tracker ===
    # El tracker debe ser el primero en iniciarse y estar disponible.
    if check_port(TARGET_IP, TRACKER_PORT):
        print(f"El puerto {TRACKER_PORT} ya está ocupado en {TARGET_IP}. Asegúrate de que el tracker no se esté ejecutando.")
        return # Salir si el tracker ya está corriendo o el puerto está ocupado

    print(f"El puerto {TRACKER_PORT} en {TARGET_IP} está libre. Iniciando el tracker...")
    if not run_script(TRACKER_SCRIPT):
        print("No se pudo iniciar el tracker. Abortando.")
        return

    # Esperar un poco para que el tracker tenga tiempo de inicializarse y empezar a escuchar.
    time.sleep(2)

    # === Verificación e inicio del Seeder ===
    # El seeder se registra con el tracker y empieza a ofrecer archivos.
    if check_port(TARGET_IP, SEEDER_PORT):
        print(f"El puerto {SEEDER_PORT} ya está ocupado en {TARGET_IP}. Asegúrate de que el seeder no se esté ejecutando.")
        return

    print(f"El puerto {SEEDER_PORT} en {TARGET_IP} está libre. Iniciando el seeder...")
    if not run_script(SEEDER_SCRIPT):
        print("No se pudo iniciar el seeder. Abortando.")
        return

    # Esperar un poco antes de iniciar el leecher para que el seeder se registre.
    time.sleep(2)

    # === Verificación e inicio del Leecher ===
    # El leecher se conecta al tracker para descubrir peers y descargar chunks.
    # También se convierte en un mini-seeder de los chunks que ya tiene.
    if check_port(TARGET_IP, LEECHER_PORT):
        print(f"El puerto {LEECHER_PORT} ya está ocupado en {TARGET_IP}. Asegúrate de que el leecher no se esté ejecutando.")
        return

    print(f"El puerto {LEECHER_PORT} en {TARGET_IP} está libre. Iniciando el leecher...")
    if not run_script(LEECHER_SCRIPT):
        print("No se pudo iniciar el leecher. Abortando.")
        return

    print("\nTodos los scripts se han ejecutado correctamente. Por favor, revisa las ventanas de terminal para cada script para ver su progreso.")

if __name__ == "__main__":
    main()
