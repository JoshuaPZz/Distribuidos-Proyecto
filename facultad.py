import zmq
import json
import threading
import time
import logging
import sys
import random
from datetime import datetime

from config import TIMEOUTS

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Facultad:
    def __init__(self, nombre, servidor_ip="localhost", servidor_puerto=5555, respaldo_ip="localhost", puerto_respaldo=5558, puerto_escucha=None):
        self.logger = logging.getLogger(f'Facultad-{nombre}')
        self.nombre = nombre
        self.servidor_ip = servidor_ip
        self.servidor_puerto = servidor_puerto
        self.respaldo_ip = respaldo_ip
        self.puerto_respaldo = puerto_respaldo
        self.puerto_escucha = puerto_escucha or (6000 + random.randint(1, 999))
        
        # Almacenamiento de solicitudes y respuestas
        self.programas_solicitudes = {}
        self.respuestas_asignaciones = {}
        
        # Configuración ZMQ para comunicación con el servidor y programas
        self.context_servidor = zmq.Context()
        self.socket_servidor = self.context_servidor.socket(zmq.REQ)
        self.socket_pub = self.context_servidor.socket(zmq.PUB)
        self.socket_pub.bind(f"tcp://*:{self.puerto_escucha}")
        
        # Iniciar del servidor activo
        self.servidor_activo = f"tcp://{self.servidor_ip}:{self.servidor_puerto}"
        self.fallos_consecutivos = 0
        self.max_fallos = 3
        
        # Flag para controlar el ciclo de ejecución
        self.ejecutando = True
    
    def conectar_servidor(self):
        """Conecta o reconecta al servidor activo."""
        self.socket_servidor.close()
        self.socket_servidor = self.context_servidor.socket(zmq.REQ)
        self.socket_servidor.setsockopt(zmq.RCVTIMEO, TIMEOUTS['confirmacion'])
        self.socket_servidor.connect(self.servidor_activo)
        self.logger.info(f"Conectado al servidor {self.servidor_activo}")

    def iniciar(self):
        """Inicia la facultad y se conecta con el servidor"""
        self.conectar_servidor()
        self.logger.info(f"Facultad {self.nombre} iniciada. Puerto de escucha: {self.puerto_escucha}")
        
        # Iniciar hilo para simular solicitudes
        threading.Thread(target=self.simular_solicitudes, daemon=True).start()
        
        try:
            while self.ejecutando:
                time.sleep(1)
        except KeyboardInterrupt:
            self.ejecutando = False
            self.logger.info(f"Facultad {self.nombre} detenida")
        finally:
            self.socket_servidor.close()
            self.socket_pub.close()
            self.context_servidor.term()
    
    def simular_solicitudes(self):
        programas = [
            "Ingeniería de Sistemas", "Ingeniería Civil", "Medicina", "Derecho", "Biología"
        ]
        while self.ejecutando:
            time.sleep(random.uniform(3, 10))
            programa = random.choice(programas)
            num_salones = random.randint(3, 8)
            num_laboratorios = random.randint(2, 4)
            while num_salones + num_laboratorios < 7 or num_salones + num_laboratorios > 10:
                num_salones = random.randint(3, 8)
                num_laboratorios = random.randint(2, 4)
            solicitud = {
                'facultad': self.nombre,
                'programa': programa,
                'num_salones': num_salones,
                'num_laboratorios': num_laboratorios,
                'num_aulas_moviles': 0
            }
            self.programas_solicitudes[programa] = solicitud
            # Notificar al programa correspondiente
            self.socket_pub.send_string(f"programa_{programa} {json.dumps(solicitud)}")
            self.enviar_solicitud_servidor(solicitud)
    
    def enviar_solicitud_servidor(self, solicitud):
        inicio = time.time()
        try:
            self.socket_servidor.send_json(solicitud)
            respuesta = self.socket_servidor.recv_json()  # Corregir aquí
            fin = time.time()
            tiempo_respuesta = fin - inicio
            self.fallos_consecutivos = 0  # Reiniciar contador de fallos
            self.confirmar_recepcion(respuesta)
            exito = respuesta.get('asignacion', {}).get('no_asignados') is None
            with open("metricas_facultad.txt", "a") as f:
                f.write(f"{solicitud['programa']},{tiempo_respuesta},{exito}\n")
        except zmq.Again:
            self.logger.warning("Timeout al esperar respuesta del servidor")
            self.fallos_consecutivos += 1
            self.conectar_servidor()
            if self.fallos_consecutivos >= self.max_fallos and self.servidor_activo.endswith(f":{self.servidor_puerto}"):
                self.logger.warning("Cambiando al servidor de respaldo")
                self.servidor_activo = f"tcp://{self.respaldo_ip}:{self.puerto_respaldo}"
                self.conectar_servidor()
                self.fallos_consecutivos = 0
        except zmq.ZMQError as e:
            self.logger.error(f"Error enviando solicitud: {e}")
            self.fallos_consecutivos += 1
            self.conectar_servidor()
            if self.fallos_consecutivos >= self.max_fallos and self.servidor_activo.endswith(f":{self.servidor_puerto}"):
                self.logger.warning("Cambiando al servidor de respaldo")
                self.servidor_activo = f"tcp://{self.respaldo_ip}:{self.puerto_respaldo}"
                self.conectar_servidor()
                self.fallos_consecutivos = 0
            
    def guardar_respuesta(self, respuesta, semestre="2025-10"):
        archivo = f"respuestas_{self.nombre}_{semestre}.json"
        try:
            with open(archivo, 'a') as f:
                json.dump(respuesta, f, indent=2)
                f.write('\n')
            self.logger.info(f"Respuesta guardada en {archivo}")
        except Exception as e:
            self.logger.error(f"Error al guardar respuesta: {e}")

    def confirmar_recepcion(self, respuesta):
        self.logger.info(f"Respuesta recibida del servidor: {respuesta}")
        id_solicitud = respuesta.get('id_solicitud')
        if id_solicitud:
            self.respuestas_asignaciones[id_solicitud] = respuesta
            self.guardar_respuesta(respuesta)
            asignacion = respuesta.get('asignacion', {})
            programa = respuesta.get('programa', 'Desconocido')
            self.logger.info(f"Recursos asignados a {programa}:")
            self.logger.info(f"  - Salones: {len(asignacion.get('salones', []))} ({', '.join(asignacion.get('salones', []))})")
            self.logger.info(f"  - Laboratorios: {len(asignacion.get('laboratorios', []))} ({', '.join(asignacion.get('laboratorios', []))})")
            self.logger.info(f"  - Aulas Móviles: {len(asignacion.get('aulas_moviles', []))} ({', '.join(asignacion.get('aulas_moviles', []))})")
            no_asignados = asignacion.get('no_asignados', {})
            if no_asignados:
                self.logger.warning(f"Recursos no asignados: {no_asignados}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python facultad.py <nombre_facultad> [servidor_ip] [servidor_puerto]")
        sys.exit(1)
    
    nombre_facultad = sys.argv[1]
    servidor_ip = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    servidor_puerto = (sys.argv[3]) if len(sys.argv) > 3 else 5555
    
    facultad = Facultad(nombre_facultad, servidor_ip, servidor_puerto)
    facultad.iniciar()