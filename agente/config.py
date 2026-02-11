"""
Configuración del agente recursivo de contexto.

Centraliza la configuración del sistema de contexto recursivo por dominio.
Las variables de entorno se cargan desde .env si existe (pydantic-settings).

NOTA: Versión de browser-use verificada: 0.11.9
- Verificado: 2026-02-09
- Documentación oficial consultada: https://docs.browser-use.com
- Código fuente instalado verificado en: venv/Lib/site-packages/browser_use/
- API verificada: Browser (alias de BrowserSession), Agent con timeouts en nivel Agent (no Browser)
"""
import logging
import os
from datetime import datetime

from utils.path_helpers import get_project_path

# ============================================================================
# Configuración AWS/Bedrock
# ============================================================================
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    
    class _AgenteSettings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )
        aws_region: str = "us-east-1"
        bedrock_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    
    _settings = _AgenteSettings()
    AWS_REGION = _settings.aws_region
    BEDROCK_MODEL = _settings.bedrock_model_id
except ImportError:
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

# ============================================================================
# Rutas y directorios
# ============================================================================
_AGENTE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_FILE = os.path.join(_AGENTE_DIR, "prompts", "mainPrompt.xml")
DOMAIN_CONTEXT_UPDATE_PROMPT_FILE = os.path.join(_AGENTE_DIR, "prompts", "domainContextUpdate.xml")
BROWSER_PROFILE_DIR = get_project_path("browser_profile")
DOMAINS_CONTEXT_PATH = get_project_path("logs/domains_context.json")
LOG_DIR = get_project_path("logs")

LOGS_DIR_NAME = "logs"
CONVERSATIONS_DIR_NAME = "logs/conversations"
HISTORY_FILE_NAME = "history.json"
FINAL_HISTORY_FILE_NAME = "final_history.json"
USAGE_FILE_NAME = "usage.json"

# ============================================================================
# Configuración del navegador
# ============================================================================
BROWSER_WINDOW_SIZE = {"width": 800, "height": 600}
# Posición de la ventana (x,y). Antes -3000,-3000 dejaba la ventana fuera de pantalla.
BROWSER_WINDOW_POSITION = os.getenv("BROWSER_WINDOW_POSITION", "100,100")
SCREENSHOT_TIMEOUT_S = float(os.getenv("SCREENSHOT_TIMEOUT_S", "30.0"))
# Timeout para arranque del navegador (browser-use lee TIMEOUT_BrowserStartEvent/TIMEOUT_BrowserLaunchEvent).
# En Windows puede exceder 30s por antivirus, primera descarga Chromium o disco lento.
BROWSER_LAUNCH_TIMEOUT_S = float(os.getenv("BROWSER_LAUNCH_TIMEOUT_S", "90.0"))

# Mitigación CDP ax_tree "Frame with the given frameId is not found" en sitios dinámicos (ej. Google).
# cross_origin_iframes=False reduce frames procesados; min/network_idle dan margen a la página.
CROSS_ORIGIN_IFRAMES = os.getenv("CROSS_ORIGIN_IFRAMES", "false").lower() in ("true", "1", "yes")
MAX_IFRAMES = int(os.getenv("MAX_IFRAMES", "5"))
MINIMUM_WAIT_PAGE_LOAD_TIME = float(os.getenv("MINIMUM_WAIT_PAGE_LOAD_TIME", "0.5"))
WAIT_FOR_NETWORK_IDLE_PAGE_LOAD_TIME = float(os.getenv("WAIT_FOR_NETWORK_IDLE_PAGE_LOAD_TIME", "1.0"))
WAIT_BETWEEN_ACTIONS = float(os.getenv("WAIT_BETWEEN_ACTIONS", "0.2"))

# ============================================================================
# Límites de ejecución del agente
# ============================================================================
MAX_HISTORY_ITEMS = int(os.getenv("MAX_HISTORY_ITEMS", "15"))
MAX_ACTIONS_PER_STEP = int(os.getenv("MAX_ACTIONS_PER_STEP", "3"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "30"))
THINKING_BUDGET_TOKENS = int(os.getenv("THINKING_BUDGET_TOKENS", "0"))
INCLUDE_ATTRIBUTES = None

# Justificación técnica: Máximo de fallos consecutivos antes de detener el agente.
# Evita bucles infinitos cuando el agente falla repetidamente en la misma acción.
# Valor recomendado: 3-5 para producción, 5-10 para desarrollo.
MAX_FAILURES = int(os.getenv("MAX_FAILURES", "10"))

