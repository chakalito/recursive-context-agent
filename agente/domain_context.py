"""
Sistema recursivo de contexto por dominio para navegación web autónoma.

Implementa el mecanismo central del agente recursivo de contexto que acumula
y actualiza conocimiento por dominio durante la navegación.

Usa asyncio.Lock para sincronizar acceso a disco (mono-hilo, sin threading).
"""

import asyncio
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from browser_use.agent.views import ActionResult
from browser_use.browser import BrowserSession
from browser_use.controller import Controller
from browser_use.llm.messages import UserMessage
from browser_use.tools.views import NoParamsAction
from langchain_core.language_models.chat_models import BaseChatModel

from agente.config import (
    CONTEXT_LOADED_LTM,
    DOMAIN_CONTEXT_CACHE_ENABLED,
    DOMAIN_CONTEXT_CACHE_TTL_S,
    DOMAINS_CONTEXT_PATH,
    MAX_CONTEXT_LENGTH,
    NO_CONTEXT_MSG,
    load_domain_context_update_prompt,
    trace_log,
)

logger = logging.getLogger(__name__)

# Lock para acceso secuencial a domains_context.json (asyncio, mono-hilo)
_FILE_LOCK = asyncio.Lock()
_SKIP_NETLOCS = frozenset(("", "about", "about:blank"))

# Constantes para cálculo de clave de caché
_CACHE_KEY_LENGTHS = {
    "existing_context": 200,
    "visit_history": 500,
    "conversation": 200,
}


def extract_domain(url: str) -> str:
    """Extrae y normaliza el dominio de una URL.

    Args:
        url: URL completa (ej: https://www.example.com/path).

    Returns:
        Dominio normalizado sin www (ej: example.com), o "" si inválido.
    """
    if not url or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    netloc = (parsed.netloc or "").lower()
    if not netloc or netloc in _SKIP_NETLOCS:
        return ""
    return normalize_domain(netloc)


def normalize_domain(domain: str) -> str:
    """Normaliza un nombre de dominio eliminando el prefijo www.

    Args:
        domain: Nombre de dominio (ej: www.example.com).

    Returns:
        Dominio en minúsculas sin www (ej: example.com).
    """
    if not domain:
        return ""
    d = domain.strip().lower()
    if d.startswith("www."):
        return d[4:]
    return d


async def load_domains_context() -> dict:
    """Carga el contexto persistido de todos los dominios desde disco.

    Returns:
        Diccionario dominio -> {context, updated_at}. Vacío si no existe el archivo.
    """
    path = Path(DOMAINS_CONTEXT_PATH)
    if not path.exists():
        return {}
    async with _FILE_LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.warning("domains_context.json está vacío; inicializando con diccionario vacío.")
                    return {}
                data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("domains_context.json inválido: %s", e, exc_info=True)
            logger.warning("Creando domains_context.json nuevo debido a error de parseo.")
            try:
                await save_domains_context({})
            except Exception as save_err:
                logger.error("Error creando domains_context.json nuevo: %s", save_err, exc_info=True)
            raise
    if not isinstance(data, dict):
        return {}
    return data


