"""
Gestión del historial de ejecución del agente recursivo de contexto.

Proporciona funciones para guardar y recuperar el historial de tareas ejecutadas.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from agente.config import (
    CALCULATE_COST,
    FINAL_HISTORY_FILE_NAME,
    HISTORY_FILE_NAME,
    LOGS_DIR_NAME,
    USAGE_FILE_NAME,
)
from utils.path_helpers import get_project_path

logger = logging.getLogger(__name__)
LOGS_DIR = get_project_path(LOGS_DIR_NAME)


def _extract_history_dict(history: Any) -> dict[str, Any]:
    """Extrae los datos del historial en formato diccionario.

    Maneja diferentes estructuras de objetos de historial de manera robusta.
    Recuperación intencional: ante errores de acceso a atributos (p. ej. si la API
    del historial cambia), retorna dict vacío para permitir guardar lo posible.

    Args:
        history: Objeto de historial (model_dump, usage, etc.).

    Returns:
        Diccionario con los datos extraídos, o {} si falla.
    """
    if not history:
        return {}

    try:
        # Intentar obtener datos mediante model_dump si está disponible
        data = history.model_dump() if hasattr(history, "model_dump") else {}

        if not isinstance(data, dict):
            return {}

        # Extraer información de uso si está disponible
        usage = getattr(history, "usage", None)
        if usage:
            if hasattr(usage, "model_dump"):
                data["usage"] = usage.model_dump()
            elif hasattr(usage, "__dict__"):
                data["usage"] = usage.__dict__

        return data
    except (AttributeError, TypeError, KeyError) as e:
        logger.warning("Error extrayendo datos del historial (recuperación controlada): %s", e)
        return {}


def save_history(history: Any) -> None:
    """Guarda el historial de ejecución en disco.

    Escribe history.json (save_to_file), final_history.json (dump) y usage.json si aplica.

    Args:
        history: Objeto de historial del agente (debe tener save_to_file y model_dump).
    """
    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
    history_path = os.path.join(LOGS_DIR, HISTORY_FILE_NAME)
    history.save_to_file(history_path)

    data = _extract_history_dict(history)
    final_history_path = os.path.join(LOGS_DIR, FINAL_HISTORY_FILE_NAME)
    with open(final_history_path, "w", encoding="utf-8") as f:
        json.dump(data if data else {"history_dump": str(history)}, f, ensure_ascii=False, indent=2)

    if CALCULATE_COST and data.get("usage"):
        usage_path = os.path.join(LOGS_DIR, USAGE_FILE_NAME)
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump(data["usage"], f, ensure_ascii=False, indent=2)


def get_history_final_result(history: Any) -> str:
    """Obtiene el resultado final del historial.

    Args:
        history: Objeto de historial del agente.

    Returns:
        String con el resultado final o mensaje por defecto si no hay historial.

    Recuperación intencional: ante errores de acceso (p. ej. atributos faltantes),
    retorna mensaje por defecto para no interrumpir el flujo de la tarea.
    """
    if history and hasattr(history, "final_result"):
        try:
            return history.final_result()
        except (AttributeError, TypeError, KeyError) as e:
            logger.warning("Error obteniendo resultado final (recuperación controlada): %s", e)

    logger.warning("No hay historial disponible para retornar resultado final")
    return "Tarea completada pero no hay historial disponible"
