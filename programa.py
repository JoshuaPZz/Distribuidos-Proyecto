import zmq
import json
import logging
import sys
import time
import random

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ProgramaAcademico:
    def __init__(self, nombre, facultad_ip, facultad_puerto):
        self.logger = logging.getLogger(f'Programa-{nombre}')
        self.nombre = nombre
        self.facultad_ip = facultad_ip
        self.facultad_puerto = facultad_puerto
        
        # Configuración ZMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{facultad_ip}:{facultad_puerto}")
    
    def enviar_solicitud(self, num_salones, num_laboratorios):
        solicitud = {
            'programa': self.nombre,
            'num_salones': num_salones,
            'num_laboratorios': num_laboratorios
        }
        
        self.logger.info(f"Enviando solicitud a facultad: {solicitud}")
        self.socket.send_json(solicitud)
        
        # Esperar respuesta (síncrono)
        respuesta = self.socket.recv_json()
        self.logger.info(f"Respuesta recibida: {respuesta}")
        return respuesta

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python programa.py <nombre> <facultad_ip> <facultad_puerto>")
        sys.exit(1)
    
    nombre = sys.argv[1]
    facultad_ip = sys.argv[2]
    facultad_puerto = int(sys.argv[3])
    
    programa = ProgramaAcademico(nombre, facultad_ip, facultad_puerto)
    
    # Ejemplo: enviar solicitud cada 10 segundos
    while True:
        programa.enviar_solicitud(
            num_salones=random.randint(5, 8),  
            num_laboratorios=random.randint(2, 4)
        )
        time.sleep(10)