async def save_domains_context(data: dict) -> None:
    """Guarda el contexto de dominios en disco usando escritura atómica.

    Args:
        data: Diccionario dominio -> {context, updated_at}.
    """
    path = Path(DOMAINS_CONTEXT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    async with _FILE_LOCK:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except OSError as e:
            logger.error("Error guardando domains_context.json: %s", e, exc_info=True)
            raise


async def get_domain_context(domain: str) -> str | None:
    """Obtiene el contexto persistido para un dominio.

    Args:
        domain: Dominio a consultar (ej: example.com).

    Returns:
        Contexto guardado o None si no existe.
    """
    if not domain:
        return None
    key = normalize_domain(domain)
    data = await load_domains_context()
    entry = data.get(key)
    if not entry or not isinstance(entry, dict):
        return None
    ctx = entry.get("context")
    return ctx if isinstance(ctx, str) else None


async def set_domain_context(domain: str, context: str) -> None:
    """Guarda o actualiza el contexto de un dominio.

    Trunca a MAX_CONTEXT_LENGTH caracteres si excede.

    Args:
        domain: Dominio donde guardar.
        context: Texto de contexto a persistir.
    """
    if not domain:
        return

    if len(context) > MAX_CONTEXT_LENGTH:
        logger.warning(
            "Contexto de dominio %s excede límite (%d > %d caracteres); truncando.",
            domain, len(context), MAX_CONTEXT_LENGTH
        )
        context = context[-MAX_CONTEXT_LENGTH:]

    key = normalize_domain(domain)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data = await load_domains_context()
    data[key] = {"context": context, "updated_at": now}
    await save_domains_context(data)
    logger.info("Contexto de dominio guardado: %s (%d caracteres)", key, len(context))


class DomainContextCache:
    """Caché de respuestas LLM para optimizar actualizaciones recursivas de contexto."""

    def __init__(self, enabled: bool = True, ttl_seconds: int = 3600):
        """Inicializa el caché.

        Args:
            enabled: Si False, el caché no almacena ni retorna resultados.
            ttl_seconds: Tiempo de vida en segundos antes de considerar expirado.
        """
        self._enabled = enabled
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[str, float]] = {}
    
    def compute_key(
        self,
        domain: str,
        existing_context: str | None,
        visit_history: str,
        conversation_or_task: str | None,
        judge_result: dict | None = None,
    ) -> str:
        """Calcula una clave de caché basada en los parámetros de actualización.

        Args:
            domain: Dominio actualizado.
            existing_context: Contexto previo del dominio.
            visit_history: Historial de visitas.
            conversation_or_task: Tarea o conversación relevante.
            judge_result: Resultado del Judge si aplica.

        Returns:
            Hash MD5 hexadecial de los parámetros concatenados.
        """
        parts = [
            domain,
            (existing_context or "").strip()[:_CACHE_KEY_LENGTHS["existing_context"]],
            (visit_history or "").strip()[:_CACHE_KEY_LENGTHS["visit_history"]],
            (conversation_or_task or "").strip()[:_CACHE_KEY_LENGTHS["conversation"]],
            str(judge_result is not None),
            json.dumps(judge_result, sort_keys=True)[:100] if judge_result else "",
        ]
        combined = "|".join(parts)
        return hashlib.md5(combined.encode("utf-8")).hexdigest()
    
    def get(self, cache_key: str) -> str | None:
        """Obtiene un resultado del caché si existe y no ha expirado.

        Args:
            cache_key: Clave calculada con compute_key.

        Returns:
            Contexto guardado o None si no existe o expiró.
        """
        if not self._enabled:
            return None
        cached = self._cache.get(cache_key)
        if cached is None:
            return None
        context_result, timestamp = cached
        now = time.time()
        if now - timestamp > self._ttl_seconds:
            del self._cache[cache_key]
            return None
        logger.debug("Cache hit para actualización de contexto (key: %s)", cache_key[:16])
        return context_result
    
    def set(self, cache_key: str, context_result: str) -> None:
        """Almacena un resultado en el caché con timestamp actual.

        Args:
            cache_key: Clave para recuperar después.
            context_result: Contexto generado por el LLM.
        """
        if not self._enabled:
            return
        self._cache[cache_key] = (context_result, time.time())
        logger.debug("Resultado almacenado en caché (key: %s)", cache_key[:16])


_cache_instance = DomainContextCache(
    enabled=DOMAIN_CONTEXT_CACHE_ENABLED,
    ttl_seconds=DOMAIN_CONTEXT_CACHE_TTL_S,
)


def _response_to_text(response: Any) -> str:
    """Extrae y normaliza el texto de la respuesta del LLM.

    Args:
        response: Objeto respuesta (completion, content o list de parts).

    Returns:
        Texto plano extraído.
    """
    raw = getattr(response, "completion", None) or getattr(response, "content", None)
    if raw is None:
        return str(response).strip()
    if isinstance(raw, list):
        return " ".join(str(getattr(part, "text", part)) for part in raw).strip()
    return str(raw).strip()


