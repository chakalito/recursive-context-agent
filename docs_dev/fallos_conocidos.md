# Fallos conocidos y documentados

Registro de fallos corregidos por el agente de programación.

---

## Formato de cada entrada

- **Fecha**: YYYY-MM-DD
- **Descripción**: breve descripción del fallo
- **Causa raíz**: motivo del problema
- **Solución**: qué se hizo para corregirlo
- **Archivos afectados**: lista de archivos modificados

---

### [2025-02-11] Tratamiento especial action_name ocultaba error real

- **Descripción**: handle_task_error sustituía el error real de browser-use ("cannot access local variable 'action_name'") por el mensaje "Tarea completada con advertencias"
- **Causa raíz**: Violación de integridad técnica y flujo agente: no se debe filtrar ni alterar salidas; el fallo debe ser visible para depuración
- **Solución**: Eliminar el tratamiento especial; siempre registrar y propagar el mensaje real del error
- **Archivos afectados**: `agente/error_handler.py`

### [2025-02-11] close_browser_async no propagaba error de cierre

- **Descripción**: Al fallar browser.stop(), el error se logueaba pero no se re-lanzaba, ocultando el fallo al caller
- **Causa raíz**: Violación de integridad técnica: el fallo debe propagarse con su mensaje original para poder debuguear
- **Solución**: Añadir re-raise tras el log; cambiar logger.warning a logger.error
- **Archivos afectados**: `agente/browser_manager.py`

### [2025-02-11] history_manager capturaba Exception genérica

- **Descripción**: _extract_history_dict y get_history_final_result capturaban Exception sin re-raise, silenciando errores inesperados
- **Causa raíz**: Uso de except Exception sin recuperación definida; falta de documentación de política de excepciones
- **Solución**: Acotar a (AttributeError, TypeError, KeyError); documentar recuperación intencional para accesos a atributos de historial
- **Archivos afectados**: `agente/history_manager.py`

### [2025-02-11] Uso de threading en AgentController

- **Descripción**: AgentController usaba threading.Lock, threading.Event, queue.Queue y threading.Thread para un worker, violando la regla mono-hilo-mono-proceso
- **Causa raíz**: Diseño original con worker thread separado y main thread con polling; regla exige flujo asyncio puro
- **Solución**: Refactor completo a API async; sustituir por asyncio.Lock, asyncio.Event; eliminar worker thread; run_task_async reemplaza submit_task + wait
- **Archivos afectados**: `agente/agent.py`, `main.py`

### [2025-02-11] threading.Lock en domain_context

- **Descripción**: load_domains_context y save_domains_context usaban threading.Lock para sincronizar acceso a disco
- **Causa raíz**: Violación mono-hilo; threading prohibido en código propio
- **Solución**: Cambiar a asyncio.Lock; convertir load_domains_context, save_domains_context, get_domain_context y set_domain_context a async
- **Archivos afectados**: `agente/domain_context.py`, `agente/domain_tracker.py`, `agente/task_processor.py`

### [2025-02-11] Integridad técnica: exc_info y acotar excepciones en domain_tracker

- **Descripción**: Handlers en domain_tracker no incluían exc_info=True al loguear, dificultando el debug; _get_previous_result capturaba Exception genérica
- **Causa raíz**: Regla integridad-tecnica: el fallo debe ser visible en logs; evitar captura genérica sin recuperación específica
- **Solución**: Añadir exc_info=True en _get_previous_result, track_step (salir, refresh, excepción global); acotar _get_previous_result a (AttributeError, TypeError); otras excepciones propagan al caller
- **Archivos afectados**: `agente/domain_tracker.py`

### [2025-02-11] Integridad técnica: exc_info en _get_partial_history

- **Descripción**: _get_partial_history capturaba Exception sin incluir stack trace en el log
- **Causa raíz**: Regla integridad-tecnica: el fallo se ha de ver para poderlo debuguear
- **Solución**: Añadir exc_info=True al logger.warning
- **Archivos afectados**: `agente/task_processor.py`

### [2025-02-11] Alineación Haiku: default_headers en ChatAnthropicBedrock

- **Descripción**: ChatAnthropicBedrock no usaba headers anthropic-beta recomendados para computer-use y context-management
- **Causa raíz**: Regla llm-haiku-bedrock recomienda default_headers para máximo rendimiento con browser-use
- **Solución**: Añadir default_headers con computer-use-2025-01-24 y context-management-2025-06-27
- **Archivos afectados**: `agente/llm_manager.py`

