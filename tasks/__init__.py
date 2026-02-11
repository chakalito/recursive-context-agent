"""
Módulo de tareas para el agente recursivo de contexto.

Proporciona definiciones de tareas y utilidades para extracción de datos.
"""
import json
import logging
from pathlib import Path
from typing import Any

from tasks.data_extractor import extract_structured_data_from_history

logger = logging.getLogger(__name__)

__all__ = ["extract_structured_data_from_history", "get_default_tasks"]


def get_default_tasks() -> list[dict[str, Any]]:
    """Carga las tareas desde tasks.json.

    Lee el archivo tasks/tasks.json y extrae la clave 'tasks'.

    Returns:
        Lista de diccionarios con 'name', 'description' y opcional 'signal_type' por tarea.

    Raises:
        FileNotFoundError: Si tasks.json no existe.
        json.JSONDecodeError: Si el JSON está mal formado.
    """
    # Obtener ruta del archivo relativa al módulo
    tasks_file = Path(__file__).parent / "tasks.json"
    
    try:
        with open(tasks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            tasks = data.get('tasks', [])
            logger.info(f"Cargadas {len(tasks)} tareas desde tasks.json")
            return tasks
    except FileNotFoundError:
        logger.error(f"Archivo tasks.json no encontrado en {tasks_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando tasks.json: {e}")
        raise
