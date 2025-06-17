#main.py
import socket
import subprocess
import time
import sys

# Puertos que vamos a verificar
TRACKER_PORT = 8000  # Puerto para el tracker
SEEDER_PORT = 6000  # Puerto para el seeder
LEECHER_PORT = 6001  # Puerto para el leecher

# Ruta absoluta donde están los scripts
TRACKER_SCRIPT = r'./src/tracker/tracker.py'
SEEDER_SCRIPT = r'./src/seeder/seeder.py'
LEECHER_SCRIPT = r'./src/leecher/leecher.py'

# Función para verificar si un puerto está abierto
def check_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)  # Tiempo de espera para la conexión
    try:
        s.connect(("8.12.0.166", port))
        s.close()
        return True
    except (socket.timeout, socket.error):
        return False

# Función para ejecutar un script (seeder, leecher o tracker)
def run_script(script_path):
    try:
        subprocess.Popen([sys.executable, script_path])  # Ejecuta el script
        print(f"Ejecutando {script_path}...")
    except Exception as e:
        print(f"Error al ejecutar {script_path}: {e}")

# Función principal para verificar puertos y ejecutar los scripts
def main():
    # Verificar puertos
    print("Verificando puertos...\n")

    # Verificar puerto del tracker
    if check_port(TRACKER_PORT):
        print(f"El puerto {TRACKER_PORT} ya está ocupado. Asegúrate de que el tracker no se esté ejecutando.")
        return
    else:
        print(f"El puerto {TRACKER_PORT} está libre. Iniciando el tracker...")

    # Ejecutar el tracker
    run_script(TRACKER_SCRIPT)

    # Esperar a que el tracker esté listo
    time.sleep(2)

    # Verificar puerto del seeder
    if check_port(SEEDER_PORT):
        print(f"El puerto {SEEDER_PORT} ya está ocupado. Asegúrate de que el seeder no se esté ejecutando.")
        return
    else:
        print(f"El puerto {SEEDER_PORT} está libre. Iniciando el seeder...")

    # Ejecutar el seeder
    run_script(SEEDER_SCRIPT)

    # Esperar un poco antes de iniciar el leecher
    time.sleep(2)

    # Verificar puerto del leecher
    if check_port(LEECHER_PORT):
        print(f"El puerto {LEECHER_PORT} ya está ocupado. Asegúrate de que el leecher no se esté ejecutando.")
        return
    else:
        print(f"El puerto {LEECHER_PORT} está libre. Iniciando el leecher...")

    # Ejecutar el leecher
    run_script(LEECHER_SCRIPT)

    print("Todos los scripts se han ejecutado correctamente.")

if __name__ == "__main__":
    main()
