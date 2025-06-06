from pathlib import Path
import zmq
import json
import threading
import logging
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ServidorCentral:
    def __init__(self, puerto_escucha=5555, num_trabajadores=5):
        self.logger = logging.getLogger('ServidorCentral')
        self.puerto_escucha = puerto_escucha
        self.num_trabajadores = num_trabajadores
        self.context = zmq.Context()
        self.salones = [f"S{i}" for i in range(1, 381)]  # 380 salones
        self.laboratorios = [f"L{i}" for i in range(1, 61)]  # 60 laboratorios
        self.aulas_moviles = [f"AM{i}" for i in range(1, 6)]  # 5 aulas móviles
        self.salones_asignados = []
        self.laboratorios_asignados = []
        self.aulas_moviles_asignados = []
        self.solicitudes = {}
        self.solicitudes_no_atendidas = {}
        self.lock = threading.Lock()  # Para sincronizar acceso a recursos compartidos
        self.archivo_solicitudes = "solicitudes.json"
        self.archivo_no_atendidas = "solicitudes_no_atendidas.json"
        self._cargar_datos()

    def _cargar_datos(self):
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
        try:
            with open(self.archivo_solicitudes, 'w') as f:
                json.dump(self.solicitudes, f, indent=2)
            with open(self.archivo_no_atendidas, 'w') as f:
                json.dump(self.solicitudes_no_atendidas, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando datos: {e}")

    def asignar_recursos(self, num_salones, num_laboratorios, num_aulas_moviles):
        id_solicitud = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{threading.get_ident()}"
        salones_asignados = []
        laboratorios_asignados = []
        aulas_moviles_asignadas = []
        recursos_no_disponibles = {}
        alerta_generada = False

        with self.lock:
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

            labs_disponibles = [l for l in self.laboratorios if l not in self.laboratorios_asignados]
            if len(labs_disponibles) >= num_laboratorios:
                laboratorios_asignados = labs_disponibles[:num_laboratorios]
                self.laboratorios_asignados.extend(laboratorios_asignados)
            else:
                faltan_labs = num_laboratorios - len(labs_disponibles)
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
            with self.lock:
                self.solicitudes_no_atendidas[id_solicitud] = alerta
                self._guardar_datos()
            self.logger.warning(f"ALERTA: No se pudieron asignar todos los recursos solicitados: {alerta}")

        resultado = {
            'salones': salones_asignados,
            'laboratorios': laboratorios_asignados,
            'aulas_moviles': aulas_moviles_asignadas,
            'no_asignados': recursos_no_disponibles if recursos_no_disponibles else None
        }

        with self.lock:
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

    def procesar_solicitud(self, mensaje):
        self.logger.info(f"Procesando solicitud: {mensaje}")
        if mensaje.get("comando") == "ping":
            return {"estado": "activo"}
        
        facultad = mensaje.get('facultad', 'Desconocida')
        programa = mensaje.get('programa', 'Desconocido')
        num_salones = mensaje.get('num_salones', 0)
        num_laboratorios = mensaje.get('num_laboratorios', 0)
        num_aulas_moviles = mensaje.get('num_aulas_moviles', 0)
        id_solicitud = f"{facultad}-{programa}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        with self.lock:
            self.solicitudes[id_solicitud] = mensaje
        resultado = self.asignar_recursos(num_salones, num_laboratorios, num_aulas_moviles)
        
        respuesta = {
            'id_solicitud': id_solicitud,
            'facultad': facultad,
            'programa': programa,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'asignacion': resultado
        }
        return respuesta

    def trabajador(self, worker_url):
        """Función que ejecuta cada trabajador"""
        socket = self.context.socket(zmq.REP)
        socket.connect(worker_url)
        self.logger.info(f"Trabajador conectado a {worker_url}")
        while True:
            try:
                mensaje = socket.recv_json()
                respuesta = self.procesar_solicitud(mensaje)
                socket.send_json(respuesta)
            except Exception as e:
                self.logger.error(f"Error en trabajador: {e}")

    def iniciar(self):
        # Configurar el frontend (ROUTER)
        frontend = self.context.socket(zmq.ROUTER)
        frontend.bind(f"tcp://*:{self.puerto_escucha}")
        self.logger.info(f"Servidor frontend iniciado en puerto {self.puerto_escucha}")

        # Configurar el backend (DEALER)
        backend = self.context.socket(zmq.DEALER)
        backend.bind("inproc://workers")

        # Iniciar trabajadores
        for i in range(self.num_trabajadores):
            threading.Thread(target=self.trabajador, args=("inproc://workers",), daemon=True).start()

        # Conectar frontend y backend con un proxy
        self.logger.info("Iniciando proxy ROUTER-DEALER")
        zmq.proxy(frontend, backend)

if __name__ == "__main__":
    servidor = ServidorCentral()
    servidor.iniciar()