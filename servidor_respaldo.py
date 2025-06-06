from pathlib import Path
import zmq
import json
import threading
import time
import logging
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class RespaldoHealthChecker:
    def __init__(self, ip_principal="", puerto_principal=5555, puerto_respaldo=5556, puerto_control=5557, puerto_proxy=5558):
        self.logger = logging.getLogger('RespaldoHealthChecker')
        self.ip_principal = ip_principal
        self.puerto_principal = puerto_principal
        self.puerto_respaldo = puerto_respaldo
        self.puerto_control = puerto_control
        self.puerto_proxy = puerto_proxy
        self.estado = "pasivo"
        self.fallos_consecutivos = 0
        self.max_fallos = 3
        self.servidor_activo = f"tcp://{self.ip_principal}:{self.puerto_principal}"
        self.proxy_activo = False
        self.context = zmq.Context()
        
        # Inicializar todos los sockets
        self.socket_principal = self.context.socket(zmq.REQ)
        self.socket_principal.connect(f"tcp://{self.ip_principal}:{self.puerto_principal}")
        self.socket_respaldo = self.context.socket(zmq.REP)
        self.socket_control = self.context.socket(zmq.REP)
        
        # Referencias a los sockets del proxy para cerrarlos más tarde
        self.proxy_frontend = None
        self.proxy_backend = None
        self.proxy_thread = None
        
        self.salones = [f"S{i}" for i in range(1, 381)]
        self.laboratorios = [f"L{i}" for i in range(1, 61)]
        self.aulas_moviles = [f"AM{i}" for i in range(1, 6)]
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

    def verificar_servidor(self):
        self.socket_principal.setsockopt(zmq.RCVTIMEO, 1000)  # Timeout de 1 segundo para recibir
        try:
            self.logger.info("Enviando ping al servidor principal")
            self.socket_principal.send_json({"comando": "ping"})
            respuesta = self.socket_principal.recv_json()
            self.logger.info("Servidor principal activo")
            self.fallos_consecutivos = 0
            return True
        except zmq.error.Again:
            self.logger.warning("Timeout: No se recibió respuesta del servidor principal")
            self.fallos_consecutivos += 1
            self.reiniciar_socket()  # Reinicia el socket para el próximo intento
            return False
        except zmq.ZMQError as e:
            if e.errno == zmq.EFSM:
                self.logger.error("Error de estado en el socket: reiniciando socket")
                self.reiniciar_socket()
            else:
                self.logger.error(f"Error en verificar_servidor: {e}")
            self.fallos_consecutivos += 1
            return False

    def trabajador(self, worker_url):
        """Función que ejecuta cada trabajador para el respaldo"""
        socket = self.context.socket(zmq.REP)
        socket.connect(worker_url)
        self.logger.info(f"Trabajador de respaldo conectado a {worker_url}")
        while True:
            try:
                mensaje = socket.recv_json()
                respuesta = self.procesar_solicitud(mensaje)
                socket.send_json(respuesta)
            except Exception as e:
                self.logger.error(f"Error en trabajador de respaldo: {e}")

    def cerrar_proxy(self):
        """Cierra los sockets del proxy si están activos."""
        if self.proxy_frontend:
            try:
                self.proxy_frontend.close(linger=0)
            except Exception as e:
                self.logger.error(f"Error cerrando proxy frontend: {e}")
            self.proxy_frontend = None
        if self.proxy_backend:
            try:
                self.proxy_backend.close(linger=0)
            except Exception as e:
                self.logger.error(f"Error cerrando proxy backend: {e}")
            self.proxy_backend = None
        self.proxy_activo = False
        self.logger.info("Proxy cerrado correctamente")
        time.sleep(1)  # Retardo para liberar el puerto

    def proxy(self):
        if self.proxy_activo:
            self.logger.warning("Proxy ya está activo, cerrando el anterior antes de iniciar uno nuevo")
            self.cerrar_proxy()
        
        try:
            self.proxy_frontend = self.context.socket(zmq.ROUTER)
            self.proxy_frontend.setsockopt(zmq.LINGER, 0)
            self.proxy_frontend.bind(f"tcp://*:{self.puerto_proxy}")
            self.proxy_backend = self.context.socket(zmq.DEALER)
            self.proxy_backend.setsockopt(zmq.LINGER, 0)
            self.proxy_backend.bind("inproc://respaldo_workers")
            self.logger.info(f"Proxy de respaldo iniciado en puerto {self.puerto_proxy}, redirigiendo a trabajadores")
            self.proxy_activo = True
            for i in range(3):
                threading.Thread(target=self.trabajador, args=("inproc://respaldo_workers",), daemon=True).start()
            zmq.proxy(self.proxy_frontend, self.proxy_backend)
        except zmq.ZMQError as e:
            self.logger.error(f"Error al iniciar proxy: {e}")
            if e.errno == zmq.EADDRINUSE:
                self.logger.error(f"El puerto {self.puerto_proxy} ya está en uso. Cambia el puerto o libera el actual.")
        except Exception as e:
            self.logger.error(f"Error inesperado en proxy: {e}")
        finally:
            self.cerrar_proxy()

    def procesar_solicitud_hilo(self, mensaje):
        respuesta = self.procesar_solicitud(mensaje)
        self.socket_respaldo.send_json(respuesta)

    def iniciar_respaldo(self):
        if self.estado != "activo":
            self.logger.warning("Intento de iniciar respaldo en estado no activo")
            return
        self.logger.info("Servidor de respaldo activo, usando proxy en puerto 5558")

    def verificar_periodicamente(self):
        while self.estado == "pasivo":
            if not self.verificar_servidor():
                if self.fallos_consecutivos >= self.max_fallos:
                    self.logger.warning("Servidor principal no responde, activando modo respaldo")
                    self.estado = "activo"
                    self.servidor_activo = f"tcp://{self.ip_principal}:5558"
                    self.cerrar_proxy()
                    time.sleep(1)
                    proxy_thread = threading.Thread(target=self.proxy)
                    proxy_thread.daemon = True
                    proxy_thread.start()
                    self.proxy_thread = proxy_thread
                    break
            time.sleep(2)

    def iniciar_control(self):
        try:
            self.socket_control.bind(f"tcp://*:{self.puerto_control}")
            self.logger.info(f"Control de respaldo iniciado en puerto {self.puerto_control}")
            while self.estado == "pasivo":
                mensaje = self.socket_control.recv_json()
                if mensaje.get("comando") == "activar":
                    self.estado = "activo"
                    self.socket_control.send_json({"estado": "activado"})
                    self.iniciar_respaldo()
                    break
        except zmq.error.Again:
            pass
        except Exception as e:
            self.logger.error(f"Error en puerto de control: {e}")
        finally:
            self.socket_control.close()

    def iniciar(self):
        threading.Thread(target=self.iniciar_control, daemon=True).start()
        threading.Thread(target=self.verificar_periodicamente, daemon=True).start()
        proxy_thread = threading.Thread(target=self.proxy)
        proxy_thread.daemon = True
        proxy_thread.start()
        self.proxy_thread = proxy_thread
        self.proxy_activo = True
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Deteniendo servidor de respaldo...")
            self.cerrar_proxy()
            self.socket_principal.close()
            self.socket_respaldo.close()
            self.socket_control.close()
            self.context.term()

    def reiniciar_socket(self):
        """Reinicia el socket REQ para el servidor principal."""
        self.socket_principal.close()
        self.socket_principal = self.context.socket(zmq.REQ)
        self.socket_principal.connect(f"tcp://{self.ip_principal}:{self.puerto_principal}")
        self.logger.info("Socket REQ reiniciado para el servidor principal")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6:
        print("Uso: python3 servidor_respaldo.py <ip_principal> <puerto_principal> <puerto_respaldo> <puerto_control> <puerto_proxy>")
        sys.exit(1)
    checker = RespaldoHealthChecker(
        ip_principal=sys.argv[1],
        puerto_principal=int(sys.argv[2]),
        puerto_respaldo=int(sys.argv[3]),
        puerto_control=int(sys.argv[4]),
        puerto_proxy=int(sys.argv[5])
    )
    checker.iniciar()