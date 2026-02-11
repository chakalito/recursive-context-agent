"""
Esquemas Pydantic para extracción estructurada de datos de inteligencia de mercado.
Estos esquemas se usan con browser_use extract() para obtener datos estructurados.
"""
import uuid
import time
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class MediaTrendItem(BaseModel):
    """Item individual de tendencia de moda de revistas."""
    title: str = Field(description="Título del artículo o tendencia")
    description: str = Field(default="", description="Descripción de la tendencia")
    keywords: list[str] = Field(default_factory=list, description="Palabras clave relacionadas")
    source_url: str = Field(default="", description="URL del artículo")
    source_platform: str = Field(default="", description="Plataforma (vogue, elle, etc.)")
    risk_impact: float = Field(default=0.0, ge=0.0, le=1.0, description="Impacto en demanda (0.0-1.0)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confianza en la información (0.0-1.0)")
    affected_categories: list[str] = Field(default_factory=list, description="Categorías de productos afectadas")


class MediaTrendSchema(BaseModel):
    """Esquema para extraer tendencias de moda de revistas (Vogue, Elle)."""
    trends: list[MediaTrendItem] = Field(description="Lista de tendencias encontradas")


class SearchTrendItem(BaseModel):
    """Item individual de tendencia de búsqueda de Google Trends."""
    keyword: str = Field(description="Palabra clave buscada")
    trend_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Índice de Google Trends (0-100)")
    trend_change_pct: float = Field(default=0.0, description="Cambio porcentual semana a semana")
    description: str = Field(default="", description="Descripción de la tendencia")
    source_url: str = Field(default="", description="URL de Google Trends")
    risk_dates: list[str] = Field(default_factory=list, description="Fechas de mayor riesgo (YYYY-MM-DD)")
    affected_categories: list[str] = Field(default_factory=list, description="Categorías de productos afectadas")
    estimated_demand_increase_pct: float = Field(default=0.0, description="Incremento estimado de demanda (%)")


class SearchTrendSchema(BaseModel):
    """Esquema para extraer tendencias de Google Trends."""
    trends: list[SearchTrendItem] = Field(description="Lista de tendencias de búsqueda encontradas")


class FashionEventItem(BaseModel):
    """Item individual de evento de moda."""
    title: str = Field(description="Nombre del evento")
    description: str = Field(default="", description="Descripción del evento")
    event_date: Optional[str] = Field(default=None, description="Fecha del evento (YYYY-MM-DD o timestamp)")
    event_end_date: Optional[str] = Field(default=None, description="Fecha de fin del evento (YYYY-MM-DD o timestamp)")
    location: str = Field(default="", description="Ubicación del evento (ciudad, venue, o 'online')")
    event_status: str = Field(default="active", description="Estado: active, postponed, cancelled, completed")
    keywords: list[str] = Field(default_factory=list, description="Palabras clave relacionadas")
    source_url: str = Field(default="", description="URL de información del evento")
    risk_impact: float = Field(default=0.0, ge=0.0, le=1.0, description="Impacto en demanda (0.0-1.0)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confianza en la información (0.0-1.0)")
    affected_categories: list[str] = Field(default_factory=list, description="Categorías de productos afectadas")
    estimated_demand_increase_pct: float = Field(default=0.0, description="Incremento estimado de demanda (%)")


class FashionEventSchema(BaseModel):
    """Esquema para extraer eventos de moda cercanos."""
    events: list[FashionEventItem] = Field(description="Lista de eventos encontrados")


class CommercialTrendItem(BaseModel):
    """Item individual de tendencia comercial de moda (Street Style, viral trends)."""
    garment_type: str = Field(description="Tipo de prenda (ej: 'cargo pants', 'baby tee', 'sneaker')")
    attributes: list[str] = Field(default_factory=list, description="Atributos: colores, telas, estampados")
    style_vibe: str = Field(default="", description="Estilo o vibe (ej: 'Y2K', 'Old Money')")
    source_url: str = Field(default="", description="URL del artículo fuente")
    urgency_level: float = Field(default=0.0, ge=0.0, le=1.0, description="Nivel de urgencia basado en viralidad (0.0-1.0)")
    zara_category_match: str = Field(default="", description="Categoría ZARA correspondiente: 'Woman', 'TRF', 'Man', 'Kids'")


