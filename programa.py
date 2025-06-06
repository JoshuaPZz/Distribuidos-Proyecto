import zmq
import json
import logging
import sys
import time

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
        
        # Configuración ZMQ para comunicación con la facultad
        self.context = zmq.Context()
        self.socket_facultad = self.context.socket(zmq.REQ)
        self.socket_facultad.connect(f"tcp://{facultad_ip}:{facultad_puerto}")
        
        # Socket para recibir notificaciones de la facultad (SUB)
        self.socket_sub = self.context.socket(zmq.SUB)
        self.socket_sub.connect(f"tcp://{facultad_ip}:{facultad_puerto}")
        self.socket_sub.setsockopt_string(zmq.SUBSCRIBE, f"programa_{nombre}")
    
    def enviar_solicitud(self, solicitud):
        inicio = time.time()
        self.logger.info(f"Enviando solicitud a facultad: {solicitud}")
        self.socket_facultad.send_json(solicitud)
        respuesta = self.socket_facultad.recv_json()
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

    def recibir_notificacion(self):
        """Recibe notificaciones de la facultad sobre nuevas solicitudes."""
        while True:
            try:
                topic, mensaje = self.socket_sub.recv_string().split(" ", 1)
                solicitud = json.loads(mensaje)
                self.logger.info(f"Recibida notificación de solicitud para {self.nombre}: {solicitud}")
                return solicitud
            except Exception as e:
                self.logger.error(f"Error recibiendo notificación: {e}")
                time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python programa.py <nombre> <facultad_ip> <facultad_puerto>")
        sys.exit(1)
    
    nombre = sys.argv[1]
    facultad_ip = sys.argv[2]
    facultad_puerto = int(sys.argv[3])
    
    programa = ProgramaAcademico(nombre, facultad_ip, facultad_puerto)
    
    # Bucle principal: recibe notificaciones de la facultad y envía solicitudes
    while True:
        solicitud = programa.recibir_notificacion()
        if solicitud and solicitud.get('programa') == nombre:
            programa.enviar_solicitud(solicitud)
        time.sleep(1)  # Pequeña pausa para evitar consumo excesivo de CPU