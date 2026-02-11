"""
Extracción de datos estructurados del historial del agente.

Proporciona funciones para parsear el historial y extraer entidades estructuradas.
"""
import json
import logging
import re
from typing import Any

from schemas import (
    CommercialTrendSchema,
    ContextTriggerSchema,
    FashionEventSchema,
    MediaTrendSchema,
    SearchInsightSchema,
    SearchTrendSchema,
    commercial_trend_to_entity_dict,
    context_trigger_to_entity_dict,
    fashion_event_to_entity_dict,
    media_trend_to_entity_dict,
    search_insight_to_entity_dict,
    search_trend_to_entity_dict,
)

logger = logging.getLogger(__name__)


def extract_structured_data_from_history(history: Any) -> list[dict[str, Any]]:
    """Extrae datos estructurados del historial del agente.

    Parsea action_results del historial, aplica esquemas Pydantic y convierte
    a entidades MarketIntelligenceEntity compatibles.

    Args:
        history: Objeto de historial con action_results() (browser-use).

    Returns:
        Lista de diccionarios con entidades extraídas (signal_type, source_url, etc.).
    """
    entities = []
    
    if not history:
        logger.warning("Historial vacío o None")
        return entities
    
    # Obtener todos los resultados de acciones
    try:
        action_results = history.action_results() if hasattr(history, 'action_results') else []
    except Exception as e:
        logger.warning(f"Error obteniendo action_results: {e}")
        action_results = []
    
    logger.info(f"Procesando {len(action_results)} resultados de acciones")
    
    for idx, result in enumerate(action_results):
        if not result:
            continue
        
        source_url = ''
        data = None
        
        # Método 1: Intentar obtener de metadata (más confiable)
        try:
            metadata = getattr(result, 'metadata', None)
            if metadata and isinstance(metadata, dict) and metadata.get('structured_extraction'):
                extraction_result = metadata.get('extraction_result', {})
                if isinstance(extraction_result, dict):
                    data = extraction_result.get('data', {})
                    source_url = extraction_result.get('source_url', '')
        except Exception as e:
            logger.debug(f"Error obteniendo metadata del resultado {idx}: {e}")
        
        # Método 2: Si no hay metadata, intentar extraer de extracted_content
        if not data:
            try:
                extracted_content = getattr(result, 'extracted_content', None)
                if extracted_content and isinstance(extracted_content, str):
                    # Buscar structured_result
                    if '<structured_result>' in extracted_content:
                        match = re.search(r'<structured_result>\s*(.*?)\s*</structured_result>', extracted_content, re.DOTALL)
                        if match:
                            json_str = match.group(1).strip()
                            try:
                                data = json.loads(json_str)
                                # Extraer URL
                                url_match = re.search(r'<url>\s*(.*?)\s*</url>', extracted_content)
                                source_url = url_match.group(1).strip() if url_match else ''
                            except json.JSONDecodeError as e:
                                logger.debug(f"Error parseando JSON del resultado {idx}: {e}")
                                # Intentar extraer JSON directamente del texto si no está en tags
                                try:
                                    json_match = re.search(
                                        r'\{[\s\S]*"(?:trends|events|search_insights|context_triggers)"[\s\S]*\}',
                                        extracted_content
                                    )
                                    if json_match:
                                        data = json.loads(json_match.group(0))
                                except json.JSONDecodeError as e2:
                                    logger.debug(f"Fallback JSON inválido en resultado {idx}: {e2}")
                                except Exception as e2:
                                    logger.debug(f"Error en fallback de extracción JSON: {e2}", exc_info=True)
                    # Si no hay structured_result, buscar JSON directamente
                    elif '{' in extracted_content and any(
                        k in extracted_content for k in ('"trends"', '"events"', '"search_insights"', '"context_triggers"')
                    ):
                        try:
                            json_match = re.search(r'\{[\s\S]*\}', extracted_content)
                            if json_match:
                                data = json.loads(json_match.group(0))
                        except json.JSONDecodeError as e:
                            logger.debug(f"Error parseando JSON directo del resultado {idx}: {e}")
                        except Exception as e:
                            logger.debug(f"Error procesando JSON directo del resultado {idx}: {e}", exc_info=True)
            except Exception as e:
                logger.debug(f"Error procesando extracted_content del resultado {idx}: {e}")
        
        # Procesar datos si se encontraron
        if data and isinstance(data, dict):
            try:
                # Determinar tipo de esquema y parsear
                if 'trends' in data and isinstance(data['trends'], list) and len(data['trends']) > 0:
                    # Verificar tipo de esquema en orden: SearchTrend → CommercialTrend → MediaTrend
                    first_item = data['trends'][0]
                    if isinstance(first_item, dict) and 'trend_score' in first_item:
                        # Es SearchTrendSchema
                        try:
                            schema = SearchTrendSchema(**data)
                            for trend in schema.trends:
                                entity_dict = search_trend_to_entity_dict(trend, source_url)
                                entities.append(entity_dict)
                            logger.debug(f"Procesadas {len(schema.trends)} tendencias de búsqueda")
                        except Exception as e:
                            logger.warning(f"Error parseando SearchTrendSchema: {e}")
                    elif isinstance(first_item, dict) and 'garment_type' in first_item:
                        # Es CommercialTrendSchema
                        try:
                            schema = CommercialTrendSchema(**data)
                            for trend in schema.trends:
                                entity_dict = commercial_trend_to_entity_dict(trend, source_url)
                                entities.append(entity_dict)
                            logger.debug(f"Procesadas {len(schema.trends)} tendencias comerciales")
                        except Exception as e:
                            logger.warning(f"Error parseando CommercialTrendSchema: {e}")
                    else:
                        # Es MediaTrendSchema (tiene title)
                        try:
                            schema = MediaTrendSchema(**data)
                            source_platform = 'vogue' if 'vogue' in source_url.lower() else 'elle' if 'elle' in source_url.lower() else ''
                            for trend in schema.trends:
                                entity_dict = media_trend_to_entity_dict(trend, source_url, source_platform)
                                entities.append(entity_dict)
                            logger.debug(f"Procesadas {len(schema.trends)} tendencias de medios")
                        except Exception as e:
                            logger.warning(f"Error parseando MediaTrendSchema: {e}")
                
                elif 'events' in data and isinstance(data['events'], list) and len(data['events']) > 0:
                    # Es FashionEventSchema
                    try:
                        schema = FashionEventSchema(**data)
                        for event in schema.events:
                            entity_dict = fashion_event_to_entity_dict(event, source_url)
                            entities.append(entity_dict)
                        logger.debug(f"Procesados {len(schema.events)} eventos")
                    except Exception as e:
                        logger.warning(f"Error parseando FashionEventSchema: {e}")

                elif 'search_insights' in data and isinstance(data['search_insights'], list) and len(data['search_insights']) > 0:
                    # Es SearchInsightSchema (Tarea 2)
                    try:
                        schema = SearchInsightSchema(**data)
                        for insight in schema.search_insights:
                            entity_dict = search_insight_to_entity_dict(insight, source_url)
                            entities.append(entity_dict)
                        logger.debug(f"Procesados {len(schema.search_insights)} insights de búsqueda")
                    except Exception as e:
                        logger.warning(f"Error parseando SearchInsightSchema: {e}")

                elif 'context_triggers' in data and isinstance(data['context_triggers'], list) and len(data['context_triggers']) > 0:
                    # Es ContextTriggerSchema (Tarea 3)
                    try:
                        schema = ContextTriggerSchema(**data)
                        for trigger in schema.context_triggers:
                            entity_dict = context_trigger_to_entity_dict(trigger, source_url)
                            entities.append(entity_dict)
                        logger.debug(f"Procesados {len(schema.context_triggers)} triggers contextuales")
                    except Exception as e:
                        logger.warning(f"Error parseando ContextTriggerSchema: {e}")
                
            except Exception as e:
                logger.warning(f"Error procesando datos estructurados del resultado {idx}: {e}")
                logger.debug(f"Datos que causaron error: {json.dumps(data, indent=2, default=str)[:500]}")
                continue
    
    logger.info(f"Total de entidades extraídas: {len(entities)}")
    return entities
