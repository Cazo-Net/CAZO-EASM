from sqlalchemy import Column, String, DateTime, Text, Float, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.database import Base


class Canvas(Base):
    __tablename__ = "canvases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    name = Column(String(255), nullable=False, default="Untitled Canvas")
    description = Column(Text, default="")
    viewport_x = Column(Float, default=0)
    viewport_y = Column(Float, default=0)
    viewport_zoom = Column(Float, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    nodes = relationship("CanvasNode", back_populates="canvas", cascade="all, delete-orphan")
    edges = relationship("CanvasEdge", back_populates="canvas", cascade="all, delete-orphan")


class CanvasNode(Base):
    __tablename__ = "canvas_nodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String(36), ForeignKey("canvases.id"), nullable=False)
    asset_type = Column(String(50), nullable=False)
    asset_id = Column(String(36), nullable=True)
    label = Column(String(255), nullable=False)
    x = Column(Float, default=0)
    y = Column(Float, default=0)
    width = Column(Float, default=200)
    height = Column(Float, default=80)
    color = Column(String(7), nullable=True)
    icon = Column(String(50), nullable=True)
    risk_level = Column(String(20), default="informational")
    data_json = Column(JSON, default=dict)
    notes = Column(Text, default="")
    tags = Column(JSON, default=list)
    hidden = Column(Boolean, default=False)
    locked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    canvas = relationship("Canvas", back_populates="nodes")


class CanvasEdge(Base):
    __tablename__ = "canvas_edges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id = Column(String(36), ForeignKey("canvases.id"), nullable=False)
    source_node_id = Column(String(36), ForeignKey("canvas_nodes.id"), nullable=False)
    target_node_id = Column(String(36), ForeignKey("canvas_nodes.id"), nullable=False)
    label = Column(String(100), default="")
    edge_type = Column(String(50), default="default")
    animated = Column(Boolean, default=False)
    style_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    canvas = relationship("Canvas", back_populates="edges")
