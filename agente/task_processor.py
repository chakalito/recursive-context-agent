"""
Procesamiento de tareas para el agente recursivo de contexto.

Proporciona funciones para preparar y ejecutar tareas. El contexto de dominio
se obtiene exclusivamente vía la herramienta get_domain_context, invocada por
decisión del agente (no por inyección desde código).

NOTA: Verificación de documentación oficial browser-use 0.11.9:
- Agent acepta timeouts: max_failures, step_timeout, llm_timeout (verificado en agent/service.py)
- Browser no acepta timeouts directamente - se configuran en Agent
- Parámetros verificados según código fuente instalado en venv/Lib/site-packages/browser_use/agent/service.py
"""
import asyncio
import logging
from typing import Any, Callable

from browser_use import Agent, Browser
from browser_use.agent.views import MessageCompactionSettings

from agente.config import (
    CALCULATE_COST,
    CONVERSATIONS_DIR_NAME,
    DIRECTLY_OPEN_URL,
    FLASH_MODE,
    INCLUDE_ATTRIBUTES,
    LLM_TIMEOUT,
    LOOP_DETECTION_ENABLED,
    LOOP_DETECTION_WINDOW,
    MAX_ACTIONS_PER_STEP,
    MAX_FAILURES,
    MAX_HISTORY_ITEMS,
    MAX_STEPS,
    MESSAGE_COMPACTION_COMPACT_EVERY_N_STEPS,
    MESSAGE_COMPACTION_ENABLED,
    MESSAGE_COMPACTION_KEEP_LAST_ITEMS,
    MESSAGE_COMPACTION_SUMMARY_MAX_CHARS,
    MESSAGE_COMPACTION_TRIGGER_CHAR_COUNT,
    STEP_TIMEOUT,
    THINKING_BUDGET_TOKENS,
    USE_VISION,
    VISION_DETAIL_LEVEL,
    trace_log,
)
from agente.history_manager import get_history_final_result

logger = logging.getLogger(__name__)


def _create_new_agent(
    task_text: str,
    system_prompt: str,
    context_for_system: str,
    llm: Any,
    browser: Browser,
    tools_controller: Any,
    step_callback: Callable,
    cancel_check_callback: Callable,
    page_extraction_llm: Any,
) -> Agent:
    """Crea una nueva instancia de Agent con la configuración adecuada.

    Args:
        task_text: Texto de la tarea.
        system_prompt: Prompt del sistema.
        context_for_system: Contexto de dominio para extender el prompt.
        llm: Modelo LLM principal.
        browser: Instancia del navegador.
        tools_controller: Controller con herramientas (DomainContextController).
        step_callback: Callback invocado en cada paso.
        cancel_check_callback: Callback que retorna True si debe cancelar.
        page_extraction_llm: LLM para extracción de página.

    Returns:
        Instancia de Agent configurada con timeouts y message_compaction.
    """
    extended_system_message = system_prompt
    if context_for_system:
        extended_system_message = (
            f"{system_prompt}\n\n{context_for_system}" if system_prompt
            else context_for_system
        )
    trace_log(
        logger,
        "_create_new_agent context_for_system_len=%d extend_system_message_len=%d",
        len(context_for_system),
        len(extended_system_message),
    )
    agent_kwargs: dict[str, Any] = {
        "task": task_text,
        "llm": llm,
        "browser": browser,
        "save_conversation_path": CONVERSATIONS_DIR_NAME,
        "extend_system_message": extended_system_message,
        "register_new_step_callback": step_callback,
        "register_should_stop_callback": cancel_check_callback,
        "use_vision": USE_VISION,
        "vision_detail_level": VISION_DETAIL_LEVEL,
        "use_thinking": THINKING_BUDGET_TOKENS > 0,
        "controller": tools_controller,
        "max_history_items": MAX_HISTORY_ITEMS,
        "max_actions_per_step": MAX_ACTIONS_PER_STEP,
        "max_failures": MAX_FAILURES,
        "step_timeout": STEP_TIMEOUT,
        "page_extraction_llm": page_extraction_llm,
        "flash_mode": FLASH_MODE,
        "calculate_cost": CALCULATE_COST,
        "directly_open_url": DIRECTLY_OPEN_URL,
        "loop_detection_enabled": LOOP_DETECTION_ENABLED,
        "loop_detection_window": LOOP_DETECTION_WINDOW,
    }
    if LLM_TIMEOUT is not None:
        agent_kwargs["llm_timeout"] = LLM_TIMEOUT
    if INCLUDE_ATTRIBUTES is not None:
        agent_kwargs["include_attributes"] = INCLUDE_ATTRIBUTES
    if MESSAGE_COMPACTION_ENABLED:
        agent_kwargs["message_compaction"] = MessageCompactionSettings(
            enabled=True,
            compact_every_n_steps=MESSAGE_COMPACTION_COMPACT_EVERY_N_STEPS,
            trigger_char_count=MESSAGE_COMPACTION_TRIGGER_CHAR_COUNT,
            keep_last_items=MESSAGE_COMPACTION_KEEP_LAST_ITEMS,
            summary_max_chars=MESSAGE_COMPACTION_SUMMARY_MAX_CHARS,
        )
    else:
        agent_kwargs["message_compaction"] = MessageCompactionSettings(enabled=False)

    return Agent(**agent_kwargs)


