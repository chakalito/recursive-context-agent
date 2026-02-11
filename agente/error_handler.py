"""
Manejo centralizado de errores del agente recursivo de contexto.

Proporciona funciones para clasificar y manejar diferentes tipos de errores
de manera consistente en todo el sistema.
"""
import logging
from typing import Callable, Optional

from agente.config import SUPPRESS_EXPECTED_CDP_ERRORS

logger = logging.getLogger(__name__)

# Patrones de error esperados
_CDP_ERROR_PATTERNS = [
    "frame with the given frameid is not found",
    "cdp",
    "frameid",
    "cdp requests failed",
    "ax_tree",
]

_BROWSER_ERROR_PATTERNS = [
    "no valid agent focus available",
    "failed to open new tab - no browser is open",
    "browser is in an unstable state",
]


def _check_error_patterns(error: Exception, patterns: list[str]) -> bool:
    """Verifica si un error coincide con alguno de los patrones dados.

    Args:
        error: Excepción a evaluar.
        patterns: Lista de subcadenas a buscar en str(error).lower().

    Returns:
        True si alguna subcadena está presente en el mensaje del error.
    """
    error_str = str(error).lower()
    return any(pattern in error_str for pattern in patterns)


def is_cdp_error(error: Exception) -> bool:
    """Verifica si un error es un error esperado de CDP (Chrome DevTools Protocol).

    Args:
        error: Excepción a evaluar.

    Returns:
        True si el error coincide con patrones CDP conocidos.
    """
    return _check_error_patterns(error, _CDP_ERROR_PATTERNS)


def is_browser_error(error: Exception) -> bool:
    """Verifica si un error está relacionado con el estado del navegador.

    Args:
        error: Excepción a evaluar.

    Returns:
        True si el error coincide con patrones de estado del browser.
    """
    return _check_error_patterns(error, _BROWSER_ERROR_PATTERNS)


def is_expected_error(error: Exception) -> bool:
    """Verifica si un error es esperado y puede ser suprimido.

    Args:
        error: Excepción a evaluar.

    Returns:
        True si es CDP o browser error (suprimible).
    """
    return is_cdp_error(error) or is_browser_error(error)


def _handle_expected_error(
    error: Exception,
    context_msg: str,
    suppress: bool,
) -> None:
    """Maneja errores esperados de manera consistente.

    Integridad-tecnica: el fallo debe ser visible (logger.error) para debug.
    Con suppress=True solo se omite exc_info para errores esperados.

    Args:
        error: Excepción ocurrida.
        context_msg: Descripción del contexto donde ocurrió.
        suppress: Si True, omitir exc_info para errores esperados.
    """
    error_str = str(error)
    is_expected = is_expected_error(error)
    # Siempre logger.error para visibilidad; exc_info solo si no es esperado o no suppress
    use_exc_info = not (is_expected and suppress)
    logger.error(f"Error {context_msg}: {error_str}", exc_info=use_exc_info)


def handle_context_update_error(
    error: Exception,
    domain: str,
    operation: str,
    suppress: Optional[bool] = None,
) -> None:
    """Maneja errores durante la actualización recursiva de contexto.

    Args:
        error: Excepción ocurrida.
        domain: Dominio donde falló la actualización.
        operation: Operación que falló (ej: 'salir', 'refresh').
        suppress: Si None, usa SUPPRESS_EXPECTED_CDP_ERRORS.
    """
    suppress = suppress if suppress is not None else SUPPRESS_EXPECTED_CDP_ERRORS
    context_msg = f"actualizando contexto ({operation}) en dominio {domain}"
    _handle_expected_error(error, context_msg, suppress)


def handle_step_callback_error(
    error: Exception,
    suppress: Optional[bool] = None,
) -> None:
    """Maneja errores en el callback de paso del agente.

    Args:
        error: Excepción ocurrida.
        suppress: Si None, usa SUPPRESS_EXPECTED_CDP_ERRORS.
    """
    suppress = suppress if suppress is not None else SUPPRESS_EXPECTED_CDP_ERRORS
    _handle_expected_error(error, "en callback de paso", suppress)


def handle_task_error(
    error: Exception,
    task_context: str = "",
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """Maneja errores durante la ejecución de tareas.

    Registra el error y notifica al callback con el mensaje real.
    No silencia ni sustituye errores; el fallo se propaga para depuración.

    Args:
        error: Excepción ocurrida.
        task_context: Descripción de la tarea (para logging).
        on_error: Callback opcional al que se pasa el mensaje de error (truncado a 100 chars).
    """
    error_msg = str(error)
    logger.error(f"Error procesando tarea {task_context}: {error_msg}", exc_info=True)
    if on_error:
        on_error(error_msg[:100] if len(error_msg) > 100 else error_msg)
