"""
Utilidades para manejo de paths del proyecto.
Consolida la lógica común de construcción de rutas relativas al proyecto.
"""
import os


def get_project_path(relative_path: str) -> str:
    """
    Obtiene la ruta absoluta de un archivo o directorio relativo al proyecto.
    
    Args:
        relative_path: Ruta relativa desde la raíz del proyecto (ej: "docs", "agente/prompts/mainPrompt.xml")
    
    Returns:
        Ruta absoluta combinando la raíz del proyecto con la ruta relativa
    
    Ejemplo:
        >>> get_project_path("docs")
        '/path/to/project/docs'
        >>> get_project_path("agente/prompts/mainPrompt.xml")
        '/path/to/project/agente/prompts/mainPrompt.xml'
    """
    # Obtener el directorio base del proyecto (dos niveles arriba de utils/)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, relative_path)
