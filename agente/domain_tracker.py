"""
Tracking recursivo de contexto por dominio para el agente recursivo de contexto.

Gestiona el seguimiento de dominios visitados y la actualización de contexto
basado en la navegación del agente.

Detección de bucles: delegada a browser-use (loop_detection_enabled=True por defecto).
"""
import logging
from typing import Any, Callable, Optional

from browser_use.agent.views import AgentOutput
from browser_use.browser.views import BrowserStateSummary
from langchain_core.language_models.chat_models import BaseChatModel

from agente.config import (
    COLOR_THINKING,
    DOMAIN_CONTEXT_MIN_STEPS_FOR_UPDATE,
    DOMAIN_CONTEXT_REFRESH_STEPS,
    MAX_VISIT_HISTORY_STEPS,
    trace_log,
)
from agente.domain_context import (
    extract_domain,
    get_domain_context,
    normalize_domain,
    set_domain_context,
    update_domain_context_async,
)

logger = logging.getLogger(__name__)


class DomainTracker:
    """Gestiona el tracking recursivo de contexto por dominio."""
    
    def __init__(self):
        """Inicializa el tracker de dominio."""
        self._previous_domain: Optional[str] = None
        self._visit_history_buffer: list[str] = []
        self._steps_in_domain: int = 0
        self._domain_for_steps: Optional[str] = None
        self._buffer_lines_sent_for_current_domain: int = 0
        self._steps_per_domain: dict[str, int] = {}
        self._visited_domains: set[str] = set()

    def reset(self) -> None:
        """Limpia el estado de tracking recursivo de contexto por dominio.

        Restablece buffers, contadores y dominios visitados.
        """
        self._previous_domain = None
        self._visit_history_buffer = []
        self._steps_in_domain = 0
        self._domain_for_steps = None
        self._buffer_lines_sent_for_current_domain = 0
        self._steps_per_domain.clear()
        self._visited_domains.clear()
    
    async def _detect_proactive_navigation(
        self,
        agent_output: AgentOutput,
        current_domain: str,
        on_message: Callable[[str, str, Optional[str], Optional[str]], None],
    ) -> None:
        """Detecta navegación proactiva y notifica si hay contexto disponible.

        Args:
            agent_output: Salida del agente con acciones planeadas.
            current_domain: Dominio actual.
            on_message: Callback para notificar al usuario.
        """
        actions = getattr(agent_output, "action", []) or []
        for action in actions:
            action_dict = action if isinstance(action, dict) else (
                action.model_dump() if hasattr(action, "model_dump") else {}
            )
            navigate_data = action_dict.get("navigate")
            if not navigate_data:
                continue

            navigate_url = (
                navigate_data.get("url") if isinstance(navigate_data, dict)
                else str(navigate_data)
            )
            if not navigate_url:
                continue

            target_domain = extract_domain(navigate_url)
            if target_domain and target_domain != current_domain:
                ctx = await get_domain_context(target_domain)
                if ctx:
                    logger.info("Detección proactiva: agente navegará a dominio %s con contexto disponible", target_domain)
                    on_message("info", f"Preparando contexto para {target_domain}", "Contexto", "#3498db")
    
    def _get_previous_result(self, agent: Optional[Any], step_number: int) -> Optional[list[Any]]:
        """Obtiene el resultado del paso anterior del historial del agente.

        Args:
            agent: Instancia del agente con get_history().
            step_number: Número del paso actual (índice 1-based).

        Returns:
            Lista de resultados del paso anterior, o None.
        """
        if not agent or not hasattr(agent, "get_history"):
            return None
        
        try:
            history = agent.get_history()
            if not history or not hasattr(history, "history") or not history.history:
                return None
            
            if len(history.history) >= step_number and step_number > 0:
                prev_history_item = history.history[step_number - 1]
                if prev_history_item and hasattr(prev_history_item, "result"):
                    return prev_history_item.result
        except (AttributeError, TypeError) as e:
            logger.debug("No se pudo obtener historial anterior: %s", e, exc_info=True)
        
        return None
    
    def _extract_action_results(
        self, previous_result: Optional[list[Any]]
    ) -> tuple[list[str], Optional[bool], list[str]]:
        """Extrae contenido, éxito y errores de resultados de acciones anteriores.

        Args:
            previous_result: Lista de resultados de acciones del paso previo.

        Returns:
            Tupla (extracted_content_parts, action_success, error_parts).
        """
        extracted_content_parts = []
        action_success = None
        error_parts = []

        if not previous_result:
            return extracted_content_parts, action_success, error_parts

        for result_item in previous_result:
            extracted = None
            err = None
            done_val = None
            success_val = None

            if isinstance(result_item, dict):
                extracted = result_item.get("extracted_content") or result_item.get("extractedContent")
                err = result_item.get("error")
                done_val = result_item.get("is_done")
                success_val = result_item.get("success")
            elif hasattr(result_item, "extracted_content"):
                extracted = getattr(result_item, "extracted_content", None)
                err = getattr(result_item, "error", None) if hasattr(result_item, "error") else None
                done_val = getattr(result_item, "is_done", None) if hasattr(result_item, "is_done") else None
                success_val = getattr(result_item, "success", None) if hasattr(result_item, "success") else None

            if done_val is not None:
                action_success = done_val
            elif success_val is not None:
                action_success = success_val

            if extracted:
                extracted_str = str(extracted)
                if len(extracted_str) > 200:
                    extracted_str = extracted_str[:200] + "..."
                extracted_content_parts.append(extracted_str)

            if err and str(err).strip():
                err_str = str(err).strip()
                if len(err_str) > 150:
                    err_str = err_str[:150] + "..."
                error_parts.append(err_str)

        return extracted_content_parts, action_success, error_parts

    def _summarize_actions(self, actions: list[Any]) -> str:
        """Resume acciones en formato compacto: click(42), navigate(url), input(index,text).

        Args:
            actions: Lista de acciones del agente.

        Returns:
            String con acciones resumidas separadas por coma.
        """
        if not actions:
            return ""
        parts = []
        for action in actions:
            data = None
            if hasattr(action, "model_dump"):
                data = action.model_dump(exclude_unset=True)
            elif isinstance(action, dict):
                data = action
            if not data or not isinstance(data, dict):
                continue
            for action_name, params in data.items():
                if not isinstance(params, dict):
                    params = {}
                if action_name == "click":
                    idx = params.get("index")
                    parts.append(f"click({idx})" if idx is not None else "click")
                elif action_name == "navigate":
                    url = params.get("url", "")
                    u = str(url)[:60] + "..." if len(str(url)) > 60 else str(url)
                    parts.append(f"navigate({u})")
                elif action_name == "input":
                    idx = params.get("index")
                    text = (params.get("text") or "")[:20]
                    if len(str(params.get("text") or "")) > 20:
                        text += "..."
                    parts.append(f"input({idx},{repr(text)})" if idx is not None else f"input({repr(text)})")
                elif action_name in ("scroll_up", "scroll_down"):
                    parts.append(action_name)
                elif action_name == "done":
                    parts.append("done")
                elif action_name == "wait":
                    parts.append("wait")
                else:
                    parts.append(f"{action_name}(...)")
        return ",".join(parts) if parts else ""

    def _format_visit_line_parts(
        self,
        step_number: int,
        url: str,
        title: str,
        next_goal: str,
        evaluation: str,
        actions_str: str,
        action_success: Optional[bool],
        extracted_content_parts: list[str],
        error_parts: list[str],
        memory: str,
        browser_errors: Optional[list],
    ) -> list[str]:
        """Formatea las partes de la línea de historial de visita.

        Args:
            step_number: Número del paso.
            url: URL actual.
            title: Título de la página.
            next_goal: Objetivo del siguiente paso.
            evaluation: Evaluación del objetivo anterior.
            actions_str: Resumen de acciones.
            action_success: Si la acción anterior tuvo éxito.
            extracted_content_parts: Contenido extraído.
            error_parts: Errores encontrados.
            memory: Memoria del agente.
            browser_errors: Errores del navegador.

        Returns:
            Lista de strings con las partes formateadas.
        """
        parts = [f"Paso {step_number}: URL={url}"]

        if title:
            parts.append(f"Título={title}")
        if next_goal:
            parts.append(f"Objetivo={next_goal}")
        if evaluation:
            parts.append(f"Evaluación={evaluation}")
        if actions_str:
            parts.append(f"Acciones={actions_str}")
        if action_success is not None:
            result_str = f"Resultado={'✓' if action_success else '✗'}"
            if error_parts:
                result_str += f" [error: {'; '.join(error_parts[:1])}]"
            parts.append(result_str)
        if extracted_content_parts:
            extracted_summary = " | ".join(extracted_content_parts[:2])
            parts.append(f"Extraído={extracted_summary}")
        if memory:
            memory_short = memory[:100] + "..." if len(memory) > 100 else memory
            parts.append(f"Memoria={memory_short}")
        if browser_errors and isinstance(browser_errors, list) and browser_errors:
            err_msgs = []
            for i, err in enumerate(browser_errors[:2]):
                if isinstance(err, str):
                    err_msgs.append((err[:100] + "...") if len(err) > 100 else err)
                else:
                    err_msgs.append(str(err)[:100])
            parts.append(f"Errores={'; '.join(err_msgs)}")
        
        return parts
    
    def build_visit_line(
        self,
        step_number: int,
        browser_state: BrowserStateSummary,
        agent_output: AgentOutput,
        previous_result: Optional[list[Any]] = None,
    ) -> str:
        """Construye una línea de historial de visita enriquecida.

        Args:
            step_number: Número del paso.
            browser_state: Estado del navegador.
            agent_output: Salida del agente.
            previous_result: Resultados del paso anterior.

        Returns:
            Línea formateada con URL, objetivo, acciones, resultado, etc.
        """
        url = getattr(browser_state, "url", None) or ""
        title = getattr(browser_state, "title", None) or ""
        next_goal = getattr(agent_output, "next_goal", None) or ""
        evaluation = getattr(agent_output, "evaluation_previous_goal", None) or ""
        memory = getattr(agent_output, "memory", None) or ""
        actions = getattr(agent_output, "action", []) or []
        actions_str = self._summarize_actions(actions)
        browser_errors = getattr(browser_state, "browser_errors", None)
        
        extracted_content_parts, action_success, error_parts = self._extract_action_results(previous_result)

        parts = self._format_visit_line_parts(
            step_number, url, title, next_goal, evaluation, actions_str,
            action_success, extracted_content_parts, error_parts, memory, browser_errors
        )
        
        return " | ".join(parts)

    async def track_step(
        self,
        browser_state: BrowserStateSummary,
        agent_output: AgentOutput,
        step_number: int,
        current_task_text: str,
        llm: Optional[BaseChatModel],
        agent: Optional[Any],
        on_message: Callable[[str, str, Optional[str], Optional[str]], None],
        update_context_callback: Callable[[str, str, str], None],
    ) -> None:
        """Rastrea un paso del agente y actualiza el contexto de dominio si es necesario.
        
        Incluye detección proactiva de navegación a dominios nuevos y enriquecimiento
        del historial con información de éxito/fallo y contenido extraído.
        
        Args:
            browser_state: Estado del navegador en este paso.
            agent_output: Salida del agente en este paso.
            step_number: Número del paso actual.
            current_task_text: Texto de la tarea actual.
            llm: Instancia del LLM para actualizar contexto.
            agent: Instancia del agente (para obtener conversación completa e historial).
            on_message: Callback para enviar mensajes.
            update_context_callback: Callback para actualizar contexto (maneja errores).
        """
        try:
            url = getattr(browser_state, "url", None) or ""
            current_domain = extract_domain(url)
            trace_log(logger, "track_step step=%d url=%s domain=%s", step_number, url, current_domain or "(none)")

            # Detectar navegación proactiva
            await self._detect_proactive_navigation(agent_output, current_domain, on_message)
            
            if current_domain:
                self._visited_domains.add(current_domain)
            
            # Obtener resultado del paso anterior
            previous_result = self._get_previous_result(agent, step_number)
            
            goal_message = getattr(agent_output, "next_goal", None) or "Procesando..."
            exit_domain: Optional[tuple[str, str]] = None
            refresh_domain: Optional[tuple[str, str]] = None

            if self._previous_domain and self._previous_domain != current_domain and current_domain:
                trace_log(logger, "domain_change prev=%s current=%s", self._previous_domain, current_domain)
                visit_history = "\n".join(self._visit_history_buffer) if self._visit_history_buffer else "(sin pasos)"
                steps_count = self._steps_per_domain.get(self._previous_domain, 0)
                
                if steps_count >= DOMAIN_CONTEXT_MIN_STEPS_FOR_UPDATE:
                    trace_log(logger, "exit_domain domain=%s steps_in_domain=%d", self._previous_domain, steps_count)
                    exit_domain = (self._previous_domain, visit_history)
                
                self._visit_history_buffer = []
                self._steps_in_domain = 0
                self._buffer_lines_sent_for_current_domain = 0
                if current_domain:
                    self._steps_per_domain[current_domain] = 0

            if current_domain:
                # Usar historial enriquecido con información de resultados anteriores
                line = self.build_visit_line(step_number, browser_state, agent_output, previous_result)
                self._visit_history_buffer.append(line)
                self._steps_per_domain[current_domain] = self._steps_per_domain.get(current_domain, 0) + 1
                
                if len(self._visit_history_buffer) > MAX_VISIT_HISTORY_STEPS:
                    self._visit_history_buffer = self._visit_history_buffer[-MAX_VISIT_HISTORY_STEPS:]
                    self._buffer_lines_sent_for_current_domain = min(
                        self._buffer_lines_sent_for_current_domain,
                        len(self._visit_history_buffer),
                    )

                if self._domain_for_steps != current_domain:
                    self._domain_for_steps = current_domain
                    self._steps_in_domain = 1
                else:
                    self._steps_in_domain += 1
                
                if self._steps_in_domain >= DOMAIN_CONTEXT_REFRESH_STEPS:
                    trace_log(logger, "refresh_domain domain=%s steps_in_domain=%d", current_domain, self._steps_in_domain)
                    new_lines = self._visit_history_buffer[self._buffer_lines_sent_for_current_domain:]
                    visit_delta = "\n".join(new_lines) if new_lines else "(sin pasos nuevos)"
                    refresh_domain = (current_domain, visit_delta)
                    self._buffer_lines_sent_for_current_domain = len(self._visit_history_buffer)
                    self._steps_in_domain = 0

            if current_domain:
                self._previous_domain = current_domain

            if exit_domain:
                domain, visit_history = exit_domain
                logger.info("Actualizando contexto al salir de dominio: %s", domain)
                try:
                    await self._update_domain_context(
                        domain, visit_history, current_task_text, llm, agent, update_context_callback
                    )
                except Exception as e:
                    logger.error("Error actualizando contexto al salir de dominio %s: %s", domain, e, exc_info=True)
                    update_context_callback(str(e), domain, "salir")
            
            if refresh_domain:
                domain, visit_delta = refresh_domain
                logger.info("Refrescando contexto de dominio: %s", domain)
                try:
                    await self._update_domain_context(
                        domain, visit_delta, current_task_text, llm, agent, update_context_callback
                    )
                except Exception as e:
                    logger.error("Error refrescando contexto de dominio %s: %s", domain, e, exc_info=True)
                    update_context_callback(str(e), domain, "refresh")

            on_message("thinking", f"Paso {step_number}: {goal_message}", f"Paso {step_number}", COLOR_THINKING)
            
        except Exception as e:
            logger.error("Error en track_step: %s", e, exc_info=True)
            update_context_callback(str(e), "", "track_step")
    
    def _build_agent_history_summary(self, agent: Optional[Any]) -> str:
        """Construye resumen del historial del agente (URLs, errores, objetivos).

        Args:
            agent: Instancia del agente con get_history().

        Returns:
            String con URLs y errores de los últimos 10 pasos (máx 8 líneas).
        """
        if not agent or not hasattr(agent, "get_history"):
            return ""
        try:
            history = agent.get_history()
            if not history or not hasattr(history, "history") or not history.history:
                return ""
            lines = []
            urls_seen = set()
            for i, item in enumerate(history.history[-10:]):
                if not item or not hasattr(item, "state"):
                    continue
                url = getattr(item.state, "url", None)
                if url and url not in urls_seen:
                    urls_seen.add(url)
                    u = (url[:77] + "...") if len(str(url)) > 80 else url
                    lines.append(f"URL: {u}")
                if hasattr(item, "result") and item.result:
                    for r in item.result:
                        err = r.get("error") if isinstance(r, dict) else getattr(r, "error", None) if r else None
                        if err and str(err).strip():
                            e = str(err).strip()
                            lines.append(f"Error: {(e[:97] + '...') if len(e) > 100 else e}")
            return "\n".join(lines[:8]) if lines else ""
        except (AttributeError, TypeError) as e:
            logger.debug("No se pudo construir agent_history_summary: %s", e)
            return ""

    async def _update_domain_context(
        self,
        domain: str,
        visit_history: str,
        conversation_or_task: str | None,
        llm: Optional[BaseChatModel],
        agent: Optional[Any],
        error_callback: Callable[[str, str, str], None],
    ) -> None:
        """Actualiza recursivamente el contexto de un dominio usando el LLM.

        Args:
            domain: Dominio a actualizar.
            visit_history: Historial de visitas en el dominio.
            conversation_or_task: Tarea o conversación actual.
            llm: Modelo para generar la actualización.
            agent: Agente para obtener resumen del historial.
            error_callback: Callback (error_msg, domain, operation) si falla.
        """
        if not domain or not llm:
            return
        trace_log(logger, "_update_domain_context domain=%s visit_history_len=%d", domain, len(visit_history))

        effective_conversation = conversation_or_task
        if agent:
            mm = getattr(agent, "message_manager", None)
            if mm:
                full_task = getattr(mm, "task", None)
                if full_task and str(full_task).strip():
                    effective_conversation = full_task

        agent_history_summary = self._build_agent_history_summary(agent)

        existing = await get_domain_context(domain)
        result = await update_domain_context_async(
            existing_context=existing,
            visit_history=visit_history,
            llm=llm,
            conversation_or_task=effective_conversation,
            domain=domain,
            agent_history_summary=agent_history_summary or None,
        )
        if result and result.strip():
            await set_domain_context(domain, result)
            logger.info("Contexto de dominio guardado: %s", domain)

    async def finalize_with_judge(
        self,
        history: Any,
        llm: Optional[BaseChatModel],
        conversation_or_task: str | None,
        update_context_callback: Callable[[str, str, str], None],
    ) -> None:
        """Actualización final del último dominio con evaluación del Judge.

        Se invoca tras agent.run() cuando la tarea terminó. Incluye el Judge
        para que el LLM de contexto sepa si las rutas realmente funcionaron.
        """
        if not self._previous_domain or not llm:
            return
        if not self._visit_history_buffer:
            trace_log(logger, "finalize_with_judge domain=%s buffer vacío, omitiendo", self._previous_domain)
            return

        judgement = None
        if history and hasattr(history, "judgement"):
            try:
                judgement = history.judgement()
            except (AttributeError, TypeError) as e:
                logger.debug("No se pudo obtener judgement: %s", e)

        visit_history = "\n".join(self._visit_history_buffer)
        domain = self._previous_domain

        agent_history_summary = ""
        if history and hasattr(history, "history") and history.history:
            lines = []
            urls_seen = set()
            for item in history.history[-10:]:
                if not item or not hasattr(item, "state"):
                    continue
                url = getattr(item.state, "url", None)
                if url and url not in urls_seen:
                    urls_seen.add(url)
                    u = (str(url)[:77] + "...") if len(str(url)) > 80 else str(url)
                    lines.append(f"URL: {u}")
            agent_history_summary = "\n".join(lines[:6]) if lines else ""

        logger.info("Finalizando contexto con Judge para dominio: %s", domain)
        try:
            existing = await get_domain_context(domain)
            result = await update_domain_context_async(
                existing_context=existing,
                visit_history=visit_history,
                llm=llm,
                conversation_or_task=conversation_or_task,
                domain=domain,
                agent_history_summary=agent_history_summary or None,
                judge_result=judgement,
            )
            if result and result.strip():
                await set_domain_context(domain, result)
                logger.info("Contexto de dominio guardado (final con Judge): %s", domain)
            self._visit_history_buffer = []
            self._buffer_lines_sent_for_current_domain = 0
        except Exception as e:
            logger.error("Error en finalize_with_judge para %s: %s", domain, e, exc_info=True)
            update_context_callback(str(e), domain, "finalize_judge")


