from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class AIConversationCreate(BaseModel):
    title: Optional[str] = "New conversation"
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class AIConversationResponse(BaseModel):
    id: str
    title: str
    user_id: str
    context_org_id: Optional[str] = None
    context_project_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIMessageCreate(BaseModel):
    content: str
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class AIMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    token_count: int
    model_used: Optional[str] = None
    response_time_ms: Optional[int] = None
    metadata_json: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class AIChatResponse(BaseModel):
    conversation_id: str
    message: AIMessageResponse
    suggestions: List[str] = []
    references: List[Dict[str, Any]] = []


class AIRecommendationResponse(BaseModel):
    id: str
    category: str
    title: str
    description: str
    priority: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    status: str
    dismissed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AIKnowledgeResponse(BaseModel):
    id: str
    title: str
    category: str
    content: str
    related_pages: List[str] = []
    tags: List[str] = []

    class Config:
        from_attributes = True


class AISettingsUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    language: Optional[str] = None
    tone: Optional[str] = None
    enabled: Optional[bool] = None


class AISettingsResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    model: str
    temperature: float
    max_tokens: int
    language: str
    tone: str
    enabled: bool

    class Config:
        from_attributes = True


class AIUsageResponse(BaseModel):
    total_questions: int
    total_reports: int
    avg_response_time_ms: int
    total_tokens: int
    estimated_cost: float
    recent_activity: List[Dict[str, Any]] = []


class AIDashboardResponse(BaseModel):
    today_summary: Dict[str, Any]
    recent_changes: List[Dict[str, Any]]
    recommendations: List[AIRecommendationResponse]
    top_recommendations: List[AIRecommendationResponse]
    certificate_alerts: List[Dict[str, Any]]
    technology_changes: List[Dict[str, Any]]
    platform_health: Dict[str, Any]
    weekly_summary: Dict[str, Any]


class AINLSearchRequest(BaseModel):
    query: str
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class AINLSearchResult(BaseModel):
    query: str
    interpretation: str
    results: List[Dict[str, Any]]
    filters_applied: Dict[str, Any] = {}
    count: int


class AIReportRequest(BaseModel):
    report_type: str
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    format: str = "markdown"


class AIReportResponse(BaseModel):
    id: str
    title: str
    content: str
    report_type: str
    format: str
    generated_at: datetime


class AIWorkflowCreate(BaseModel):
    name: str
    trigger: str
    prompt_template: str
    schedule: Optional[str] = None
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class AIWorkflowResponse(BaseModel):
    id: str
    name: str
    trigger: str
    prompt_template: str
    schedule: Optional[str] = None
    enabled: bool
    last_run: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