# Justificación técnica: Timeout máximo por paso del agente (en segundos).
# Evita que un paso individual bloquee indefinidamente el agente.
# Valor recomendado: 180s (3 minutos) para tareas complejas.
STEP_TIMEOUT = int(os.getenv("STEP_TIMEOUT", "180"))

# Justificación técnica: Timeout para llamadas al LLM (en segundos).
# Si es None, se calcula automáticamente según el modelo.
# Valor recomendado: 90s para modelos grandes, 30-60s para modelos rápidos.
_llm_timeout_str = os.getenv("LLM_TIMEOUT", "").strip()
LLM_TIMEOUT = int(_llm_timeout_str) if _llm_timeout_str else None

# ============================================================================
# Configuración de contexto por dominio
# ============================================================================
DOMAIN_CONTEXT_REFRESH_STEPS = int(os.getenv("DOMAIN_CONTEXT_REFRESH_STEPS", "10"))
MAX_VISIT_HISTORY_STEPS = int(os.getenv("MAX_VISIT_HISTORY_STEPS", "20"))
DOMAIN_CONTEXT_MIN_STEPS_FOR_UPDATE = int(os.getenv("DOMAIN_CONTEXT_MIN_STEPS_FOR_UPDATE", "3"))
DOMAIN_CONTEXT_CACHE_ENABLED = os.getenv("DOMAIN_CONTEXT_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
DOMAIN_CONTEXT_CACHE_TTL_S = int(os.getenv("DOMAIN_CONTEXT_CACHE_TTL_S", "3600"))
# Justificación técnica: Máximo de caracteres para contexto de dominio persistido.
# Dominios con mucho historial (vogue, harpersbazaar) pueden producir 1350-1772 caracteres.
# Valor recomendado: 1500-2000 para reducir truncados; 1000 era insuficiente.
MAX_CONTEXT_LENGTH = int(os.getenv("DOMAIN_CONTEXT_MAX_LENGTH", "2000"))

# ============================================================================
# Visión (browser-use)
# ============================================================================
# Visión: True para elementos no-DOM (mapas, canvas, video); False para solo DOM.
# Regla llm-haiku-bedrock: 'low' para navegación, 'high' solo extracción visual.
USE_VISION = os.getenv("USE_VISION", "true").lower() in ("true", "1", "yes")
VISION_DETAIL_LEVEL = os.getenv("VISION_DETAIL_LEVEL", "low")  # 'auto' | 'low' | 'high'

# ============================================================================
# Compactación de historial (MessageCompactionSettings)
# ============================================================================
# Default browser-use: trigger_char_count=40000 (~10k tokens).
# Ajustado para Haiku con MAX_STEPS=30: trigger más temprano evita saturar.
MESSAGE_COMPACTION_ENABLED = os.getenv("MESSAGE_COMPACTION_ENABLED", "true").lower() in ("true", "1", "yes")
MESSAGE_COMPACTION_COMPACT_EVERY_N_STEPS = int(os.getenv("MESSAGE_COMPACTION_COMPACT_EVERY_N_STEPS", "12"))
MESSAGE_COMPACTION_TRIGGER_CHAR_COUNT = int(os.getenv("MESSAGE_COMPACTION_TRIGGER_CHAR_COUNT", "20000"))
MESSAGE_COMPACTION_KEEP_LAST_ITEMS = int(os.getenv("MESSAGE_COMPACTION_KEEP_LAST_ITEMS", "6"))
MESSAGE_COMPACTION_SUMMARY_MAX_CHARS = int(os.getenv("MESSAGE_COMPACTION_SUMMARY_MAX_CHARS", "6000"))

# ============================================================================
# Modos de operación
# ============================================================================
FLASH_MODE = os.getenv("FLASH_MODE", "false").lower() in ("true", "1", "yes")
CALCULATE_COST = os.getenv("CALCULATE_COST", "false").lower() in ("true", "1", "yes")
# Por defecto false: el fallo debe ser visible para debug (integridad-tecnica).
SUPPRESS_EXPECTED_CDP_ERRORS = os.getenv("SUPPRESS_EXPECTED_CDP_ERRORS", "false").lower() in ("true", "1", "yes")

# Desactiva navegación automática a la primera URL detectada en la tarea.
# Con False: el agente arranca en about:blank y el LLM decide la ruta.
# Evita ERR_ABORTED en sitios que bloquean bots (ej. whowhatwear.com).
DIRECTLY_OPEN_URL = os.getenv("DIRECTLY_OPEN_URL", "false").lower() in ("true", "1", "yes")

# ============================================================================
# Detección de bucles (browser-use ActionLoopDetector)
# ============================================================================
# Delegamos exclusivamente al mecanismo nativo de browser-use: nudges al LLM
# en repetición de acciones y estancamiento de página. No bloquea; el LLM decide.
LOOP_DETECTION_ENABLED = os.getenv("LOOP_DETECTION_ENABLED", "true").lower() in ("true", "1", "yes")
LOOP_DETECTION_WINDOW = int(os.getenv("LOOP_DETECTION_WINDOW", "5"))

# ============================================================================
# Timeouts y esperas
# ============================================================================
# Justificación técnica: Tiempo máximo para esperar que un reset del agente se complete.
# Debe ser >= BROWSER_LAUNCH_TIMEOUT_S + margen para cerrar browser y limpiar recursos.
# Configurable vía MAX_RESET_WAIT_TIME; default deriva de BROWSER_LAUNCH_TIMEOUT_S.
_reset_wait = os.getenv("MAX_RESET_WAIT_TIME", "").strip()
MAX_RESET_WAIT_TIME = float(_reset_wait) if _reset_wait else max(60.0, BROWSER_LAUNCH_TIMEOUT_S + 15.0)

# Justificación técnica: Intervalo mínimo para polling sin causar CPU spinning.
# Usado en _wait_for_task_completion_async para verificar is_task_running.
# 0.1s es un balance entre responsividad y eficiencia de CPU.
RESET_WAIT_INTERVAL = 0.1

# ============================================================================
# Configuración de logging y trazas
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
# Si True: trazas se emiten a nivel INFO. Si False: trazas a nivel DEBUG (visibles con LOG_LEVEL=DEBUG).
TRACE_AGENT = os.getenv("TRACE_AGENT", "false").lower() in ("true", "1", "yes")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ============================================================================
# Señales del sistema
# ============================================================================
RESET_SIGNAL = "__RESET__"

# ============================================================================
# Mensajes del sistema
# ============================================================================
MSG_CANCELLING = "Solicitando cancelación..."
MSG_CANCELLED = "Cancelando..."
MSG_TASK_INTERRUPTED = "Tarea interrumpida"
MSG_TASK_CANCELLED = "Tarea cancelada"
MSG_RESET_TIMEOUT = f"Timeout en reset del agente después de {int(MAX_RESET_WAIT_TIME)}s"
MSG_RESET_WARNING = "Advertencia"

CONTEXT_LOADED_LTM = "Contexto de {domain} cargado."
NO_CONTEXT_MSG = "No hay contexto guardado para este dominio."

# ============================================================================
# Colores y formato
# ============================================================================
COLOR_ERROR = "#e74c3c"
COLOR_SUCCESS = "#2ecc71"
COLOR_WARNING = "#f39c12"
COLOR_THINKING = "#9b59b6"
CONSOLE_SEPARATOR_LENGTH = 60

# ============================================================================
# Funciones de carga de prompts
# ============================================================================
def _load_prompt_file(file_path: str) -> str:
    """Carga un archivo de prompt y reemplaza la fecha actual.

    Args:
        file_path: Ruta absoluta al archivo de prompt (XML).

    Returns:
        Contenido del archivo con {current_date} sustituido por la fecha actual.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    current_date = datetime.now().strftime("%Y-%m-%d")
    return content.replace("{current_date}", current_date)


def load_system_prompt() -> str:
    """Carga el prompt del sistema desde el archivo XML.

    Returns:
        Contenido del prompt principal (mainPrompt.xml).
    """
    return _load_prompt_file(PROMPT_FILE)


def load_domain_context_update_prompt() -> str:
    """Carga el template XML para actualización recursiva de contexto por dominio.

    Returns:
        Contenido del template domainContextUpdate.xml.
    """
    return _load_prompt_file(DOMAIN_CONTEXT_UPDATE_PROMPT_FILE)


def trace_log(logger_instance: logging.Logger, msg: str, *args, **kwargs) -> None:
    """Emite traza: INFO si TRACE_AGENT=true, DEBUG si no.

    El mensaje se precede con [TRACE] para facilitar filtrado.

    Args:
        logger_instance: Logger donde emitir la traza.
        msg: Plantilla del mensaje (puede tener %s, %d, etc.).
        *args: Argumentos para formatear la plantilla.
        **kwargs: Argumentos adicionales para el método de logging.
    """
    full_msg = f"[TRACE] {msg}"
    if TRACE_AGENT:
        logger_instance.info(full_msg, *args, **kwargs)
    else:
        logger_instance.debug(full_msg, *args, **kwargs)
