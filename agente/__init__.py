"""
Paquete del agente recursivo de contexto para navegación web autónoma.

Implementa un sistema que acumula y actualiza conocimiento por dominio durante
la navegación, mejorando la eficiencia en visitas subsecuentes mediante
actualización recursiva de contexto usando LLM.

Ejemplo de uso:
    import asyncio
    from agente import create_agent_controller

    def on_message(role, content, status=None, color=None):
        print(f"[{role}] {content}")

    async def main():
        controller = create_agent_controller(on_message)
        try:
            await controller.reset_agent_async()
            result = await controller.run_task_async("Buscar información sobre X")
            print(result)
        finally:
            await controller.stop_async()

    asyncio.run(main())
"""
from typing import Any, Callable, Optional

from agente.agent import AgentController


def create_agent_controller(
    on_message: Callable[[str, str, Optional[str], Optional[str]], None],
    custom_controller: Any = None,
    browser_user_data_dir: Optional[str] = None,
) -> AgentController:
    """
    Crea una instancia del controlador del agente recursivo de contexto.
    
    Args:
        on_message: Callback para notificaciones de estado (role, content, status, color).
        custom_controller: Controller personalizado. Si es None, usa DomainContextController.
        browser_user_data_dir: Directorio de perfil del navegador. Si es None, usa el por defecto.
        
    Returns:
        Instancia de AgentController configurada y lista para usar.
    """
    return AgentController(
        on_message=on_message,
        custom_controller=custom_controller,
        browser_user_data_dir=browser_user_data_dir,
    )


__all__ = [
    "AgentController",
    "create_agent_controller",
]
