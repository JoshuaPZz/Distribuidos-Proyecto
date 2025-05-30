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
    def __init__(self, nombre, servidor_ip="localhost", servidor_puerto=5555, puerto_escucha=None):
        self.logger = logging.getLogger(f'Facultad-{nombre}')
        self.nombre = nombre
        self.servidor_ip = servidor_ip
        self.servidor_puerto = servidor_puerto
        self.puerto_escucha = puerto_escucha or (6000 + random.randint(1, 999))
        
        # Almacenamiento de solicitudes y respuestas
        self.programas_solicitudes = {}
        self.respuestas_asignaciones = {}
        
        # Configuración ZMQ para comunicación con el servidor
        self.context_servidor = zmq.Context()
        self.socket_servidor = self.context_servidor.socket(zmq.REQ)
        
        # Flag para controlar el ciclo de ejecución
        self.ejecutando = True
    
    def iniciar(self):
        """Inicia la facultad y se conecta con el servidor"""
        # Conectar al servidor
        self.socket_servidor.connect(f"tcp://{self.servidor_ip}:{self.servidor_puerto}")
        self.logger.info(f"Facultad {self.nombre} conectada al servidor {self.servidor_ip}:{self.servidor_puerto}")
        self.logger.info(f"Puerto de la facultad {self.puerto_escucha}")
        
        # Iniciar hilo para simular solicitudes
        threading.Thread(target=self.simular_solicitudes, daemon=True).start()
        
        try:
            # En esta versión simplificada, simplemente esperamos
            while self.ejecutando:
                time.sleep(1)
        except KeyboardInterrupt:
            self.ejecutando = False
            self.logger.info(f"Facultad {self.nombre} detenida")
        finally:
            self.socket_servidor.close()
            self.context_servidor.term()
    
    def simular_solicitudes(self):
        """Simula solicitudes de programas académicos"""
        programas = [
            "Ingeniería de Sistemas",
            "Ingeniería Civil",
            "Medicina",
            "Derecho",
            "Biología"
        ]
        
        while self.ejecutando:
            # Esperar un tiempo aleatorio antes de enviar solicitud
            time.sleep(random.uniform(3, 10))
            
            # Seleccionar un programa aleatoriamente
            programa = random.choice(programas)
            
            # Generar solicitud aleatoria
            # Modificar en el método simular_solicitudes:
            solicitud = {
                'facultad': self.nombre,
                'programa': programa,
                'num_salones': random.randint(5, 8),  # Ajustar para que la suma esté entre 7 y 10
                'num_laboratorios': random.randint(2, 4),
                'num_aulas_moviles': 0  # Opcional, según necesidad
            }
            
            # Registrar solicitud
            self.programas_solicitudes[programa] = solicitud
            
            # Enviar solicitud al servidor
            self.enviar_solicitud_servidor(solicitud)
    
    def enviar_solicitud_servidor(self, solicitud):
        """Envía una solicitud al servidor de forma asíncrona"""
        self.logger.info(f"Enviando solicitud al servidor: {solicitud}")
        
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.RCVTIMEO, TIMEOUTS['confirmacion'])
        
        try:
            socket.connect(f"tcp://{self.servidor_ip}:{self.servidor_puerto}")
            socket.send_json(solicitud)
            
            # Esperar respuesta
            respuesta = socket.recv_json()
            self.confirmar_recepcion(respuesta)
            
        except zmq.Again:
            self.logger.warning("Timeout al esperar respuesta del servidor")
            # Lógica de reintento podría ir aquí
        except Exception as e:
            self.logger.error(f"Error al comunicarse con el servidor: {e}")
        finally:
            socket.close()
            context.term()
    
    def confirmar_recepcion(self, respuesta):
        """Procesa la respuesta recibida del servidor"""
        self.logger.info(f"Respuesta recibida del servidor: {respuesta}")
        
        # Guardar respuesta
        id_solicitud = respuesta.get('id_solicitud')
        if id_solicitud:
            self.respuestas_asignaciones[id_solicitud] = respuesta
            
            # Mostrar recursos asignados
            asignacion = respuesta.get('asignacion', {})
            programa = respuesta.get('programa', 'Desconocido')
            
            self.logger.info(f"Recursos asignados a {programa}:")
            self.logger.info(f"  - Salones: {len(asignacion.get('salones', []))} ({', '.join(asignacion.get('salones', []))})")
            self.logger.info(f"  - Laboratorios: {len(asignacion.get('laboratorios', []))} ({', '.join(asignacion.get('laboratorios', []))})")
            self.logger.info(f"  - Aulas Móviles: {len(asignacion.get('aulas_moviles', []))} ({', '.join(asignacion.get('aulas_moviles', []))}")
            
            # Verificar recursos no asignados
            no_asignados = asignacion.get('no_asignados', {})
            if no_asignados:
                self.logger.warning(f"Recursos no asignados por falta de disponibilidad: {no_asignados}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python facultad.py <nombre_facultad> [servidor_ip] [servidor_puerto]")
        sys.exit(1)
    
    nombre_facultad = sys.argv[1]
    servidor_ip = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    servidor_puerto = int(sys.argv[3]) if len(sys.argv) > 3 else 5555
    
    facultad = Facultad(nombre_facultad, servidor_ip, servidor_puerto)
    facultad.iniciar()