class CommercialTrendSchema(BaseModel):
    """Esquema para extraer tendencias comerciales de moda (viral trends, street style)."""
    trends: list[CommercialTrendItem] = Field(description="Lista de tendencias comerciales encontradas")


class SearchInsightItem(BaseModel):
    """Item individual de insight de búsqueda (Google Trends, términos en ascenso)."""
    query: str = Field(description="Término de búsqueda")
    growth_status: str = Field(default="", description="Estado de crecimiento (ej: 'Breakout', '+300%')")
    implied_product: str = Field(default="", description="Prenda física que busca el usuario")
    suggested_action: str = Field(default="", description="Acción sugerida (ej: 'Mover al frente de tienda')")
    related_keywords: list[str] = Field(default_factory=list, description="Palabras clave relacionadas")


class SearchInsightSchema(BaseModel):
    """Esquema para extraer insights de búsqueda (Tarea 2: Google Trends)."""
    search_insights: list[SearchInsightItem] = Field(description="Lista de insights de búsqueda")


class ContextTriggerItem(BaseModel):
    """Item individual de trigger contextual (clima, evento social)."""
    trigger_type: str = Field(description="Tipo: 'Weather' o 'Event'")
    detail: str = Field(default="", description="Detalle (ej: 'Lluvia intensa', 'Festival Coachella')")
    date_range: str = Field(default="", description="Rango de fechas")
    recommended_stock_focus: list[str] = Field(default_factory=list, description="Enfoque recomendado de stock")
    visual_merchandising_tip: str = Field(default="", description="Sugerencia de colocación")


class ContextTriggerSchema(BaseModel):
    """Esquema para extraer triggers contextuales (Tarea 3: clima y calendario social)."""
    context_triggers: list[ContextTriggerItem] = Field(description="Lista de triggers contextuales")


# Funciones helper para convertir esquemas a estructuras compatibles con MarketIntelligenceEntity

