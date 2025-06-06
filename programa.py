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
    
    def enviar_solicitud(self, num_salones=None, num_laboratorios=None):
        inicio = time.time()
        solicitud = {
            'programa': self.nombre,
            'num_salones': num_salones or random.randint(3, 8),
            'num_laboratorios': num_laboratorios or random.randint(2, 4)
        }
        while solicitud['num_salones'] + solicitud['num_laboratorios'] < 7 or solicitud['num_salones'] + solicitud['num_laboratorios'] > 10:
            solicitud['num_salones'] = random.randint(3, 8)
            solicitud['num_laboratorios'] = random.randint(2, 4)
        self.logger.info(f"Enviando solicitud a facultad: {solicitud}")
        self.socket.send_json(solicitud)
        respuesta = self.socket.recv_json()
        fin = time.time()
        tiempo_respuesta = fin - inicio
        self.logger.info(f"Respuesta recibida: {respuesta}")
        self.guardar_respuesta(respuesta)
        exito = respuesta.get('asignacion', {}).get('no_asignados') is None
        with open("metricas_programa.txt", "a") as f:
            f.write(f"{self.nombre},{tiempo_respuesta},{exito}\n")
        return respuesta
    
    def guardar_respuesta(self, respuesta, semestre="2025-10"):
        archivo = f"respuestas_{semestre}.json"
        try:
            with open(archivo, 'a') as f:
                json.dump(respuesta, f, indent=2)
                f.write('\n')
            self.logger.info(f"Respuesta guardada en {archivo}")
        except Exception as e:
            self.logger.error(f"Error al guardar respuesta: {e}")

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