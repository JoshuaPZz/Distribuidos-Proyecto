import subprocess
import time
import sys
import os
import signal
import threading

def iniciar_servidor():
    """Inicia el servidor en un nuevo proceso"""
    print("Iniciando servidor...")
    servidor = subprocess.Popen(["python", "servidor.py"])
    return servidor

def iniciar_facultad(nombre, servidor_ip="localhost"):
    """Inicia una facultad en un nuevo proceso"""
    print(f"Iniciando facultad {nombre}...")
    facultad = subprocess.Popen(["python", "facultad.py", nombre, servidor_ip])
    return facultad

def main():
    # Verificar parámetros
    if len(sys.argv) > 1:
        servidor_ip = sys.argv[1]
    else:
        servidor_ip = "localhost"
    
    print(f"Usando servidor en {servidor_ip}")
    
    # Lista para mantener referencias a los procesos
    procesos = []
    
    try:
        # Iniciar servidor si estamos en la máquina del servidor
        if servidor_ip == "localhost":
            servidor = iniciar_servidor()
            procesos.append(servidor)
            time.sleep(2)  # Esperar a que el servidor arranque
        
        # Iniciar facultades
        facultades = ["Ingeniería", "Ciencias", "Artes", "Medicina", "Derecho"]
        for nombre in facultades[:3]:  # Iniciar solo 3 facultades como ejemplo
            facultad = iniciar_facultad(nombre, servidor_ip)
            procesos.append(facultad)
            time.sleep(1)  # Esperar un poco entre inicios
        
        print("\nSimulación en ejecución. Presiona Ctrl+C para detener.\n")
        
        # Mantener la simulación corriendo hasta Ctrl+C
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nDeteniendo simulación...")
    finally:
        # Cerrar todos los procesos
        for proceso in procesos:
            proceso.terminate()
            proceso.wait()
        
        print("Simulación finalizada.")

if __name__ == "__main__":
    main()