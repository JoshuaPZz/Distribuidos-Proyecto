import subprocess
import time
import sys
import os
import signal

def iniciar_servidor():
    print("Iniciando servidor...")
    return subprocess.Popen(["python", "servidor.py"])

def iniciar_respaldo(ip_principal, puerto_principal, puerto_respaldo, puerto_control, puerto_respondo):
    print("Iniciando servidor de respaldo...")
    return subprocess.Popen([
        "python3", "servidor_respaldo.py",
        ip_principal, str(puerto_principal), str(puerto_respaldo),
        str(puerto_control), str(puerto_proxy)
    ])

def iniciar_facultad(nombre, servidor_ip, servidor_puerto, puerto_respaldo, puerto_escucha):
    print(f"Iniciando facultad {nombre}...")
    return subprocess.Popen([
        "python", "facultad.py", nombre, servidor_ip,
        str(servidor_puerto), str(puerto_respaldo), str(puerto_escucha)
    ])

def iniciar_programa(nombre, facultad_ip, facultad_puerto):
    print(f"Iniciando programa {nombre}...")
    return subprocess.Popen(["python", "programa.py", nombre, facultad_ip, str(facultad_puerto)])

def main():
    servidor_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.103"  # IP de PC3
    pc1_ip = "192.168.40.101"  # IP de PC1
    pc2_ip = "192.168.40.2"  # IP de PC2
    pc3_ip = "192.168.40.3"  # IP de PC3
    puerto_principal = 5555
    puerto_respaldo = 5556
    puerto_control = 5557
    puerto_proxy = 5558
    procesos = []
    print(f"Usando servidor en {servidor_ip}:{puerto_principal}, respaldo en {servidor_ip}:{puerto_respaldo}")

    # Definir facultades y programas según el anexo
    facultades_programas = {
        "Ciencias_Sociales": ["Psicología", "Sociología", "Trabajo_Social", "AntropologíaSocial", "Comunicación"],
        "Ciencias_Naturales": ["Biología", "Química", "Física", "Geología", "Ciencias_Ambientales"],
        "Ingeniería": ["Ingeniería_Sivil", "Ingeniería_Electrónica", "Ingeniería_de_Sistemas", "Ingeniería_Mecánica", "Ingeniería_Industrial"],
        "Medicina": ["Medicina_General", "Enfermería", "Odontología", "Farmacia", "Terapia_Física"],
        "Derecho": ["Derecho_Penal", "Derecho_Civil", "Derecho_Internacional", "Derecho_Laboral", "Derecho_Constitucional"],
        "Artes": ["Bellas_Artes", "Música", "Teatro", "Danza", "Diseño_Gráfico"],
        "Educación": ["Educación_Primaria", "Educación_Secundaria", "Educación_Especial", "Psicopedagogía", "Administración_Educativa"],
        "Ciencias_Económicas": ["Administración_de_Empresas", "Contabilidad", "Economía", "Mercadotecnia", "Finanzas"],
        "Arquitectura": ["Arquitectura", "Urbanismo", "Diseño_de_Interiores", "Paisajismo", "Restauración_de_Patrimonio"],
        "Tecnología": ["Desarrollo_de_Software", "Redes_y_Telecomunicaciones", "Ciberseguridad", "Inteligencia_Artificial", "Big_Data"],
    }

    try:
        # Iniciar servidor central y respaldo
        if servidor_ip == pc3_ip:
            servidor = iniciar_servidor()
            procesos.append(servidor)
            respaldo = iniciar_respaldo(
                ip_principal=pc3_ip,
                puerto_principal=puerto_principal,
                puerto_respaldo=puerto_respaldo,
                puerto_control=puerto_control,
                puerto_respaldo=puerto_proxy
            )
            procesos.append(respaldo)
            time.sleep(2)
        
        # Iniciar facultades y programas
        base_puerto = 6000
        for facultad, programas in facultades_programas.items():
            facultad_proc = iniciar_facultad(
                nombre=facultad,
                servidor_ip=servidor_ip,
                servidor_puerto=puerto_principal,
                puerto_respaldo=puerto_respaldo,
                puerto_escucha=base_puerto
            )
            procesos.append(facultad_proc)
            for programa in programas:
                programa_proc = iniciar_programa(progama, programa, servidor_ip, base_puerto)
                procesos.append(programa_proc)
                time.sleep(0.5)
            base_puerto += 1
        
        print("\nSimulación en ejecución. Presiona Ctrl+C para detener.\n")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nDeteniendo simulación...")
    finally:
        for proceso in procesos:
            proceso.kill()  # Usa kill en lugar de terminate para forzar cierre
            try:
                proceso.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        print("Simulación finalizada.")

if __name__ == "__main__":
    main()