"""
Controlador principal del agente recursivo de contexto.

Gestiona el ciclo de vida del agente autónomo de navegación web con sistema
de contexto recursivo por dominio.

Flujo mono-hilo: usa asyncio exclusivamente, sin threading ni multiprocessing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from browser_use import Agent, Browser
from browser_use.agent.views import AgentOutput
from browser_use.browser.views import BrowserStateSummary
from browser_use.controller import Controller
from langchain_core.language_models.chat_models import BaseChatModel

from agente.browser_manager import close_browser_async, ensure_browser_ready, init_browser_async
from agente.config import (
    BROWSER_PROFILE_DIR,
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_WARNING,
    MAX_RESET_WAIT_TIME,
    MSG_CANCELLED,
    MSG_CANCELLING,
    MSG_RESET_TIMEOUT,
    MSG_RESET_WARNING,
    MSG_TASK_CANCELLED,
    MSG_TASK_INTERRUPTED,
    RESET_WAIT_INTERVAL,
    load_system_prompt,
    trace_log,
)
from agente.domain_context import DomainContextController, extract_domain
from agente.domain_tracker import DomainTracker
from agente.error_handler import handle_context_update_error, handle_step_callback_error, handle_task_error
from agente.history_manager import save_history
from agente.llm_manager import ensure_llm
from agente.task_processor import execute_task
from tasks import extract_structured_data_from_history

logger = logging.getLogger(__name__)


class AgentController:
    """Controlador del agente recursivo de contexto para navegación web autónoma.

    API async pura: sin threading. Usar run_task_async, reset_agent_async, stop_async.
    """

    def __init__(
        self,
        on_message: Callable[[str, str, Optional[str], Optional[str]], None],
        custom_controller: Optional[Controller] = None,
        browser_user_data_dir: Optional[str] = None,
    ):
        """Inicializa el controlador del agente.

        Args:
            on_message: Callback (role, content, status, color) para notificaciones.
            custom_controller: Controller personalizado. None usa DomainContextController.
            browser_user_data_dir: Directorio de perfil del navegador. None usa default.
        """
        self.on_message = on_message
        self._browser_user_data_dir = browser_user_data_dir or BROWSER_PROFILE_DIR
        self._tools_controller = (
            custom_controller if custom_controller is not None else DomainContextController()
        )

        self.browser: Optional[Browser] = None
        self.agent: Optional[Agent] = None
        self.llm: Optional[BaseChatModel] = None
        self._page_extraction_llm: Optional[BaseChatModel] = None
        self.system_prompt = load_system_prompt()

        self._lock = asyncio.Lock()
        self._cancel_event = asyncio.Event()
        self._task_running = False

        self._domain_tracker = DomainTracker()
        self._current_task_text: str = ""

        self._on_task_state_change: Optional[Callable[[bool], None]] = None
        self._last_history: Optional[Any] = None
        self._agent_ref: Optional[list] = None

    def set_task_state_callback(self, callback: Callable[[bool], None]) -> None:
        """Establece el callback para cambios de estado de ejecución.

        Args:
            callback: Función llamada con True al iniciar tarea, False al terminar.
        """
        self._on_task_state_change = callback

    @property
    def is_task_running(self) -> bool:
        """Indica si hay una tarea en ejecución."""
        return self._task_running

    async def cancel_task_async(self) -> None:
        """Cancela la tarea actual en ejecución.

        Establece _cancel_event, detiene el agente y notifica al usuario.
        """
        if self._task_running:
            logger.info("Cancelando tarea en ejecución...")
            self._cancel_event.set()
            async with self._lock:
                try:
                    self._stop_agent()
                except Exception as e:
                    logger.warning(f"Error deteniendo agente: {e}", exc_info=True)
                    raise
            self.on_message("system", MSG_CANCELLING, MSG_CANCELLED, COLOR_ERROR)

    async def reset_agent_async(self) -> None:
        """Reinicia el estado del agente, browser y LLMs para empezar limpio.

        Si hay tarea en ejecución, la cancela primero. Tiempo máximo MAX_RESET_WAIT_TIME.
        """
        logger.info("Iniciando reset del agente")

        if self._task_running:
            logger.info("Cancelando tarea antes del reset...")
            await self.cancel_task_async()
            await self._wait_for_task_completion_async(MAX_RESET_WAIT_TIME)

        self._cancel_event.clear()

        try:
            await asyncio.wait_for(
                self._reset_agent_async(), timeout=MAX_RESET_WAIT_TIME
            )
            logger.info("Reset del agente completado exitosamente")
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout esperando reset del agente después de {MAX_RESET_WAIT_TIME}s"
            )
            self.on_message("system", MSG_RESET_TIMEOUT, MSG_RESET_WARNING, COLOR_WARNING)

    async def _wait_for_task_completion_async(self, max_wait: float) -> None:
        """Espera a que la tarea termine o se alcance el timeout.

        Args:
            max_wait: Segundos máximos de espera.
        """
        waited_time = 0.0
        while self._task_running and waited_time < max_wait:
            await asyncio.sleep(RESET_WAIT_INTERVAL)
            waited_time += RESET_WAIT_INTERVAL

    async def _reset_agent_async(self) -> None:
        """Reinicia completamente el pipeline: browser, LLMs y estado del agente."""
        logger.info("Iniciando reset completo del pipeline")
        # #region agent log
        try:
            import json
            with open(r"c:\Users\anuez2\Downloads\browser-use_AGENTE_v2\.cursor\debug.log", "a", encoding="utf-8") as _dbg:
                _dbg.write(json.dumps({"id":"log_reset_start","timestamp":__import__("time").time()*1000,"location":"agent.py:_reset_agent_async","message":"Reset pipeline start","data":{"had_browser":self.browser is not None},"hypothesisId":"H2"}) + "\n")
        except Exception:
            pass
        # #endregion
        try:
            await self._stop_agent_if_running()
            await self._cleanup_resources()
            # #region agent log
            try:
                import json
                with open(r"c:\Users\anuez2\Downloads\browser-use_AGENTE_v2\.cursor\debug.log", "a", encoding="utf-8") as _dbg:
                    _dbg.write(json.dumps({"id":"log_reset_after_cleanup","timestamp":__import__("time").time()*1000,"location":"agent.py:_reset_agent_async","message":"After cleanup, before init","data":{},"hypothesisId":"H3"}) + "\n")
            except Exception:
                pass
            # #endregion
            await self._clear_agent_state()
            self.browser = await init_browser_async(self._browser_user_data_dir)
            logger.info("Reset completo del pipeline finalizado")
        except Exception as e:
            logger.error(f"Error durante reset del pipeline: {e}", exc_info=True)
            self.on_message("system", f"Error en reset: {e}", "Error", "#e74c3c")
            async with self._lock:
                self._cancel_event.clear()
                self._task_running = False
            raise

    async def _stop_agent_if_running(self) -> None:
        """Detiene el agente si está activo."""
        if self.agent:
            try:
                async with self._lock:
                    self._stop_agent()
            except Exception as e:
                logger.warning(f"Error deteniendo agente: {e}", exc_info=True)
                raise

    async def _cleanup_resources(self) -> None:
        """Limpia recursos (LLMs y browser)."""
        self.llm, self._page_extraction_llm = None, None
        await close_browser_async(self.browser)
        self.browser = None

    async def _clear_agent_state(self) -> None:
        """Limpia el estado interno del agente."""
        async with self._lock:
            self.agent = None
            self._agent_ref = None
            self._domain_tracker.reset()
            self._current_task_text = ""
            self._cancel_event.clear()
            self._last_history = None
            self._task_running = False

    async def run_task_async(self, task_text: str) -> str:
        """Ejecuta una tarea y retorna el resultado.

        Bloquea hasta que la tarea termine (éxito, error o cancelación).

        Args:
            task_text: Descripción de la tarea a ejecutar.

        Returns:
            Resultado final de la tarea o mensaje de cancelación/interrupción.
        """
        trace_log(logger, "run_task_async START task=%s", task_text[:80] + "..." if len(task_text) > 80 else task_text)
        try:
            await self._validate_task_start()
            self.browser = await ensure_browser_ready(
                self.browser, self._browser_user_data_dir
            )

            self._set_task_running(True)
            self._current_task_text = task_text

            if self._cancel_event.is_set():
                trace_log(logger, "run_task_async END result=cancelled_before_start")
                self.on_message(
                    "system", "Cancelado antes de iniciar", MSG_CANCELLED, COLOR_ERROR
                )
                return "Tarea cancelada antes de iniciar"

            self.llm, self._page_extraction_llm = ensure_llm(
                self.llm, self._page_extraction_llm
            )
            agent_ref = [self.agent]
            self._agent_ref = agent_ref

            final_result = await execute_task(
                task_text=task_text,
                browser=self.browser,
                llm=self.llm,
                page_extraction_llm=self._page_extraction_llm,
                system_prompt=self.system_prompt,
                tools_controller=self._tools_controller,
                agent_ref=agent_ref,
                step_callback=self._on_step_callback,
                cancel_check_callback=self._should_stop_async,
                set_last_history_callback=lambda h: setattr(self, "_last_history", h),
            )

            self.agent = agent_ref[0]

            await self._domain_tracker.finalize_with_judge(
                history=self._last_history,
                llm=self.llm,
                conversation_or_task=self._current_task_text,
                update_context_callback=lambda e, d, op: handle_context_update_error(
                    Exception(e) if isinstance(e, str) else e, d, op
                ),
            )

            if self._cancel_event.is_set():
                trace_log(logger, "run_task_async END result=interrupted")
                self.on_message(
                    "system", MSG_TASK_INTERRUPTED, MSG_CANCELLED, COLOR_ERROR
                )
                return MSG_TASK_INTERRUPTED
            trace_log(logger, "run_task_async END result=%s", final_result[:80] + "..." if len(final_result) > 80 else final_result)
            logger.info("Tarea completada exitosamente")
            self.on_message("agent", final_result, "Completado", COLOR_SUCCESS)
            return final_result

        except asyncio.CancelledError:
            trace_log(logger, "run_task_async END result=CancelledError")
            logger.warning("Tarea cancelada con CancelledError")
            self.on_message("system", MSG_TASK_CANCELLED, MSG_CANCELLED, COLOR_ERROR)
            raise
        except InterruptedError:
            trace_log(logger, "run_task_async END result=InterruptedError")
            logger.warning("Tarea interrumpida con InterruptedError")
            self.on_message(
                "system", MSG_TASK_INTERRUPTED, MSG_CANCELLED, COLOR_ERROR
            )
            return MSG_TASK_INTERRUPTED
        except Exception as e:
            trace_log(logger, "run_task_async END result=error: %s", str(e)[:80])
            handle_task_error(
                e,
                task_context=f"tarea '{task_text[:50]}...'",
                on_error=lambda msg: self.on_message(
                    "system", msg, "Fallo", COLOR_ERROR
                ),
            )
            raise
        finally:
            await self._cleanup_after_task()

    async def run_tasks_async(
        self, tasks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Ejecuta una secuencia de tareas: reset, ejecutar, guardar historial, extraer entidades.

        Orquesta internamente el flujo completo. main.py solo invoca y muestra resultados.

        Args:
            tasks: Lista de dicts con 'name' y 'description' por tarea.

        Returns:
            Lista acumulada de entidades extraídas (market_intelligence_data).
        """
        results: list[dict[str, Any]] = []
        for i, task in enumerate(tasks, 1):
            try:
                task_name = task.get("name", f"Tarea {i}")
                task_description = task.get("description", "")
                if not task_description:
                    logger.warning(f"Tarea {i} sin descripción, omitiendo")
                    continue

                self.on_message("system", f"Ejecutando tarea {i}: {task_name}", f"Tarea {i}", None)
                await self.reset_agent_async()
                if self._task_running:
                    logger.warning("Reset incompleto, continuando con precaución")

                await self.run_task_async(task_description)

                history = self.get_last_history()
                if not history:
                    logger.warning(f"No se encontró historial para tarea {i}")
                    self.on_message("system", f"Tarea {i} completada pero sin historial", "Advertencia", None)
                    continue

                save_history(history)
                entities = extract_structured_data_from_history(history)
                results.extend(entities)
                self.on_message(
                    "agent",
                    f"Tarea {i} completada: {len(entities)} entidades extraídas",
                    "Completado",
                    COLOR_SUCCESS,
                )

            except asyncio.CancelledError:
                logger.info("Ejecución de tareas cancelada")
                await self.cancel_task_async()
                self.on_message("system", MSG_TASK_CANCELLED, MSG_CANCELLED, COLOR_ERROR)
                raise
            except InterruptedError:
                logger.info("Ejecución de tareas interrumpida")
                self.on_message("system", MSG_TASK_INTERRUPTED, MSG_CANCELLED, COLOR_ERROR)
                raise
            except Exception as e:
                logger.error(f"Error en tarea {i}: {e}", exc_info=True)
                self.on_message(
                    "system",
                    f"Error en tarea {i}: {e}",
                    "Fallo",
                    COLOR_ERROR,
                )
                self.on_message("system", "Continuando con la siguiente tarea...", None, None)

        return results

    async def _validate_task_start(self) -> None:
        """Valida que se pueda iniciar una nueva tarea.

        Raises:
            RuntimeError: Si ya hay una tarea en ejecución.
        """
        if self._cancel_event.is_set():
            self._cancel_event.clear()

        if self._task_running:
            raise RuntimeError(
                "No se puede iniciar nueva tarea: hay una tarea en ejecución"
            )

    async def _cleanup_after_task(self) -> None:
        """Limpia recursos después de completar una tarea."""
        async with self._lock:
            if self.agent:
                try:
                    self._stop_agent()
                except Exception as e:
                    logger.warning(
                        f"Error deteniendo agente en limpieza: {e}", exc_info=True
                    )
                    raise
                self.agent = None

            self.llm, self._page_extraction_llm = None, None
            self._current_task_text = ""
            self._cancel_event.clear()
            self._agent_ref = None

        self._set_task_running(False)

    def get_last_history(self) -> Optional[Any]:
        """Obtiene el historial de la última tarea ejecutada.

        Returns:
            Objeto de historial o None si no hay.
        """
        return self._last_history

    def _stop_agent(self) -> None:
        """Detiene el agente en ejecución."""
        if self.agent:
            try:
                self.agent.stop()
            except Exception as e:
                logger.error(f"Error al intentar detener el agente: {e}", exc_info=True)
                raise

    async def stop_async(self) -> None:
        """Detiene el agente, cierra el navegador y libera recursos."""
        if self._task_running:
            await self.cancel_task_async()
        await self._stop_agent_if_running()
        await self._cleanup_resources()
        await self._clear_agent_state()
        self.agent = None
        self.llm = None
        self._page_extraction_llm = None

    async def _on_step_callback(
        self,
        browser_state: BrowserStateSummary,
        agent_output: AgentOutput,
        step_number: int,
    ) -> None:
        """Callback ejecutado en cada paso del agente para tracking recursivo de contexto.

        Invoca DomainTracker.track_step para actualizar contexto por dominio.
        No propaga excepciones: un raise abortaría el agente (integridad-tecnica).

        Args:
            browser_state: Estado del navegador en este paso.
            agent_output: Salida del agente.
            step_number: Número del paso actual.
        """
        try:
            url = getattr(browser_state, "url", None) or ""
            current_domain = extract_domain(url)
            trace_log(logger, "step_callback step=%d url=%s domain=%s", step_number, url, current_domain or "(none)")

            self.llm, self._page_extraction_llm = ensure_llm(
                self.llm, self._page_extraction_llm
            )

            agent_for_track = (
                self._agent_ref[0] if self._agent_ref and len(self._agent_ref) > 0 else self.agent
            )
            await self._domain_tracker.track_step(
                browser_state=browser_state,
                agent_output=agent_output,
                step_number=step_number,
                current_task_text=self._current_task_text,
                llm=self.llm,
                agent=agent_for_track,
                on_message=self.on_message,
                update_context_callback=lambda e, d, op: handle_context_update_error(
                    Exception(e) if isinstance(e, str) else e, d, op
                ),
            )
        except Exception as e:
            handle_step_callback_error(e)

    async def _should_stop_async(self) -> bool:
        """Verifica si se debe detener la ejecución de la tarea.

        Returns:
            True si _task_running y _cancel_event está establecido.
        """
        cancel_event_set = self._cancel_event.is_set()
        should_stop = self._task_running and cancel_event_set

        if cancel_event_set and not self._task_running:
            self._cancel_event.clear()

        return should_stop

    def _set_task_running(self, running: bool) -> None:
        """Actualiza el estado de ejecución de la tarea.

        Args:
            running: True si hay tarea activa, False si terminó.
        """
        self._task_running = running
        if not running:
            self._cancel_event.clear()
        if self._on_task_state_change:
            self._on_task_state_change(running)
