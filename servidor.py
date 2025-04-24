from pathlib import Path
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
        
        # Recursos disponibles (modificar estas líneas)
        self.salones = [f"S{i}" for i in range(1, 381)]  # 380 salones
        self.laboratorios = [f"L{i}" for i in range(1, 61)]  # 60 laboratorios
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
        
        # Archivos para persistencia
        self.archivo_solicitudes = "solicitudes.json"
        self.archivo_no_atendidas = "solicitudes_no_atendidas.json"
        
        # Cargar datos persistentes si existen
        self._cargar_datos()
    
    # Modificar el método iniciar para usar hilos
    def iniciar(self):
        self.socket.bind(f"tcp://*:{self.puerto_escucha}")
        self.logger.info(f"Servidor iniciado en puerto {self.puerto_escucha}")
        
        # Configurar un timeout en el socket para verificar interrupciones
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1000 ms = 1 segundo
        
        try:
            while True:
                try:
                    mensaje = self.socket.recv_json()
                    self.logger.info(f"Solicitud recibida: {mensaje}")
                    
                    respuesta = self.procesar_solicitud(mensaje)
                    self.socket.send_json(respuesta)
                except zmq.error.Again:
                    # Timeout en recv_json(), continúa el ciclo para verificar interrupciones
                    continue
                
        except KeyboardInterrupt:
            self.logger.info("Servidor detenido")
        finally:
            self._guardar_datos()  # Asegurarse de guardar datos antes de salir
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
        
        # Crear respuesta
        respuesta = {
            'id_solicitud': id_solicitud,
            'facultad': facultad,
            'programa': programa,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'asignacion': resultado
        }
        
        return respuesta  # El servidor enviará esta respuesta y esperará nueva solicitud
        
    def _cargar_datos(self):
        """Carga datos persistentes desde archivos"""
        try:
            if Path(self.archivo_solicitudes).exists():
                with open(self.archivo_solicitudes, 'r') as f:
                    self.solicitudes = json.load(f)
                    
            if Path(self.archivo_no_atendidas).exists():
                with open(self.archivo_no_atendidas, 'r') as f:
                    self.solicitudes_no_atendidas = json.load(f)
        except Exception as e:
            self.logger.error(f"Error cargando datos: {e}")

    def _guardar_datos(self):
        """Guarda datos persistentes en archivos"""
        try:
            with open(self.archivo_solicitudes, 'w') as f:
                json.dump(self.solicitudes, f, indent=2)
                
            with open(self.archivo_no_atendidas, 'w') as f:
                json.dump(self.solicitudes_no_atendidas, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando datos: {e}")

    
    def asignar_recursos(self, num_salones, num_laboratorios, num_aulas_moviles):
        """Asigna recursos según la solicitud y maneja casos de falta de disponibilidad"""
        id_solicitud = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{threading.get_ident()}"
        
        salones_asignados = []
        laboratorios_asignados = []
        aulas_moviles_asignadas = []
        recursos_no_disponibles = {}
        alerta_generada = False

        # Asignar salones con control de concurrencia
        with self.lock_salones:
            try:
                salones_disponibles = [s for s in self.salones if s not in self.salones_asignados]
                
                if len(salones_disponibles) >= num_salones:
                    salones_asignados = salones_disponibles[:num_salones]
                    self.salones_asignados.extend(salones_asignados)
                else:
                    recursos_no_disponibles['salones'] = num_salones - len(salones_disponibles)
                    salones_asignados = salones_disponibles
                    self.salones_asignados.extend(salones_disponibles)
                    alerta_generada = True
                    
                    self.logger.warning(f"No hay suficientes salones disponibles. Faltan: {recursos_no_disponibles['salones']}")
            except Exception as e:
                self.logger.error(f"Error asignando salones: {e}")

        # Asignar laboratorios con control de concurrencia
        with self.lock_laboratorios:
            try:
                labs_disponibles = [l for l in self.laboratorios if l not in self.laboratorios_asignados]
                
                if len(labs_disponibles) >= num_laboratorios:
                    laboratorios_asignados = labs_disponibles[:num_laboratorios]
                    self.laboratorios_asignados.extend(laboratorios_asignados)
                else:
                    # Intentar asignar aulas móviles si faltan laboratorios
                    faltan_labs = num_laboratorios - len(labs_disponibles)
                    
                    with self.lock_aulas_moviles:
                        am_disponibles = [am for am in self.aulas_moviles if am not in self.aulas_moviles_asignados]
                        
                        if len(am_disponibles) >= faltan_labs:
                            aulas_moviles_asignadas = am_disponibles[:faltan_labs]
                            self.aulas_moviles_asignados.extend(aulas_moviles_asignadas)
                            laboratorios_asignados = labs_disponibles
                            self.laboratorios_asignados.extend(labs_disponibles)
                            recursos_no_disponibles['laboratorios_convertidos'] = faltan_labs
                        else:
                            recursos_no_disponibles['laboratorios'] = faltan_labs
                            laboratorios_asignados = labs_disponibles
                            self.laboratorios_asignados.extend(labs_disponibles)
                            alerta_generada = True
                            
                    self.logger.warning(f"No hay suficientes laboratorios disponibles. Faltan: {faltan_labs}")
            except Exception as e:
                self.logger.error(f"Error asignando laboratorios: {e}")

        # Asignar aulas móviles adicionales si fueron solicitadas directamente
        with self.lock_aulas_moviles:
            try:
                am_disponibles = [am for am in self.aulas_moviles if am not in self.aulas_moviles_asignados]
                am_directas = num_aulas_moviles - len(aulas_moviles_asignadas)
                
                if am_directas > 0:
                    if len(am_disponibles) >= am_directas:
                        aulas_moviles_asignadas.extend(am_disponibles[:am_directas])
                        self.aulas_moviles_asignados.extend(am_disponibles[:am_directas])
                    else:
                        recursos_no_disponibles['aulas_moviles'] = am_directas - len(am_disponibles)
                        aulas_moviles_asignadas.extend(am_disponibles)
                        self.aulas_moviles_asignados.extend(am_disponibles)
                        alerta_generada = True
                        
                        self.logger.warning(f"No hay suficientes aulas móviles disponibles. Faltan: {recursos_no_disponibles['aulas_moviles']}")
            except Exception as e:
                self.logger.error(f"Error asignando aulas móviles: {e}")

        # Registrar alerta si hubo falta de recursos
        if alerta_generada:
            alerta = {
                'id_solicitud': id_solicitud,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'recursos_faltantes': recursos_no_disponibles,
                'solicitud_original': {
                    'salones': num_salones,
                    'laboratorios': num_laboratorios,
                    'aulas_moviles': num_aulas_moviles
                },
                'asignacion_real': {
                    'salones': len(salones_asignados),
                    'laboratorios': len(laboratorios_asignados),
                    'aulas_moviles': len(aulas_moviles_asignadas)
                }
            }
            
            with threading.Lock():
                self.solicitudes_no_atendidas[id_solicitud] = alerta
                self._guardar_datos()
                
            self.logger.warning(f"ALERTA: No se pudieron asignar todos los recursos solicitados: {alerta}")

        # Crear respuesta con resultados
        resultado = {
            'salones': salones_asignados,
            'laboratorios': laboratorios_asignados,
            'aulas_moviles': aulas_moviles_asignadas,
            'no_asignados': recursos_no_disponibles if recursos_no_disponibles else None
        }

        # Registrar asignación
        with threading.Lock():
            self.solicitudes[id_solicitud] = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'solicitud': {
                    'salones': num_salones,
                    'laboratorios': num_laboratorios,
                    'aulas_moviles': num_aulas_moviles
                },
                'asignacion': resultado,
                'estado': 'completa' if not recursos_no_disponibles else 'parcial'
            }
            self._guardar_datos()

        return resultado

if __name__ == "__main__":
    servidor = ServidorCentral()
    servidor.iniciar()