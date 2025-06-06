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
        self.socket_servidor = None
        self.socket_pub = self.context_servidor.socket(zmq.PUB)
        self.socket_pub.bind(f"tcp://*:{self.puerto_escucha}")
        
        # Control del servidor activo
        self.servidor_activo = f"tcp://{self.servidor_ip}:{self.servidor_puerto}"
        self.usando_respaldo = False
        self.fallos_consecutivos = 0
        self.max_fallos = 3
        
        # Flag para controlar el ciclo de ejecución
        self.ejecutando = True
        
        # Lock para thread safety
        self.lock = threading.Lock()
    
    def conectar_servidor(self):
        """Conecta o reconecta al servidor activo."""
        try:
            if self.socket_servidor:
                self.socket_servidor.close()
            
            self.socket_servidor = self.context_servidor.socket(zmq.REQ)
            self.socket_servidor.setsockopt(zmq.RCVTIMEO, TIMEOUTS['confirmacion'])
            self.socket_servidor.setsockopt(zmq.SNDTIMEO, TIMEOUTS['confirmacion'])
            self.socket_servidor.setsockopt(zmq.LINGER, 0)
            self.socket_servidor.connect(self.servidor_activo)
            self.logger.info(f"Conectado al servidor {self.servidor_activo}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando al servidor {self.servidor_activo}: {e}")
            return False

    def probar_conexion_servidor(self):
        """Prueba la conexión con el servidor actual enviando un ping."""
        try:
            test_socket = self.context_servidor.socket(zmq.REQ)
            test_socket.setsockopt(zmq.RCVTIMEO, 2000)  # 2 segundos timeout
            test_socket.setsockopt(zmq.SNDTIMEO, 2000)
            test_socket.setsockopt(zmq.LINGER, 0)
            test_socket.connect(self.servidor_activo)
            
            test_socket.send_json({"comando": "ping"})
            respuesta = test_socket.recv_json()
            test_socket.close()
            
            return respuesta.get("estado") == "activo"
        except Exception as e:
            self.logger.warning(f"Prueba de conexión falló: {e}")
            if 'test_socket' in locals():
                test_socket.close()
            return False

    def cambiar_a_respaldo(self):
        """Cambia la conexión al servidor de respaldo."""
        with self.lock:
            if not self.usando_respaldo:
                self.logger.warning("Servidor principal no disponible, cambiando a respaldo...")
                self.servidor_activo = f"tcp://{self.respaldo_ip}:{self.puerto_respaldo}"
                self.usando_respaldo = True
                self.fallos_consecutivos = 0
                
                if self.conectar_servidor():
                    self.logger.info("Conectado exitosamente al servidor de respaldo")
                    return True
                else:
                    self.logger.error("Error conectando al servidor de respaldo")
                    return False
            return True

    def volver_a_principal(self):
        """Intenta volver al servidor principal."""
        with self.lock:
            if self.usando_respaldo:
                servidor_temp = f"tcp://{self.servidor_ip}:{self.servidor_puerto}"
                
                # Probar conexión al servidor principal
                try:
                    test_socket = self.context_servidor.socket(zmq.REQ)
                    test_socket.setsockopt(zmq.RCVTIMEO, 2000)
                    test_socket.setsockopt(zmq.SNDTIMEO, 2000)
                    test_socket.setsockopt(zmq.LINGER, 0)
                    test_socket.connect(servidor_temp)
                    
                    test_socket.send_json({"comando": "ping"})
                    respuesta = test_socket.recv_json()
                    test_socket.close()
                    
                    if respuesta.get("estado") == "activo":
                        self.logger.info("Servidor principal disponible, volviendo...")
                        self.servidor_activo = servidor_temp
                        self.usando_respaldo = False
                        self.fallos_consecutivos = 0
                        self.conectar_servidor()
                        return True
                        
                except Exception as e:
                    self.logger.debug(f"Servidor principal aún no disponible: {e}")
                    if 'test_socket' in locals():
                        test_socket.close()
            
            return False

    def iniciar(self):
        """Inicia la facultad y se conecta con el servidor"""
        if not self.conectar_servidor():
            self.logger.error("No se pudo conectar al servidor inicial")
            return
            
        self.logger.info(f"Facultad {self.nombre} iniciada. Puerto de escucha: {self.puerto_escucha}")
        
        # Iniciar hilo para simular solicitudes
        threading.Thread(target=self.simular_solicitudes, daemon=True).start()
        
        # Iniciar hilo para verificar reconexión al servidor principal
        threading.Thread(target=self.verificar_reconexion, daemon=True).start()
        
        try:
            while self.ejecutando:
                time.sleep(1)
        except KeyboardInterrupt:
            self.ejecutando = False
            self.logger.info(f"Facultad {self.nombre} detenida")
        finally:
            if self.socket_servidor:
                self.socket_servidor.close()
            self.socket_pub.close()
            self.context_servidor.term()
    
    def verificar_reconexion(self):
        """Verifica periódicamente si se puede volver al servidor principal."""
        while self.ejecutando:
            time.sleep(10)  # Verificar cada 10 segundos
            if self.usando_respaldo:
                self.volver_a_principal()
    
    def simular_solicitudes(self):
        programas = [
            "Ingeniería de Sistemas", "Ingeniería Civil", "Medicina", "Derecho", "Biología"
        ]
        while self.ejecutando:
            time.sleep(random.uniform(3, 10))
            if not self.ejecutando:
                break
                
            programa = random.choice(programas)
            num_salones = random.randint(3, 8)
            num_laboratorios = random.randint(2, 4)
            
            # Asegurar que la suma esté en el rango deseado
            while num_salones + num_laboratorios < 7 or num_salones + num_laboratorios > 10:
                num_salones = random.randint(3, 8)
                num_laboratorios = random.randint(2, 4)
            
            solicitud = {
                'facultad': self.nombre,
                'programa': programa,
                'num_salones': num_salones,
                'num_laboratorios': num_laboratorios,
                'num_aulas_moviles': 0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.programas_solicitudes[programa] = solicitud
            
            # Notificar al programa correspondiente
            try:
                self.socket_pub.send_string(f"programa_{programa} {json.dumps(solicitud)}")
                self.logger.debug(f"Notificación enviada a programa {programa}")
            except Exception as e:
                self.logger.error(f"Error enviando notificación a programa {programa}: {e}")
            
            # Enviar solicitud al servidor
            self.enviar_solicitud_servidor(solicitud)
    
    def enviar_solicitud_servidor(self, solicitud):
        """Envía solicitud al servidor con manejo de failover mejorado."""
        max_intentos = 3
        intento = 0
        
        while intento < max_intentos and self.ejecutando:
            inicio = time.time()
            intento += 1
            
            try:
                self.logger.info(f"Enviando solicitud (intento {intento}): {solicitud['programa']}")
                self.socket_servidor.send_json(solicitud)
                respuesta = self.socket_servidor.recv_json()
                
                fin = time.time()
                tiempo_respuesta = fin - inicio
                
                # Resetear contador de fallos si la solicitud fue exitosa
                self.fallos_consecutivos = 0
                
                # Procesar respuesta
                self.confirmar_recepcion(respuesta)
                exito = respuesta.get('asignacion', {}).get('no_asignados') is None
                
                # Guardar métricas
                try:
                    with open("metricas_facultad.txt", "a") as f:
                        servidor_tipo = "respaldo" if self.usando_respaldo else "principal"
                        f.write(f"{solicitud['programa']},{tiempo_respuesta},{exito},{servidor_tipo},{intento}\n")
                except Exception as e:
                    self.logger.error(f"Error guardando métricas: {e}")
                
                self.logger.info(f"Solicitud procesada exitosamente para {solicitud['programa']}")
                return respuesta
                
            except zmq.Again:
                self.logger.warning(f"Timeout en intento {intento} - servidor no responde")
                self.manejar_error_conexion()
                
            except zmq.ZMQError as e:
                self.logger.error(f"Error ZMQ en intento {intento}: {e}")
                self.manejar_error_conexion()
                
            except Exception as e:
                self.logger.error(f"Error inesperado en intento {intento}: {e}")
                self.manejar_error_conexion()
            
            # Esperar antes del siguiente intento
            if intento < max_intentos:
                time.sleep(1)
        
        self.logger.error(f"No se pudo procesar la solicitud después de {max_intentos} intentos")
        return None
    
    def manejar_error_conexion(self):
        """Maneja errores de conexión y realiza failover si es necesario."""
        self.fallos_consecutivos += 1
        
        # Intentar reconectar al servidor actual
        if not self.conectar_servidor():
            # Si falla la reconexión y no estamos usando respaldo, cambiar
            if not self.usando_respaldo and self.fallos_consecutivos >= self.max_fallos:
                self.cambiar_a_respaldo()
            elif self.usando_respaldo:
                # Si ya estamos en respaldo y sigue fallando, intentar reconectar
                self.logger.warning("Servidor de respaldo también presenta problemas")
                time.sleep(2)
                self.conectar_servidor()
            
    def guardar_respuesta(self, respuesta, semestre="2025-10"):
        archivo = f"respuestas_{self.nombre}_{semestre}.json"
        try:
            with open(archivo, 'a') as f:
                json.dump(respuesta, f, indent=2)
                f.write('\n')
            self.logger.debug(f"Respuesta guardada en {archivo}")
        except Exception as e:
            self.logger.error(f"Error al guardar respuesta: {e}")

    def confirmar_recepcion(self, respuesta):
        """Procesa y confirma la recepción de una respuesta del servidor."""
        self.logger.info(f"Respuesta recibida del servidor: ID {respuesta.get('id_solicitud')}")
        
        id_solicitud = respuesta.get('id_solicitud')
        if id_solicitud:
            self.respuestas_asignaciones[id_solicitud] = respuesta
            self.guardar_respuesta(respuesta)
            
            asignacion = respuesta.get('asignacion', {})
            programa = respuesta.get('programa', 'Desconocido')
            
            # Log detallado de la asignación
            self.logger.info(f"Recursos asignados a {programa}:")
            salones = asignacion.get('salones', [])
            laboratorios = asignacion.get('laboratorios', [])
            aulas_moviles = asignacion.get('aulas_moviles', [])
            
            self.logger.info(f"  - Salones: {len(salones)} ({', '.join(salones) if salones else 'ninguno'})")
            self.logger.info(f"  - Laboratorios: {len(laboratorios)} ({', '.join(laboratorios) if laboratorios else 'ninguno'})")
            self.logger.info(f"  - Aulas Móviles: {len(aulas_moviles)} ({', '.join(aulas_moviles) if aulas_moviles else 'ninguno'})")
            
            # Advertencias sobre recursos no asignados
            no_asignados = asignacion.get('no_asignados')
            if no_asignados:
                self.logger.warning(f"Recursos no asignados para {programa}: {no_asignados}")
            
            # Estadísticas adicionales
            servidor_tipo = "respaldo" if self.usando_respaldo else "principal"
            self.logger.info(f"Procesado por servidor: {servidor_tipo}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python facultad.py <nombre_facultad> [servidor_ip] [servidor_puerto] [respaldo_ip] [puerto_respaldo]")
        sys.exit(1)
    
    nombre_facultad = sys.argv[1]
    servidor_ip = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    servidor_puerto = int(sys.argv[3]) if len(sys.argv) > 3 else 5555  # CORREGIDO: Conversión a int
    respaldo_ip = sys.argv[4] if len(sys.argv) > 4 else "localhost"
    puerto_respaldo = int(sys.argv[5]) if len(sys.argv) > 5 else 5558  # AGREGADO: Puerto respaldo
    
    facultad = Facultad(nombre_facultad, servidor_ip, servidor_puerto, respaldo_ip, puerto_respaldo)
    facultad.iniciar()