def _build_base_entity_dict(
    signal_type: str,
    source_url: str,
    source_platform: str,
    llm_structured_output: dict[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    """Construye el diccionario base común a todas las entidades MarketIntelligenceEntity.

    Args:
        signal_type: Tipo de señal (media_trends, search_trends, etc.).
        source_url: URL de origen.
        source_platform: Plataforma de origen.
        llm_structured_output: Salida estructurada del LLM.
        **overrides: Campos adicionales que sobrescriben los defaults.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    now = time.time()
    base = {
        "id": str(uuid.uuid4()),
        "signal_type": signal_type,
        "source_url": source_url,
        "source_platform": source_platform,
        "source_method": "browser_use",
        "event_date": None,
        "event_end_date": None,
        "event_status": "active",
        "location": "",
        "risk_dates": [],
        "affected_skus": [],
        "affected_stores": [],
        "trend_score": 0.0,
        "trend_change_pct": 0.0,
        "mention_count": 0,
        "sentiment_score": 0.0,
        "llm_provider": "",
        "llm_model": "",
        "llm_prompt": "",
        "llm_raw_response": "",
        "llm_structured_output": llm_structured_output,
        "llm_reasoning_chain": "",
        "llm_latency_ms": 0.0,
        "llm_tokens_used": 0,
        "found_at": now,
        "effective_from": None,
        "effective_until": None,
        "created_at": now,
        "updated_at": now,
        "reviewed": False,
        "reviewed_by": None,
        "action_taken": "",
    }
    base.update(overrides)
    return base


def _parse_date(date_str: Optional[str]) -> Optional[float]:
    """Convierte una fecha string a timestamp float.

    Args:
        date_str: Fecha en YYYY-MM-DD o como timestamp numérico.

    Returns:
        Timestamp Unix (float) o None si no se puede parsear.
    """
    if not date_str:
        return None
    try:
        # Intentar parsear como YYYY-MM-DD
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.timestamp()
    except ValueError:
        try:
            # Intentar parsear como timestamp
            return float(date_str)
        except ValueError:
            return None


def media_trend_to_entity_dict(item: MediaTrendItem, source_url: str = "", source_platform: str = "") -> dict[str, Any]:
    """Convierte un MediaTrendItem a un diccionario compatible con MarketIntelligenceEntity.

    Args:
        item: Tendencias de medios extraídas.
        source_url: URL por defecto si item no la tiene.
        source_platform: Plataforma por defecto si item no la tiene.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    return _build_base_entity_dict(
        signal_type="media_trends",
        source_url=item.source_url or source_url,
        source_platform=item.source_platform or source_platform,
        llm_structured_output=item.model_dump(),
        title=item.title,
        description=item.description,
        keywords=item.keywords,
        risk_impact=item.risk_impact,
        confidence=item.confidence,
        severity="medium" if item.risk_impact < 0.5 else "high",
        affected_categories=item.affected_categories,
        estimated_demand_increase_pct=item.risk_impact * 100.0,
        viral_potential=0.0,
    )


def search_trend_to_entity_dict(item: SearchTrendItem, source_url: str = "") -> dict[str, Any]:
    """Convierte un SearchTrendItem a un diccionario compatible con MarketIntelligenceEntity.

    Args:
        item: Tendencias de búsqueda extraídas.
        source_url: URL por defecto si item no la tiene.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    return _build_base_entity_dict(
        signal_type="search_trends",
        source_url=item.source_url or source_url,
        source_platform="google_trends",
        llm_structured_output=item.model_dump(),
        title=f"Tendencia: {item.keyword}",
        description=item.description,
        keywords=[item.keyword] + (item.affected_categories or []),
        risk_dates=item.risk_dates,
        risk_impact=min(item.trend_score / 100.0, 1.0) if item.trend_score > 0 else 0.0,
        confidence=0.8 if item.trend_score > 50 else 0.5,
        severity="high" if item.trend_score > 75 else "medium" if item.trend_score > 50 else "low",
        affected_categories=item.affected_categories,
        estimated_demand_increase_pct=item.estimated_demand_increase_pct,
        trend_score=item.trend_score,
        trend_change_pct=item.trend_change_pct,
        viral_potential=0.0,
    )


def fashion_event_to_entity_dict(item: FashionEventItem, source_url: str = "") -> dict[str, Any]:
    """Convierte un FashionEventItem a un diccionario compatible con MarketIntelligenceEntity.

    Args:
        item: Evento de moda extraído.
        source_url: URL por defecto si item no la tiene.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    event_date_ts = _parse_date(item.event_date)
    event_end_date_ts = _parse_date(item.event_end_date)
    return _build_base_entity_dict(
        signal_type="fashion_events",
        source_url=item.source_url or source_url,
        source_platform="",
        llm_structured_output=item.model_dump(),
        title=item.title,
        description=item.description,
        keywords=item.keywords,
        event_date=event_date_ts,
        event_end_date=event_end_date_ts,
        event_status=item.event_status,
        location=item.location,
        risk_impact=item.risk_impact,
        confidence=item.confidence,
        severity="high" if item.risk_impact > 0.7 else "medium" if item.risk_impact > 0.4 else "low",
        affected_categories=item.affected_categories,
        estimated_demand_increase_pct=item.estimated_demand_increase_pct,
        viral_potential=0.0,
        effective_from=event_date_ts,
        effective_until=event_end_date_ts,
    )


def commercial_trend_to_entity_dict(item: CommercialTrendItem, source_url: str = "") -> dict[str, Any]:
    """Convierte un CommercialTrendItem a un diccionario compatible con MarketIntelligenceEntity.

    Args:
        item: Tendencia comercial extraída.
        source_url: URL por defecto si item no la tiene.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    description_parts = []
    if item.style_vibe:
        description_parts.append(f"Estilo: {item.style_vibe}")
    if item.attributes:
        description_parts.append(f"Atributos: {', '.join(item.attributes)}")
    description = ". ".join(description_parts) if description_parts else ""

    keywords = [item.garment_type]
    if item.attributes:
        keywords.extend(item.attributes)
    if item.style_vibe:
        keywords.append(item.style_vibe)

    affected_categories = [item.zara_category_match] if item.zara_category_match else []

    return _build_base_entity_dict(
        signal_type="commercial_trends",
        source_url=item.source_url or source_url,
        source_platform="",
        llm_structured_output=item.model_dump(),
        title=item.garment_type,
        description=description,
        keywords=keywords,
        risk_impact=item.urgency_level,
        confidence=0.7 if item.urgency_level > 0.5 else 0.5,
        severity="high" if item.urgency_level > 0.7 else "medium" if item.urgency_level > 0.4 else "low",
        affected_categories=affected_categories,
        estimated_demand_increase_pct=item.urgency_level * 100.0,
        viral_potential=item.urgency_level,
    )


def search_insight_to_entity_dict(item: SearchInsightItem, source_url: str = "") -> dict[str, Any]:
    """Convierte un SearchInsightItem a un diccionario compatible con MarketIntelligenceEntity.

    Args:
        item: Insight de búsqueda extraído.
        source_url: URL por defecto si item no la tiene.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    keywords = [item.query]
    if item.related_keywords:
        keywords.extend(item.related_keywords)
    description = f"Query: {item.query}"
    if item.growth_status:
        description += f" | Growth: {item.growth_status}"
    if item.implied_product:
        description += f" | Producto implícito: {item.implied_product}"
    if item.suggested_action:
        description += f" | Acción: {item.suggested_action}"
    return _build_base_entity_dict(
        signal_type="search_demand",
        source_url=source_url,
        source_platform="google_trends",
        llm_structured_output=item.model_dump(),
        title=item.query,
        description=description,
        keywords=keywords,
        risk_impact=0.5 if "breakout" in item.growth_status.lower() or "+" in item.growth_status else 0.3,
        confidence=0.7,
        severity="high" if "breakout" in item.growth_status.lower() else "medium",
        affected_categories=[item.implied_product] if item.implied_product else [],
        viral_potential=0.0,
        action_taken=item.suggested_action or "",
    )


def context_trigger_to_entity_dict(item: ContextTriggerItem, source_url: str = "") -> dict[str, Any]:
    """Convierte un ContextTriggerItem a un diccionario compatible con MarketIntelligenceEntity.

    Args:
        item: Trigger contextual extraído.
        source_url: URL por defecto si item no la tiene.

    Returns:
        Diccionario con estructura MarketIntelligenceEntity.
    """
    keywords = [item.trigger_type, item.detail]
    keywords.extend(item.recommended_stock_focus)
    description = f"{item.trigger_type}: {item.detail}"
    if item.date_range:
        description += f" | {item.date_range}"
    if item.visual_merchandising_tip:
        description += f" | VM: {item.visual_merchandising_tip}"
    return _build_base_entity_dict(
        signal_type="contextual_triggers",
        source_url=source_url,
        source_platform="",
        llm_structured_output=item.model_dump(),
        title=f"{item.trigger_type}: {item.detail}",
        description=description,
        keywords=keywords,
        risk_impact=0.5 if item.trigger_type == "Weather" else 0.6,
        confidence=0.7,
        severity="medium",
        affected_categories=item.recommended_stock_focus,
        viral_potential=0.0,
        action_taken=item.visual_merchandising_tip or "",
    )
