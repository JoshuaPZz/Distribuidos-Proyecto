import subprocess
import time
import sys
import os
import signal

def iniciar_servidor():
    print("Iniciando servidor...")
    return subprocess.Popen(["python", "servidor.py"])

def iniciar_facultad(nombre, servidor_ip="localhost", puerto="5558"):
    print(f"Iniciando facultad {nombre}...")
    return subprocess.Popen(["python", "facultad.py", nombre, servidor_ip, puerto])

def iniciar_programa(nombre, facultad_ip, facultad_puerto):
    print(f"Iniciando programa {nombre}...")
    return subprocess.Popen(["python", "programa.py", nombre, facultad_ip, str(facultad_puerto)])

def main():
    servidor_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"  # IP de PC3
    pc1_ip = "192.168.1.101"  # IP de PC1
    pc2_ip = "192.168.1.102"  # IP de PC2
    pc3_ip = "192.168.1.103"  # IP de PC3
    procesos = []
    print(f"Usando servidor en {servidor_ip}")

    # Definir facultades y programas según el anexo
    facultades_programas = {
        "Ciencias_Sociales": ["Psicología", "Sociología", "Trabajo_Social", "Antropología", "Comunicación"],
        "Ciencias_Naturales": ["Biología", "Química", "Física", "Geología", "Ciencias_Ambientales"],
        "Ingeniería": ["Ingeniería_Civil", "Ingeniería_Electrónica", "Ingeniería_de_Sistemas", "Ingeniería_Mecánica", "Ingeniería_Industrial"],
        "Medicina": ["Medicina_General", "Enfermería", "Odontología", "Farmacia", "Terapia_Física"],
        "Derecho": ["Derecho_Penal", "Derecho_Civil", "Derecho_Internacional", "Derecho_Laboral", "Derecho_Constitucional"],
        "Artes": ["Bellas_Artes", "Música", "Teatro", "Danza", "Diseño_Gráfico"],
        "Educación": ["Educación_Primaria", "Educación_Secundaria", "Educación_Especial", "Psicopedagogía", "Administración_Educativa"],
        "Ciencias_Económicas": ["Administración_de_Empresas", "Contabilidad", "Economía", "Mercadotecnia", "Finanzas"],
        "Arquitectura": ["Arquitectura", "Urbanismo", "Diseño_de_Interiores", "Paisajismo", "Restauración_de_Patrimonio"],
        "Tecnología": ["Desarrollo_de_Software", "Redes_y_Telecomunicaciones", "Ciberseguridad", "Inteligencia_Artificial", "Big_Data"]
    }

    try:
        # Iniciar servidor central (PC3)
        if servidor_ip == pc3_ip:
            servidor = iniciar_servidor()
            procesos.append(servidor)
            respaldo = subprocess.Popen(["python", "servidor_respaldo.py"], cwd="/path/to/pc1")
            procesos.append(respaldo)
            health_check = subprocess.Popen(["python", "health-check.py"], cwd="/path/to/pc1")
            procesos.append(health_check)
            time.sleep(2)
        
        # Iniciar facultades (PC2)
        base_puerto = 6000
        for facultad, programas in facultades_programas.items():
            facultad_proc = iniciar_facultad(facultad, pc3_ip, "5558")
            procesos.append(facultad_proc)
            # Iniciar programas (distribuidos en PC1, PC2, PC3)
            for i, programa in enumerate(programas):
                if i < 2:  # 2 programas en PC1
                    programa_proc = iniciar_programa(programa, pc2_ip, base_puerto, cwd="/path/to/pc1")
                elif i < 4:  # 2 programas en PC2
                    programa_proc = iniciar_programa(programa, pc2_ip, base_puerto, cwd="/path/to/pc2")
                else:  # 1 programa en PC3
                    programa_proc = iniciar_programa(programa, pc2_ip, base_puerto, cwd="/path/to/pc3")
                procesos.append(programa_proc)
                base_puerto += 1
                time.sleep(0.5)
        
        print("\nSimulación en ejecución. Presiona Ctrl+C para detener.\n")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nDeteniendo simulación...")
    finally:
        for proceso in procesos:
            proceso.terminate()
            proceso.wait()
        print("Simulación finalizada.")

if __name__ == "__main__":
    main()