### [2025-02-11] Limpieza: except: pass en data_extractor silenciaba errores

- **Descripción**: data_extractor usaba `except: pass` en fallbacks de parseo JSON, ocultando errores inesperados
- **Causa raíz**: Violación de integridad-tecnica: no silenciar errores; el fallo se ha de ver para debuguear
- **Solución**: Capturar json.JSONDecodeError explícitamente; para otras excepciones, logger.debug con exc_info=True
- **Archivos afectados**: `tasks/data_extractor.py`

### [2026-02-11] UnboundLocalError get_domain_context en DomainContextController

- **Descripción**: Al iniciar el agente, DomainContextController.__init__ lanzaba UnboundLocalError: cannot access local variable 'get_domain_context' where it is not associated with a value
- **Causa raíz**: La función interna async def get_domain_context(...) dentro de __init__ tenía el mismo nombre que la función del módulo get_domain_context; Python considera get_domain_context como variable local de todo __init__, pero en la línea get_persisted_context = get_domain_context aún no estaba definida
- **Solución**: Renombrar la función interna a get_domain_context_tool para que no haga shadow del get_domain_context del módulo
- **Archivos afectados**: `agente/domain_context.py`

### [2025-02-11] Limpieza: código muerto y redundancia

- **Descripción**: Funciones no usadas (handle_cdp_error, retry_with_backoff), módulo huérfano (debug_log.py), constantes obsoletas (TASK_COMPLETION_WAIT_INTERVAL, RESET_VERIFICATION_WAIT_TIME, MSG_RESET_COMPLETE, CONTEXT_INJECTED_FORMAT), funciones duplicadas (print_task_header idéntica a print_section_header)
- **Causa raíz**: Código residual de refactors previos y diseño con threads; duplicación no detectada
- **Solución**: Eliminar handle_cdp_error y retry_with_backoff; eliminar utils/debug_log.py; eliminar constantes no usadas en config; unificar print_section_header; usar CONSOLE_SEPARATOR_LENGTH en task_processor; actualizar docstring de agente/__init__.py
- **Archivos afectados**: `agente/config.py`, `agente/error_handler.py`, `agente/task_processor.py`, `agente/__init__.py`, `main.py`, `utils/debug_log.py` (eliminado)

### [2026-02-11] net::ERR_ABORTED en navegación inicial a whowhatwear.com

- **Descripción**: El agente intentaba ir automáticamente a whowhatwear.com; la navegación fallaba con RuntimeError: Navigation failed: net::ERR_ABORTED
- **Causa raíz**: directly_open_url=True hacía que browser-use extrajera la única URL del texto y la usara como acción inicial; sitios como whowhatwear pueden bloquear o abortar automatización
- **Solución**: Usar directly_open_url=False para que el agente arranque en about:blank y el LLM siga el orden de la tarea (Google primero, según instrucciones)
- **Archivos afectados**: `agente/config.py`, `agente/task_processor.py`, `docs_dev/fallos_conocidos.md`

### [2026-02-11] Eliminación de inyección forzada de contexto de dominio

- **Descripción**: El contexto de dominio se inyectaba desde código al system prompt y se usaban callbacks para marcar dominios "ya proporcionados", filtrando la herramienta get_domain_context
- **Causa raíz**: Violación de integridad-flujo-agente: no filtrar ni alterar entradas/salidas del modelo; el agente debe decidir cuándo invocar herramientas por sí mismo
- **Solución**: Eliminar prepare_task_with_context y _inject_context_from_task_text; eliminar _injected_domain, set_injected_domain, clear_injected_domain del AgentController y DomainContextController; reforzar instrucciones en mainPrompt.xml para que el agente invoque get_domain_context al entrar en dominios nuevos
- **Archivos afectados**: `agente/task_processor.py`, `agente/agent.py`, `agente/domain_context.py`, `agente/prompts/mainPrompt.xml`, `agente/config.py`, `agente/domain_tracker.py`

### [2026-02-11] Escape automático de bucle infinito no se ejecutaba