def _get_partial_history(
    agent: Any,
    set_last_history_callback: Callable[[Any], None],
    context_msg: str,
) -> None:
    """Intenta obtener y guardar historial parcial del agente.
    
    Args:
        agent: Instancia del agente (puede ser None).
        set_last_history_callback: Callback para guardar el historial.
        context_msg: Mensaje de contexto para logging (ej: "cancelación", "interrupción", "error").
    """
    if agent and hasattr(agent, 'get_history'):
        try:
            history = agent.get_history()
            if history:
                set_last_history_callback(history)
                logger.info(f"Historial parcial obtenido después de {context_msg}")
        except Exception as e:
            logger.warning("No se pudo obtener historial parcial: %s", e, exc_info=True)


async def execute_task(
    task_text: str,
    browser: Browser,
    llm: Any,
    page_extraction_llm: Any,
    system_prompt: str,
    tools_controller: Any,
    agent_ref: Any,  # Referencia mutable al agente (para actualizar)
    step_callback: Callable[[Any, Any, int], None],
    cancel_check_callback: Callable[[], bool],
    set_last_history_callback: Callable[[Any], None],
) -> str:
    """Ejecuta una tarea con el agente.
    
    Args:
        task_text: Texto de la tarea a ejecutar.
        browser: Instancia del navegador.
        llm: Instancia del LLM principal.
        page_extraction_llm: Instancia del LLM para extracción de página.
        system_prompt: Prompt del sistema.
        tools_controller: Controlador de herramientas.
        agent_ref: Referencia mutable al agente (se actualiza si se crea uno nuevo).
        step_callback: Callback para cada paso del agente.
        cancel_check_callback: Callback para verificar si se debe cancelar.
        set_last_history_callback: Callback para guardar el historial.
    
    Returns:
        String con el resultado final de la tarea.
    """
    trace_log(logger, "execute_task START task=%s", task_text[:80] + "..." if len(task_text) > 80 else task_text)
    context_for_system = ""
    
    # Crear o actualizar agente
    agent = agent_ref[0] if isinstance(agent_ref, list) else agent_ref
    if not agent:
        agent = _create_new_agent(
            task_text, system_prompt, context_for_system,
            llm, browser, tools_controller, step_callback,
            cancel_check_callback, page_extraction_llm
        )
        if isinstance(agent_ref, list):
            agent_ref[0] = agent
    else:
        trace_log(logger, "add_new_task (agente existente)")
        logger.info("Añadiendo nueva tarea al contexto existente")
        agent.add_new_task(task_text)

    history = None
    try:
        trace_log(logger, "agent.run START max_steps=%d", MAX_STEPS)
        history = await agent.run(max_steps=MAX_STEPS)
        trace_log(logger, "agent.run END")
        set_last_history_callback(history)
        logger.info("Tarea ejecutada exitosamente")
    except asyncio.CancelledError:
        logger.warning("Tarea cancelada durante ejecución")
        _get_partial_history(agent, set_last_history_callback, "cancelación")
        raise
    except InterruptedError:
        logger.warning("Tarea interrumpida durante ejecución")
        _get_partial_history(agent, set_last_history_callback, "interrupción")
        # No re-raise InterruptedError, es esperado cuando se cancela
    except Exception as e:
        logger.error(f"Error durante ejecución de tarea: {e}", exc_info=True)
        _get_partial_history(agent, set_last_history_callback, "error")
        raise

    return get_history_final_result(history)
