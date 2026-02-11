"""
Punto de entrada principal del agente recursivo de contexto.
Programa de consola para demostración académica.

Flujo async mono-hilo: sin threading ni time.sleep.
main.py: solo lee tasks.json, invoca al agente y muestra output.
"""
import asyncio
import logging
from typing import Any

from agente import create_agent_controller
from agente.config import (
    CONSOLE_SEPARATOR_LENGTH,
    LOG_BACKUP_COUNT,
    LOG_DIR,
    LOG_LEVEL,
    LOG_MAX_BYTES,
)
from tasks import get_default_tasks
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def on_message(role: str, content: str, status: str | None = None, color: str | None = None) -> None:
    """Callback para mostrar mensajes del agente en consola.

    Args:
        role: Rol del emisor (ej: 'agent', 'system').
        content: Contenido del mensaje.
        status: Estado opcional que se muestra entre corchetes.
        color: Color opcional para la salida (no usado en consola).
    """
    status_str = f" [{status}]" if status else ""
    print(f"[{role}]{status_str} {content}")


def print_section_header(title: str) -> None:
    """Imprime un encabezado de sección con separadores.

    Args:
        title: Título a mostrar entre líneas de separación.
    """
    separator = "=" * CONSOLE_SEPARATOR_LENGTH
    print(f"\n{separator}")
    print(title)
    print(f"{separator}\n")


def print_summary(market_intelligence_data: list[dict[str, Any]]) -> None:
    """Imprime un resumen final de las entidades recopiladas.

    Args:
        market_intelligence_data: Lista de entidades extraídas con campo signal_type.
    """
    print_section_header("RESUMEN FINAL")
    print(f"Total de entidades recopiladas: {len(market_intelligence_data)}")

    signal_counts: dict[str, int] = {}
    for entity in market_intelligence_data:
        signal_type = entity.get("signal_type", "unknown")
        signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1

    print("\nEntidades por tipo de señal:")
    for signal_type, count in signal_counts.items():
        print(f"  - {signal_type}: {count}")

    print_section_header("Proceso completado.")


async def main_async() -> None:
    """Función principal async del programa de consola.

    Configura logging, carga tareas, ejecuta el agente y muestra el resumen.
    Maneja KeyboardInterrupt y CancelledError para limpieza correcta.
    """
    try:
        setup_logging(
            log_level=LOG_LEVEL,
            log_dir=LOG_DIR,
            max_bytes=LOG_MAX_BYTES,
            backup_count=LOG_BACKUP_COUNT,
        )
        logger.info("Iniciando agente recursivo de contexto")
    except Exception as e:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        logger.error("Error configurando logging: %s", e)

    controller = create_agent_controller(on_message)
    tasks = get_default_tasks()

    try:
        print_section_header("Recursive Context Agent - Recopilación de Inteligencia de Mercado")
        print(f"Ejecutando {len(tasks)} tareas secuenciales...\n")

        results = await controller.run_tasks_async(tasks)
        print_summary(results)

    except KeyboardInterrupt:
        logger.info("Interrupción del usuario detectada")
        print("\n\nInterrupción del usuario. Cancelando tareas...")
        await controller.cancel_task_async()
    except asyncio.CancelledError:
        logger.info("Tarea cancelada")
        await controller.cancel_task_async()
    finally:
        logger.info("Deteniendo agente...")
        print("\nDeteniendo agente...")
        await controller.stop_async()


def main() -> None:
    """Punto de entrada síncrono; ejecuta el loop async.

    Invoca asyncio.run(main_async()) para ejecutar el flujo completo.
    """
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
