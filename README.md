# Agente recursivo de contexto

Agente de navegación web autónoma basado en [browser-use](https://docs.browser-use.com) y Claude Haiku 4.5 (AWS Bedrock). Implementa un **sistema de contexto recursivo por dominio**: acumula y actualiza conocimiento durante la navegación para mejorar la eficiencia en visitas subsecuentes.

## Requisitos

- **Python 3.11+**
- **AWS Bedrock** configurado (Claude Haiku 4.5 u otros modelos compatibles)
- Credenciales AWS en el entorno o `.env`
- Navegador Chromium (instalado vía Playwright)

## Instalación

1. Crear y activar entorno virtual:

```bash
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configurar variables de entorno (crear `.env` en la raíz):

```env
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
LOG_LEVEL=INFO
```

## Uso

### Ejecución por consola

```bash
python main.py
```

Lee las tareas desde `tasks/tasks.json`, las ejecuta secuencialmente y muestra el resumen de entidades extraídas.

### Uso programático

```python
import asyncio
from agente import create_agent_controller

def on_message(role, content, status=None, color=None):
    print(f"[{role}] {content}")

async def main():
    controller = create_agent_controller(on_message)
    try:
        result = await controller.run_task_async("Buscar tendencias de moda en Vogue")
        print(result)
    finally:
        await controller.stop_async()

asyncio.run(main())
```

## Estructura del proyecto

```
.
├── main.py              # Punto de entrada (lee tasks, invoca agente, muestra output)
├── schemas.py           # Esquemas Pydantic para extracción estructurada
├── agente/              # Motor del agente
│   ├── agent.py         # AgentController: orquestación y ciclo de vida
│   ├── browser_manager.py
│   ├── config.py        # Configuración centralizada
│   ├── domain_context.py    # Contexto recursivo por dominio
│   ├── domain_tracker.py    # Tracking de visitas y actualización de contexto
│   ├── error_handler.py
│   ├── history_manager.py
│   ├── llm_manager.py
│   ├── task_processor.py
│   └── prompts/         # Plantillas XML (mainPrompt, domainContextUpdate)
├── tasks/
│   ├── tasks.json       # Definiciones de tareas
│   ├── data_extractor.py
│   └── __init__.py
├── utils/
│   ├── logging_config.py
│   └── path_helpers.py
├── docs_dev/            # Documentación para desarrolladores
│   ├── arquitectura.md
│   └── fallos_conocidos.md
└── logs/                # Historial, dominios_context.json (generados)
```

## Configuración

Principales variables de entorno (ver `agente/config.py`):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `AWS_REGION` | us-east-1 | Región AWS Bedrock |
| `BEDROCK_MODEL_ID` | us.anthropic.claude-haiku-4-5-... | Modelo LLM |
| `LOG_LEVEL` | INFO | Nivel de logging |
| `MAX_STEPS` | 30 | Pasos máximos por tarea |
| `BROWSER_LAUNCH_TIMEOUT_S` | 90 | Timeout de arranque del navegador |
| `STEP_TIMEOUT` | 180 | Timeout por paso del agente (s) |
| `MAX_HISTORY_ITEMS` | 15 | Ítems de historial enviados al LLM |
| `USE_VISION` | true | Usar visión para elementos no-DOM |

## Referencias

- [Documentación oficial browser-use](https://docs.browser-use.com)
- Reglas y contexto del proyecto en `.cursor/rules/`
- Arquitectura técnica en [docs_dev/arquitectura.md](docs_dev/arquitectura.md)
