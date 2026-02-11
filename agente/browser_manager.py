"""
Gestión del ciclo de vida del navegador para el agente recursivo de contexto.

Proporciona funciones para inicializar, cerrar y gestionar el navegador.

NOTA: Verificación de documentación oficial browser-use 0.11.9:
- Browser y BrowserSession son la misma clase (verificado: Browser == BrowserSession es True)
- Browser es el alias recomendado en la API más reciente (verificado en agent/service.py línea 141)
- Timeouts se configuran en nivel Agent, no Browser (verificado en documentación y código)
- Browser no acepta parámetros de timeout directamente - se pasan al Agent
- La regla browser-use/configuracion.mdc muestra BrowserSession pero Browser es equivalente y preferido
"""
import logging
import os
from typing import Optional

from browser_use import Browser

from agente.config import (
    BROWSER_LAUNCH_TIMEOUT_S,
    BROWSER_PROFILE_DIR,
    BROWSER_WINDOW_SIZE,
    BROWSER_WINDOW_POSITION,
    CROSS_ORIGIN_IFRAMES,
    MAX_IFRAMES,
    MINIMUM_WAIT_PAGE_LOAD_TIME,
    SCREENSHOT_TIMEOUT_S,
    WAIT_BETWEEN_ACTIONS,
    WAIT_FOR_NETWORK_IDLE_PAGE_LOAD_TIME,
)

logger = logging.getLogger(__name__)


async def init_browser_async(
    browser_user_data_dir: Optional[str] = None,
) -> Browser:
    """Inicializa el navegador con la configuración adecuada.
    
    Args:
        browser_user_data_dir: Directorio de datos del usuario del navegador.
                              Si es None, usa BROWSER_PROFILE_DIR.
    
    Returns:
        Instancia del navegador inicializado.
    """
    try:
        # Configurar timeouts de browser-use antes de browser.start()
        # (se leen al instanciar eventos; default 30s insuficiente en Windows)
        os.environ['TIMEOUT_ScreenshotEvent'] = str(SCREENSHOT_TIMEOUT_S)
        os.environ['TIMEOUT_BrowserStartEvent'] = str(BROWSER_LAUNCH_TIMEOUT_S)
        os.environ['TIMEOUT_BrowserLaunchEvent'] = str(BROWSER_LAUNCH_TIMEOUT_S)
        logger.debug(
            f"Configurados timeouts: Screenshot={SCREENSHOT_TIMEOUT_S}s, "
            f"BrowserStart/BrowserLaunch={BROWSER_LAUNCH_TIMEOUT_S}s"
        )
        
        user_data_dir = browser_user_data_dir if browser_user_data_dir else BROWSER_PROFILE_DIR
        
        browser = Browser(
            headless=False,
            keep_alive=True,
            args=[f"--window-position={BROWSER_WINDOW_POSITION}"],
            window_size=BROWSER_WINDOW_SIZE,
            user_data_dir=user_data_dir,
            highlight_elements=True,
            paint_order_filtering=True,
            cross_origin_iframes=CROSS_ORIGIN_IFRAMES,
            max_iframes=MAX_IFRAMES,
            max_iframe_depth=5,
            minimum_wait_page_load_time=MINIMUM_WAIT_PAGE_LOAD_TIME,
            wait_for_network_idle_page_load_time=WAIT_FOR_NETWORK_IDLE_PAGE_LOAD_TIME,
            wait_between_actions=WAIT_BETWEEN_ACTIONS,
        )
        await browser.start()
        logger.info("Navegador inicializado correctamente")
        # #region agent log
        try:
            import json
            with open(r"c:\Users\anuez2\Downloads\browser-use_AGENTE_v2\.cursor\debug.log", "a", encoding="utf-8") as _dbg:
                _dbg.write(json.dumps({"id":"log_init_browser","timestamp":__import__("time").time()*1000,"location":"browser_manager.py:init_browser_async","message":"Browser started","data":{"window_position":BROWSER_WINDOW_POSITION,"window_size":BROWSER_WINDOW_SIZE},"hypothesisId":"H1","runId":"post-fix"}) + "\n")
        except Exception:
            pass
        # #endregion
        return browser
    except Exception as e:
        logger.error(f"Fallo al iniciar navegador: {e}", exc_info=True)
        raise


async def close_browser_async(browser: Optional[Browser]) -> None:
    """Cierra el navegador de manera segura.
    
    Args:
        browser: Instancia del navegador a cerrar (puede ser None).
    """
    if browser:
        try:
            # #region agent log
            try:
                import json
                with open(r"c:\Users\anuez2\Downloads\browser-use_AGENTE_v2\.cursor\debug.log", "a", encoding="utf-8") as _dbg:
                    _dbg.write(json.dumps({"id":"log_close_before","timestamp":__import__("time").time()*1000,"location":"browser_manager.py:close_browser_async","message":"Closing browser","data":{},"hypothesisId":"H2"}) + "\n")
            except Exception:
                pass
            # #endregion
            await browser.stop()
            logger.info("Browser cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando browser: {e}", exc_info=True)
            raise


async def ensure_browser_ready(
    browser: Optional[Browser],
    browser_user_data_dir: Optional[str] = None,
) -> Browser:
    """Asegura que el navegador esté inicializado, creándolo si no existe.
    
    Args:
        browser: Instancia del navegador actual (puede ser None).
        browser_user_data_dir: Directorio de datos del usuario del navegador.
    
    Returns:
        Instancia del navegador (existente o recién creado).
    """
    if not browser:
        logger.info("Navegador no inicializado, inicializando...")
        # #region agent log
        try:
            import json
            with open(r"c:\Users\anuez2\Downloads\browser-use_AGENTE_v2\.cursor\debug.log", "a", encoding="utf-8") as _dbg:
                _dbg.write(json.dumps({"id":"log_ensure_create","timestamp":__import__("time").time()*1000,"location":"browser_manager.py:ensure_browser_ready","message":"Creating new browser (was None)","data":{},"hypothesisId":"H3"}) + "\n")
        except Exception:
            pass
        # #endregion
        browser = await init_browser_async(browser_user_data_dir)
    return browser
