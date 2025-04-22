import zmq
import json
import threading
import time
import logging
import socket
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ServidorCentral:
    def __init__(self, puerto_escucha=5555):
        self.logger = logging.getLogger('ServidorCentral')
        self.puerto_escucha = puerto_escucha
        
        # Recursos disponibles
        self.salones = [f"S{i}" for i in range(1, 31)]  # 30 salones
        self.laboratorios = [f"L{i}" for i in range(1, 16)]  # 15 laboratorios
        self.aulas_moviles = [f"AM{i}" for i in range(1, 6)]  # 5 aulas móviles
        
        # Control de recursos asignados
        self.salones_asignados = []
        self.laboratorios_asignados = []
        self.aulas_moviles_asignados = []
        
        # Solicitudes procesadas y no atendidas
        self.solicitudes = {}
        self.solicitudes_no_atendidas = {}
        
        # Locks para control de concurrencia
        self.lock_salones = threading.Lock()
        self.lock_laboratorios = threading.Lock()
        self.lock_aulas_moviles = threading.Lock()
        
        # Preparar contexto ZMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
    
    def iniciar(self):
        """Inicia el servidor y comienza a escuchar solicitudes"""
        self.socket.bind(f"tcp://*:{self.puerto_escucha}")
        self.logger.info(f"Servidor iniciado en puerto {self.puerto_escucha}")

        try:
            ip_local = socket.gethostbyname(socket.gethostname())
            self.logger.info(f"Servidor iniciado en IP {ip_local}, puerto {self.puerto_escucha}")
        except Exception as e:
            self.logger.warning(f"No se pudo obtener la IP local: {e}")
        
        try:
            while True:
                mensaje = self.socket.recv_json()
                self.logger.info(f"Solicitud recibida: {mensaje}")
                respuesta = self.procesar_solicitud(mensaje)
                self.socket.send_json(respuesta)
        except KeyboardInterrupt:
            self.logger.info("Servidor detenido")
        finally:
            self.socket.close()
            self.context.term()
    
    def procesar_solicitud(self, mensaje):
        """Procesa una solicitud y envía respuesta"""
        # Extraer información de la solicitud
        facultad = mensaje.get('facultad', 'Desconocida')
        programa = mensaje.get('programa', 'Desconocido')
        num_salones = mensaje.get('num_salones', 0)
        num_laboratorios = mensaje.get('num_laboratorios', 0)
        num_aulas_moviles = mensaje.get('num_aulas_moviles', 0)
        
        # Registrar solicitud
        id_solicitud = f"{facultad}-{programa}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.solicitudes[id_solicitud] = mensaje
        
        # Procesar asignación de recursos
        resultado = self.asignar_recursos(num_salones, num_laboratorios, num_aulas_moviles)
        
        # Agregar información de asignación
        respuesta = {
            'id_solicitud': id_solicitud,
            'facultad': facultad,
            'programa': programa,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'asignacion': resultado
        }
        
        # Enviar respuesta
        self.socket.send_json(respuesta)
        self.logger.info(f"Respuesta enviada para solicitud {id_solicitud}")
    
    def asignar_recursos(self, num_salones, num_laboratorios, num_aulas_moviles):
        """Asigna recursos según la solicitud"""
        salones_asignados = []
        laboratorios_asignados = []
        aulas_moviles_asignadas = []
        recursos_no_disponibles = {}
        
        # Asignar salones
        with self.lock_salones:
            salones_disponibles = [s for s in self.salones if s not in self.salones_asignados]
            if len(salones_disponibles) >= num_salones:
                salones_asignados = salones_disponibles[:num_salones]
                self.salones_asignados.extend(salones_asignados)
            else:
                recursos_no_disponibles['salones'] = num_salones - len(salones_disponibles)
                salones_asignados = salones_disponibles
                self.salones_asignados.extend(salones_disponibles)
        
        # Asignar laboratorios
        with self.lock_laboratorios:
            labs_disponibles = [l for l in self.laboratorios if l not in self.laboratorios_asignados]
            if len(labs_disponibles) >= num_laboratorios:
                laboratorios_asignados = labs_disponibles[:num_laboratorios]
                self.laboratorios_asignados.extend(laboratorios_asignados)
            else:
                recursos_no_disponibles['laboratorios'] = num_laboratorios - len(labs_disponibles)
                laboratorios_asignados = labs_disponibles
                self.laboratorios_asignados.extend(labs_disponibles)
        
        # Asignar aulas móviles
        with self.lock_aulas_moviles:
            am_disponibles = [am for am in self.aulas_moviles if am not in self.aulas_moviles_asignados]
            if len(am_disponibles) >= num_aulas_moviles:
                aulas_moviles_asignadas = am_disponibles[:num_aulas_moviles]
                self.aulas_moviles_asignados.extend(aulas_moviles_asignadas)
            else:
                recursos_no_disponibles['aulas_moviles'] = num_aulas_moviles - len(am_disponibles)
                aulas_moviles_asignadas = am_disponibles
                self.aulas_moviles_asignados.extend(am_disponibles)
        
        # Crear respuesta con resultados
        return {
            'salones': salones_asignados,
            'laboratorios': laboratorios_asignados,
            'aulas_moviles': aulas_moviles_asignadas,
            'no_asignados': recursos_no_disponibles
        }

if __name__ == "__main__":
    servidor = ServidorCentral()
    servidor.iniciar()