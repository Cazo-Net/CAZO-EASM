from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.database import Base


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="New conversation")
    context_org_id = Column(String(36), nullable=True)
    context_project_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("AIMessage", back_populates="conversation", cascade="all, delete-orphan")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("ai_conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    model_used = Column(String(100), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("AIConversation", back_populates="messages")


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    org_id = Column(String(36), nullable=True)
    project_id = Column(String(36), nullable=True)
    category = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="medium")
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(36), nullable=True)
    status = Column(String(20), default="pending")
    dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIKnowledgeArticle(Base):
    __tablename__ = "ai_knowledge_articles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    related_pages = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, default=0)
    response_time_ms = Column(Integer, default=0)
    org_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AISettings(Base):
    __tablename__ = "ai_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    provider = Column(String(50), default="openai")
    model = Column(String(100), default="gpt-4o-mini")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    language = Column(String(10), default="en")
    tone = Column(String(20), default="balanced")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AIWorkflow(Base):
    __tablename__ = "ai_workflows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    trigger = Column(String(50), nullable=False)
    prompt_template = Column(Text, nullable=False)
    schedule = Column(String(50), nullable=True)
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    org_id = Column(String(36), nullable=True)
    project_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
