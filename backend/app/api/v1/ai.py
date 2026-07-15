from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.ai_service import AIService
from app.schemas.ai import (
    AIConversationCreate, AIConversationResponse,
    AIMessageCreate, AIChatResponse,
    AIRecommendationResponse, AIKnowledgeResponse,
    AISettingsUpdate, AISettingsResponse,
    AIUsageResponse, AIDashboardResponse,
    AINLSearchRequest, AINLSearchResult,
    AIReportRequest, AIReportResponse,
    AIWorkflowCreate, AIWorkflowResponse,
)

router = APIRouter()


@router.post("/chat")
async def chat(
    data: AIMessageCreate,
    conversation_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    result = await service.chat(
        user_id=current_user.id,
        conversation_id=conversation_id,
        message=data.content,
        org_id=data.org_id,
        project_id=data.project_id,
    )
    return result


@router.get("/conversations")
def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.ai import AIConversation
    convs = db.query(AIConversation).filter(
        AIConversation.user_id == current_user.id
    ).order_by(AIConversation.updated_at.desc()).limit(limit).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.ai import AIConversation, AIMessage
    conv = db.query(AIConversation).filter(
        AIConversation.id == conversation_id,
        AIConversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = db.query(AIMessage).filter(
        AIMessage.conversation_id == conversation_id
    ).order_by(AIMessage.created_at).all()
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "model_used": m.model_used,
                "response_time_ms": m.response_time_ms,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.ai import AIConversation
    conv = db.query(AIConversation).filter(
        AIConversation.id == conversation_id,
        AIConversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"ok": True}


@router.get("/dashboard")
def get_ai_dashboard(
    org_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    return service.get_dashboard(current_user.id, org_id)


@router.post("/search")
async def natural_language_search(
    data: AINLSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    return await service.search(current_user.id, data.query, data.org_id, data.project_id)


@router.post("/reports/generate")
async def generate_report(
    data: AIReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    return await service.generate_report(
        current_user.id, data.report_type, data.org_id, data.project_id,
        data.date_from, data.date_to,
    )


@router.get("/recommendations")
async def get_recommendations(
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    return await service.get_recommendations(current_user.id, org_id, project_id)


@router.put("/recommendations/{rec_id}/dismiss")
def dismiss_recommendation(
    rec_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.ai import AIRecommendation
    rec = db.query(AIRecommendation).filter(
        AIRecommendation.id == rec_id,
        AIRecommendation.user_id == current_user.id,
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.dismissed = True
    db.commit()
    return {"ok": True}


@router.get("/knowledge")
def list_knowledge_articles(
    category: Optional[str] = None,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.ai import AIKnowledgeArticle
    q = db.query(AIKnowledgeArticle)
    if category:
        q = q.filter(AIKnowledgeArticle.category == category)
    if query:
        q = q.filter(AIKnowledgeArticle.title.contains(query))
    articles = q.limit(50).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "category": a.category,
            "content": a.content,
            "related_pages": a.related_pages or [],
            "tags": a.tags or [],
        }
        for a in articles
    ]


@router.get("/settings")
def get_ai_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    settings = service._ensure_settings(current_user.id)
    return {
        "id": settings.id,
        "user_id": settings.user_id,
        "provider": settings.provider,
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "language": settings.language,
        "tone": settings.tone,
        "enabled": settings.enabled,
    }


@router.put("/settings")
def update_ai_settings(
    data: AISettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    settings = service._ensure_settings(current_user.id)
    if data.provider is not None:
        settings.provider = data.provider
    if data.model is not None:
        settings.model = data.model
    if data.temperature is not None:
        settings.temperature = data.temperature
    if data.max_tokens is not None:
        settings.max_tokens = data.max_tokens
    if data.language is not None:
        settings.language = data.language
    if data.tone is not None:
        settings.tone = data.tone
    if data.enabled is not None:
        settings.enabled = data.enabled
    db.commit()
    db.refresh(settings)
    return {
        "id": settings.id,
        "provider": settings.provider,
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "language": settings.language,
        "tone": settings.tone,
        "enabled": settings.enabled,
    }


@router.get("/usage")
def get_usage_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AIService(db)
    return service.get_usage_stats(current_user.id)
