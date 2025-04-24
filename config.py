import logging

# Configuración de logging
LOG_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

# Configuración de persistencia
PERSISTENCE_CONFIG = {
    'solicitudes_file': 'solicitudes.json',
    'no_atendidas_file': 'solicitudes_no_atendidas.json'
}

# Tiempos de espera
TIMEOUTS = {
    'confirmacion': 5000,  # 5 segundos
    'reintento': 3000     # 3 segundos
}