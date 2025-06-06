import subprocess
import time
import sys
import os
import signal

def iniciar_servidor():
    print("Iniciando servidor...")
    return subprocess.Popen(["python", "servidor.py"])

def enviar_solicitud(self, solicitud):
    inicio = time.time()
    try:
        self.socket_servidor.send_json(solicitud)
        respuesta = self.socket_servidor.recv_json()
        fin = time.time()
        tiempo_respuesta = fin - inicio
        self.fallos_consecutivos = 0  # Reiniciar contador de fallos
        self.confirmar_recepcion(respuesta)
        exito = respuesta.get('asignacion', {}).get('no_asignados') is None
        with open("metricas_facultad.txt", "a") as f:
            f.write(f"{solicitud['programa']},{tiempo_respuesta},{exito}\n")
    except zmq.Again:
        self.logger.warning("Timeout al esperar respuesta del servidor")
        self.fallos_consecutivos += 1
        self.conectar_servidor()  # Reinicia el socket
        if self.fallos_consecutivos >= self.max_fallos and self.servidor_activo.endswith(f":{self.servidor_puerto}"):
            self.logger.warning("Cambiando al servidor de respaldo")
            self.servidor_activo = f"tcp://{self.servidor_ip}:5558"  # Cambiar a puerto 5558
            self.conectar_servidor()
            self.fallos_consecutivos = 0
    except zmq.ZMQError as e:
        self.logger.error(f"Error enviando solicitud: {e}")
        self.fallos_consecutivos += 1
        self.conectar_servidor()  # Reinicia el socket
        if self.fallos_consecutivos >= self.max_fallos and self.servidor_activo.endswith(f":{self.servidor_puerto}"):
            self.logger.warning("Cambiando al servidor de respaldo")
            self.servidor_activo = f"tcp://{self.servidor_ip}:5558"  # Cambiar a puerto 5558
            self.conectar_servidor()
            self.fallos_consecutivos = 0