- **Descripción**: Al detectar bucle infinito (URL repetida >3 veces), el escape automático a about:blank no se ejecutaba; el agente seguía en bucle hasta 21+ repeticiones
- **Causa raíz**: _on_step_callback pasaba agent=self.agent a track_step, pero self.agent solo se actualiza después de execute_task. Durante agent.run(), self.agent era None, por lo que LOOP_AUTO_ESCAPE_ENABLED and agent fallaba y el escape nunca ocurría
- **Solución**: Guardar agent_ref en self._agent_ref antes de execute_task; en _on_step_callback usar agent_ref[0] cuando exista para pasar el agente actual a track_step; limpiar _agent_ref en _cleanup_after_task y _clear_agent_state
- **Archivos afectados**: `agente/agent.py`

### [2026-02-11] Contexto de dominio truncado excesivamente

- **Descripción**: Dominios como vogue.com o harpersbazaar.com producían 1350-1772 caracteres; se truncaba a 1000 eliminando contexto del inicio
- **Causa raíz**: MAX_CONTEXT_LENGTH=1000 hardcodeado en config; dominio con historial rico excedía el límite
- **Solución**: Hacer MAX_CONTEXT_LENGTH configurable vía DOMAIN_CONTEXT_MAX_LENGTH (env var) con valor por defecto 1500
- **Archivos afectados**: `agente/config.py`

### [2026-02-11] Tareas 2 y 3 retornaban 0 entidades extraídas

- **Descripción**: Tarea 2 (Google Trends) pide search_insights; Tarea 3 (clima/eventos) pide context_triggers. El data_extractor solo manejaba trends y events
- **Causa raíz**: Faltaban SearchInsightSchema, ContextTriggerSchema y sus handlers en data_extractor; las tareas usaban esquemas distintos a los soportados
- **Solución**: Añadir SearchInsightItem, SearchInsightSchema, ContextTriggerItem, ContextTriggerSchema en schemas.py; añadir search_insight_to_entity_dict y context_trigger_to_entity_dict; en data_extractor añadir ramas para search_insights y context_triggers; ampliar regex de búsqueda JSON para incluir estos campos
- **Archivos afectados**: `schemas.py`, `tasks/data_extractor.py`

### [2026-02-11] Falsos positivos en detección de bucle infinito

