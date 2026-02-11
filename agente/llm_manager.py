"""
Gestión de instancias LLM para el agente recursivo de contexto.

Proporciona funciones para crear y gestionar instancias de modelos de lenguaje.
"""
import logging
from typing import Optional

from browser_use.llm.aws.chat_anthropic import ChatAnthropicBedrock
from browser_use.llm.aws.chat_bedrock import ChatAWSBedrock
from langchain_core.language_models.chat_models import BaseChatModel

from agente.config import AWS_REGION, BEDROCK_MODEL

logger = logging.getLogger(__name__)


def create_llm(model_name: str = BEDROCK_MODEL, region: str = AWS_REGION) -> BaseChatModel:
    """Crea una instancia del modelo LLM configurado.

    Usa ChatAnthropicBedrock para modelos anthropic con headers beta;
    ChatAWSBedrock para el resto.

    Args:
        model_name: Identificador del modelo en Bedrock (ej: us.anthropic.claude-haiku-...).
        region: Región AWS (ej: us-east-1).

    Returns:
        Instancia de BaseChatModel lista para invocar.
    """
    logger.info("Instanciando LLM: %s en %s", model_name, region)
    if "anthropic" in model_name.lower():
        return ChatAnthropicBedrock(
            model=model_name,
            aws_region=region,
            temperature=0.0,
            default_headers={
                "anthropic-beta": "computer-use-2025-01-24,context-management-2025-06-27",
            },
        )
    return ChatAWSBedrock(model=model_name, aws_region=region, temperature=0.0)


def ensure_llm(
    llm: Optional[BaseChatModel],
    page_extraction_llm: Optional[BaseChatModel],
) -> tuple[BaseChatModel, BaseChatModel]:
    """Inicializa los LLMs si no están creados.
    
    Args:
        llm: Instancia del LLM principal (puede ser None)
        page_extraction_llm: Instancia del LLM para extracción de página (puede ser None)
    
    Returns:
        Tupla con (llm_principal, llm_extraccion) ambos inicializados
    """
    if not llm:
        llm = create_llm()
    if not page_extraction_llm:
        page_extraction_llm = create_llm()
    return llm, page_extraction_llm
