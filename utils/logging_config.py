"""
Configuración centralizada del sistema de logging.

Proporciona setup_logging() para inicializar handlers básicos con rotación.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.path_helpers import get_project_path

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _get_log_level(env_var: str = "LOG_LEVEL", default: str = "INFO") -> int:
    """Obtiene el nivel de logging desde variable de entorno.

    Args:
        env_var: Nombre de la variable de entorno a leer.
        default: Valor por defecto si la variable no existe.

    Returns:
        Constante de nivel de logging (logging.DEBUG, INFO, etc.).
    """
    level_str = os.getenv(env_var, default).upper()
    return _LEVEL_MAP.get(level_str, logging.INFO)


def setup_logging(
    log_level: str | None = None,
    log_dir: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configura el sistema de logging básico con rotación de archivos.
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  Si None, se lee de LOG_LEVEL env var o usa INFO por defecto.
        log_dir: Directorio donde se guardan los logs. Si None, usa logs/ en la raíz del proyecto.
        max_bytes: Tamaño máximo de archivo de log antes de rotar (default: 10MB).
        backup_count: Número de archivos de respaldo a mantener (default: 5).
    """
    try:
        # Determinar nivel de logging
        if log_level is None:
            level = _get_log_level()
        else:
            level = _LEVEL_MAP.get(log_level.upper(), logging.INFO)
        
        # Determinar directorio de logs
        if log_dir is None:
            log_dir = get_project_path("logs")
        else:
            log_dir = os.path.abspath(log_dir)
        
        # Asegurar que el directorio existe
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # Ruta de archivo de log
        app_log_path = os.path.join(log_dir, "app.log")
        
        # Formato estructurado
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        
        # Configurar root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(console_handler)
        
        # Handler para archivo con rotación
        try:
            file_handler = RotatingFileHandler(
                app_log_path,
                mode="a",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            root_logger.addHandler(file_handler)
        except OSError as e:
            logging.warning("No se pudo crear handler para app.log: %s", e)
        
        logger = logging.getLogger(__name__)
        logger.info("Sistema de logging configurado (nivel: %s, directorio: %s)", 
                   logging.getLevelName(level), log_dir)
        
    except Exception as e:
        # Fallback a logging básico si falla la configuración
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s: %(message)s"
        )
        logging.error("Error configurando logging avanzado, usando configuración básica: %s", e)
