import zmq
import time
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class HealthChecker:
    def __init__(self, ip_principal="", puerto_principal=5555, 
    ip_respaldo="", puerto_respaldo=5556, 
    puerto_control_respaldo=5557, puerto_proxy=5558):
        self.logger = logging.getLogger('HealthChecker')
        self.ip_principal = ip_principal
        self.puerto_principal = puerto_principal
        self.ip_respaldo = ip_respaldo
        self.puerto_respaldo = puerto_respaldo
        self.puerto_control_respaldo = puerto_control_respaldo
        self.puerto_proxy = puerto_proxy
        self.context = zmq.Context()
        self.socket_principal = self.context.socket(zmq.REQ)
        self.socket_respaldo = self.context.socket(zmq.REQ)
        self.fallos_consecutivos = 0
        self.max_fallos = 3
        self.servidor_activo = f"tcp://{self.ip_principal}:{self.puerto_principal}"
        self.proxy_activo = False

    def verificar_servidor(self):
        self.socket_principal.setsockopt(zmq.RCVTIMEO, 1000)
        self.socket_principal.connect(f"tcp://{self.ip_principal}:{self.puerto_principal}")
        try:
            self.socket_principal.send_json({"comando": "ping"})
            respuesta = self.socket_principal.recv_json()
            self.logger.info("Servidor principal activo")
            self.fallos_consecutivos = 0
            return True
        except zmq.error.Again:
            self.fallos_consecutivos += 1
            self.logger.warning(f"Fallo detectado en servidor principal ({self.fallos_consecutivos}/{self.max_fallos})")
            return False
        finally:
            self.socket_principal.disconnect(f"tcp://{self.ip_principal}:{self.puerto_principal}")

    def activar_respaldo(self):
        self.socket_respaldo.setsockopt(zmq.RCVTIMEO, 1000)
        self.socket_respaldo.connect(f"tcp://{self.ip_respaldo}:{self.puerto_control_respaldo}")
        try:
            self.socket_respaldo.send_json({"comando": "activar"})
            respuesta = self.socket_respaldo.recv_json()
            self.logger.info(f"Respuesta del respaldo: {respuesta}")
            if respuesta.get("estado") == "activado":
                self.servidor_activo = f"tcp://{self.ip_respaldo}:{self.puerto_respaldo}"
                self.logger.info("Servidor de respaldo activado exitosamente")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error al activar respaldo: {e}")
            return False
        finally:
            self.socket_respaldo.disconnect(f"tcp://{self.ip_respaldo}:{self.puerto_control_respaldo}")

    def proxy(self):
        frontend = self.context.socket(zmq.ROUTER)
        backend = self.context.socket(zmq.DEALER)
        frontend.bind(f"tcp://*:{self.puerto_proxy}")
        backend.connect(self.servidor_activo)
        self.logger.info(f"Proxy iniciado en puerto {self.puerto_proxy}, redirigiendo a {self.servidor_activo}")
        zmq.proxy(frontend, backend)

    def iniciar(self):
        # Iniciar proxy en un hilo separado
        proxy_thread = threading.Thread(target=self.proxy)
        proxy_thread.daemon = True
        proxy_thread.start()
        self.proxy_activo = True

        while True:
            if not self.verificar_servidor():
                if self.fallos_consecutivos >= self.max_fallos:
                    self.logger.warning("Servidor principal no responde, activando respaldo")
                    if self.activar_respaldo():
                        self.logger.info("Respaldo activo, actualizando proxy")
                        # Actualizar el backend del proxy requiere reiniciarlo
                        self.proxy_activo = False
                        time.sleep(1)  # Esperar a que el proxy anterior termine
                        proxy_thread = threading.Thread(target=self.proxy)
                        proxy_thread.daemon = True
                        proxy_thread.start()
                        self.proxy_activo = True
                        break
            time.sleep(2)

if __name__ == "__main__":
    checker = HealthChecker(
        ip_principal="", puerto_principal=5555,
        ip_respaldo="", puerto_respaldo=5556,
        puerto_control_respaldo=5557, puerto_proxy=5558
    )
    checker.iniciar()