async def update_domain_context_async(
    existing_context: str | None,
    visit_history: str,
    llm: BaseChatModel,
    conversation_or_task: str | None = None,
    agent_history_summary: str | None = None,
    domain: str | None = None,
    judge_result: dict | None = None,
) -> str:
    """Actualiza recursivamente el contexto de un dominio usando un LLM.

    Usa plantilla domainContextUpdate.xml y puede servir desde caché.

    Args:
        existing_context: Contexto previo del dominio.
        visit_history: Historial de visitas en el dominio.
        llm: Modelo de lenguaje para generar la actualización.
        conversation_or_task: Tarea o conversación relevante.
        agent_history_summary: Resumen de URLs y errores del agente.
        domain: Dominio actualizado.
        judge_result: Evaluación del Judge si la tarea terminó.

    Returns:
        Contexto actualizado generado por el LLM.
    """
    trace_log(
        logger,
        "update_domain_context_async domain=%s existing_len=%d visit_history_len=%d",
        domain or "unknown",
        len(existing_context or ""),
        len(visit_history or ""),
    )
    cache_key = _cache_instance.compute_key(
        domain or "unknown",
        existing_context,
        visit_history,
        conversation_or_task,
        judge_result,
    )
    cached_result = _cache_instance.get(cache_key)
    if cached_result is not None:
        logger.info("Usando resultado del caché para actualización de contexto (dominio: %s)", domain)
        return cached_result

    template = load_domain_context_update_prompt()

    conversation_block = ""
    if (conversation_or_task or "").strip():
        conversation_block += (
            "Conversación / intención del usuario (tarea actual o mensajes relevantes):\n---\n"
            + (conversation_or_task or "").strip()
            + "\n---\n\n"
        )
    if (agent_history_summary or "").strip():
        conversation_block += (
            "Resumen del historial del agente (errores, resultados, URLs):\n---\n"
            + (agent_history_summary or "").strip()
            + "\n---\n"
        )

    judge_block = ""
    if judge_result and isinstance(judge_result, dict):
        verdict = judge_result.get("verdict", "")
        failure = (judge_result.get("failure_reason") or "")[:150]
        captcha = judge_result.get("reached_captcha", False)
        impossible = judge_result.get("impossible_task", False)
        reasoning = (str(judge_result.get("reasoning") or ""))[:200]
        extra = []
        if captcha:
            extra.append("Captcha: sí")
        if impossible:
            extra.append("Impossible: sí")
        judge_block = (
            "\n\nEvaluación del Judge (tarea ya terminó):\n---\n"
            f"Verdict: {verdict} | Failure: {failure}"
        )
        if extra:
            judge_block += " | " + " | ".join(extra)
        judge_block += "\n"
        if reasoning:
            judge_block += f"Reasoning: {reasoning}\n"
        judge_block += "---\n"

    prompt = template.format(
        existing=(existing_context or "").strip() or "(ninguno)",
        visit_history=(visit_history or "").strip() or "(sin pasos en este dominio)",
        conversation_block=conversation_block,
        judge_block=judge_block,
    )
    messages = [UserMessage(content=prompt)]
    
    try:
        response = await llm.ainvoke(messages)
        result = _response_to_text(response)
        _cache_instance.set(cache_key, result)
        trace_log(logger, "update_domain_context_async result_len=%d", len(result or ""))
        return result
    except Exception as e:
        logger.error("Error actualizando contexto de dominio: %s", e, exc_info=True)
        raise


class DomainContextController(Controller):
    """Controller que extiende browser-use con la herramienta get_domain_context.

    Registra la acción get_domain_context que el agente puede invocar para
    obtener el contexto acumulado del dominio actual.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        get_persisted_context = sys.modules[__name__].get_domain_context

        @self.registry.action(
            "Obtener contexto guardado del dominio actual. "
            "IMPORTANTE: Invoca ANTES de navegar a un dominio nuevo para prepararte con conocimiento acumulado. "
            "Si ya estás en un dominio nuevo, invócalo inmediatamente. "
            "Cada varios pasos en el mismo dominio, invócalo de nuevo para refrescar el contexto actualizado. "
            "El contexto incluye rutas optimizadas, problemas conocidos a evitar, y conocimiento previo que mejora iterativamente con cada visita.",
            param_model=NoParamsAction,
        )
        async def get_domain_context_tool(params: NoParamsAction, browser_session: BrowserSession):
            """Herramienta que permite al agente acceder al contexto acumulado de un dominio."""
            url = ""
            if browser_session:
                url = await browser_session.get_current_page_url() or ""
            domain = extract_domain(url)
            trace_log(logger, "get_domain_context INVOKED domain=%s", domain or "(none)")
            ctx = await get_persisted_context(domain) if domain else None
            has_context = bool(ctx and ctx.strip())
            trace_log(logger, "get_domain_context RETURN %s", f"len={len(ctx)}" if has_context else "NO_CONTEXT")
            text = ctx or NO_CONTEXT_MSG
            
            if ctx and ctx.strip():
                logger.info("Contexto de dominio cargado vía get_domain_context: %s", domain)
                return ActionResult(
                    extracted_content=text,
                    long_term_memory=CONTEXT_LOADED_LTM.format(domain=domain),
                    include_extracted_content_only_once=True,
                )
            return ActionResult(extracted_content=text)