- **Descripción**: check_loop() consideraba URLs con diferentes query params como iguales (ej. trends.google.com/explore?q=vestido vs ?q=moda), generando falsos positivos cuando el agente exploraba búsquedas distintas de forma legítima
- **Causa raíz**: Normalización eliminaba query params: `url.split('?')[0].split('#')[0]` colapsaba distintas URLs en una sola
- **Solución**: Conservar query params; solo eliminar fragmentos (#); usar `url.strip().split('#')[0].strip()` para que URLs con distinto `q=` se consideren distintas
- **Archivos afectados**: `agente/domain_tracker.py`

### [2026-02-11] Contexto de dominio truncado con límite insuficiente

- **Descripción**: Dominios con historial rico (google.com, trends.google.com, duckduckgo.com) excedían 1500 caracteres y se truncaba el contexto perdiendo el resumen inicial
- **Causa raíz**: MAX_CONTEXT_LENGTH por defecto 1500 insuficiente; comentario en config ya sugería 1500-2000 para reducir truncados
- **Solución**: Aumentar valor por defecto de DOMAIN_CONTEXT_MAX_LENGTH de 1500 a 2000
- **Archivos afectados**: `agente/config.py`

### [2026-02-11] Verbosidad excesiva en data_extractor

- **Descripción**: Cada action_result con datos estructurados generaba un log INFO ("Procesadas X tendencias..."), saturando los logs con mensajes repetitivos
- **Causa raíz**: Logs por tipo de entidad a nivel INFO para cada resultado; varios resultados del mismo tipo generaban múltiples líneas similares
- **Solución**: Pasar mensajes "Procesadas X tendencias/insights/triggers" a logger.debug(); mantener en INFO "Procesando N resultados" y "Total de entidades extraídas"
- **Archivos afectados**: `tasks/data_extractor.py`

### [2026-02-11] Mejoras prioridad alta de browser-use

- **Descripción**: Aplicación de mejoras identificadas en el análisis de browser-use: use_vision, message_compaction explícito, eliminación del escape de bucles personalizado
- **Causa raíz**: Código custom redundante; capacidades de browser-use no aprovechadas (visión, compactación); duplicación de lógica de detección de bucles
- **Solución**: (1) Habilitar use_vision con vision_detail_level='low' configurable vía USE_VISION, VISION_DETAIL_LEVEL; (2) Añadir message_compaction explícito con MessageCompactionSettings ajustado a Haiku (trigger_char_count=20000, compact_every_n_steps=12); (3) Eliminar check_loop, _visited_urls y escape automático a about:blank de domain_tracker; delegar detección de bucles a browser-use (loop_detection_enabled=True por defecto); eliminar MAX_URL_REPETITIONS y LOOP_AUTO_ESCAPE_ENABLED de config
- **Archivos afectados**: `agente/config.py`, `agente/task_processor.py`, `agente/domain_tracker.py`

### [2026-02-11] Migración completa a loop detection de browser-use

- **Descripción**: Confirmación y cierre de la migración: el proyecto usa exclusivamente el ActionLoopDetector nativo de browser-use para detección de bucles
- **Causa raíz**: Necesidad de eliminar cualquier vestigio propio y documentar explícitamente el uso del mecanismo de browser-use
- **Solución**: (1) Verificación: no quedaba código residual (check_loop, escape, MAX_URL_REPETITIONS); (2) Añadir LOOP_DETECTION_ENABLED y LOOP_DETECTION_WINDOW en config.py; (3) Pasar loop_detection_enabled y loop_detection_window explícitamente al Agent en task_processor; (4) Documentar migración completada en fallos_conocidos
- **Archivos afectados**: `agente/config.py`, `agente/task_processor.py`, `docs_dev/fallos_conocidos.md`

### [2026-02-11] Limpieza de código del proyecto

- **Descripción**: Eliminación de código muerto, redundancias, duplicación y constantes no usadas para mejorar mantenibilidad
- **Causa raíz**: Código residual de refactors previos; valores hardcodeados en lugar de constantes; duplicación de boilerplate en schemas
- **Solución**: (1) Eliminar extract_domains_from_text (no usada) y re de domain_tracker; (2) Eliminar SHUTDOWN_DRAIN_SLEEP_S; (3) Eliminar pyc obsoleto definitions.cpython-311.pyc; (4) Usar COLOR_THINKING en domain_tracker en vez de literal "#9b59b6"; (5) Usar CONVERSATIONS_DIR_NAME en task_processor para save_conversation_path; (6) Unificar level_map en _LEVEL_MAP en logging_config; (7) Extraer _build_base_entity_dict en schemas.py para reducir duplicación en conversores; (8) Renombrar función interna a get_domain_context_tool en DomainContextController
- **Archivos afectados**: `agente/domain_tracker.py`, `agente/config.py`, `agente/task_processor.py`, `agente/domain_context.py`, `utils/logging_config.py`, `schemas.py`, `tasks/__pycache__/` (pyc eliminado)

### [2026-02-11] Limpieza adicional de código

- **Descripción**: Eliminación de estado redundante, parámetro no usado, y añadir .gitignore estándar
- **Causa raíz**: AgentController._visited_domains duplicaba DomainTracker._visited_domains; process_task_results recibía task_name sin usarlo; falta de .gitignore para Python
- **Solución**: (1) Eliminar _visited_domains de AgentController (solo usaba para trace_log); (2) Eliminar parámetro task_name de process_task_results; (3) Crear .gitignore con __pycache__/, venv/, logs/, browser_profile/, .env; (4) Simplificar browser_user_data_dir a `or BROWSER_PROFILE_DIR`
- **Archivos afectados**: `agente/agent.py`, `main.py`, `.gitignore` (creado), `docs_dev/fallos_conocidos.md`

### [2026-02-11] Frontera main/agente: orquestación en main

- **Descripción**: main.py contenía lógica de orquestación (reset, bucle, process_task_results con save_history y extract_structured_data) que violaba la regla main-agente-frontera
- **Causa raíz**: La regla exige que main solo lea tasks, invoque al agente y muestre output; la orquestación debe estar en agente/
- **Solución**: Añadir run_tasks_async en AgentController que orquesta internamente reset → run_task_async → save_history → extract; simplificar main.py a load tasks, run_tasks_async, print_summary
- **Archivos afectados**: `agente/agent.py`, `main.py`

### [2026-02-11] Integridad técnica: SUPPRESS_EXPECTED_CDP_ERRORS ocultaba fallos

- **Descripción**: Por defecto true hacía que errores CDP/browser se registraran a debug; con LOG_LEVEL=INFO no se veían
- **Causa raíz**: Regla integridad-tecnica: el fallo debe ser visible para poderlo debuguear
- **Solución**: Cambiar valor por defecto a false en config.py
- **Archivos afectados**: `agente/config.py`

### [2026-02-11] Integridad técnica: error_handler usaba logger.debug para errores esperados

- **Descripción**: Con suppress=True, errores esperados (CDP, browser) se logueaban con logger.debug en lugar de logger.error
- **Causa raíz**: Ocultaba fallos; integridad-tecnica exige visibilidad
- **Solución**: Siempre usar logger.error; suppress solo controla exc_info (omisión de stack trace para errores esperados)
- **Archivos afectados**: `agente/error_handler.py`

### [2026-02-11] Integridad técnica: errores en limpieza no se propagaban

- **Descripción**: cancel_task_async, _stop_agent_if_running y _cleanup_after_task logueaban errores al detener el agente pero no hacían raise
- **Causa raíz**: Regla integridad-tecnica: el fallo debe propagarse con su mensaje original para depuración
- **Solución**: Añadir raise tras logger.warning/error en los bloques de detención; documentar en _on_step_callback por qué no se propaga (callback de browser-use, raise abortaría el agente)
- **Archivos afectados**: `agente/agent.py`

### [2026-02-11] Timeout en arranque del navegador en Windows

- **Descripción**: LocalBrowserWatchdog.on_BrowserLaunchEvent excedía 30s y fallaba con TimeoutError; el agente no llegaba a iniciar la primera tarea
- **Causa raíz**: browser-use usa por defecto 30s para BrowserStartEvent y BrowserLaunchEvent; en Windows el arranque puede tardar más por antivirus, primera descarga de Chromium o disco lento
- **Solución**: Configurar TIMEOUT_BrowserStartEvent y TIMEOUT_BrowserLaunchEvent vía variables de entorno antes de browser.start(); añadir BROWSER_LAUNCH_TIMEOUT_S (default 90s) y derivar MAX_RESET_WAIT_TIME para que el reset no corte antes de que termine el arranque
- **Archivos afectados**: `agente/config.py`, `agente/browser_manager.py`

### [2026-02-11] CDP ax_tree: Frame with the given frameId is not found

- **Descripción**: Al navegar a Google u otros sitios dinámicos, browser-use fallaba con RuntimeError -32602 "Frame with the given frameId is not found" y TimeoutError en ax_tree; el DOM build usaba "minimal state" y el agente recibía "Element index N not available"
- **Causa raíz**: En _get_ax_tree_for_all_frames, browser-use obtiene el frame tree y lanza Accessibility.getFullAXTree en paralelo; sitios como google.com crean/destruyen iframes dinámicamente, provocando race condition (frames obsoletos al ejecutar las peticiones CDP)
- **Solución**: Mitigación vía configuración Browser sin modificar librerías: cross_origin_iframes=False (reduce frames procesados), max_iframes=5, minimum_wait_page_load_time=0.5, wait_for_network_idle_page_load_time=1.0, wait_between_actions=0.2; variables de entorno CROSS_ORIGIN_IFRAMES, MAX_IFRAMES, MINIMUM_WAIT_PAGE_LOAD_TIME, WAIT_FOR_NETWORK_IDLE_PAGE_LOAD_TIME, WAIT_BETWEEN_ACTIONS
- **Archivos afectados**: `agente/config.py`, `agente/browser_manager.py`

---

## Excepciones mantenidas por diseño

Handlers que capturan excepciones y no re-lanzan, documentados como recuperación intencional:

| Ubicación | Excepción | Razón |
|-----------|-----------|-------|
| agent.py `_on_step_callback` | Exception en tracking de dominio | Callback invocado por browser-use; un raise abortaría el bucle del agente; log + continuar |
| domain_tracker.py `_get_previous_result` | AttributeError, TypeError al obtener historial | Best-effort; API de historial puede cambiar; otras excepciones propagan |
| domain_tracker.py `track_step` | Exception en update_context | Callbacks no deben interrumpir el agente; exc_info en log antes de callback |
| task_processor.py `_get_partial_history` | Exception al obtener historial | Best-effort en cancelación; guardar lo posible; exc_info en log |

---
