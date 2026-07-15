from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class CanvasNodeCreate(BaseModel):
    asset_type: str
    asset_id: Optional[str] = None
    label: str
    x: float = 0
    y: float = 0
    width: float = 200
    height: float = 80
    color: Optional[str] = None
    icon: Optional[str] = None
    risk_level: str = "informational"
    data_json: Dict[str, Any] = {}
    notes: str = ""
    tags: List[str] = []


class CanvasNodeUpdate(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    color: Optional[str] = None
    label: Optional[str] = None
    risk_level: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    hidden: Optional[bool] = None
    locked: Optional[bool] = None


class CanvasNodeResponse(BaseModel):
    id: str
    canvas_id: str
    asset_type: str
    asset_id: Optional[str] = None
    label: str
    x: float
    y: float
    width: float
    height: float
    color: Optional[str] = None
    icon: Optional[str] = None
    risk_level: str
    data_json: Dict[str, Any] = {}
    notes: str
    tags: List[str] = []
    hidden: bool
    locked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CanvasEdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    label: str = ""
    edge_type: str = "default"
    animated: bool = False
    style_json: Dict[str, Any] = {}


class CanvasEdgeResponse(BaseModel):
    id: str
    canvas_id: str
    source_node_id: str
    target_node_id: str
    label: str
    edge_type: str
    animated: bool
    style_json: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class CanvasCreate(BaseModel):
    name: str = "Untitled Canvas"
    description: str = ""
    project_id: Optional[str] = None


class CanvasUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    viewport_x: Optional[float] = None
    viewport_y: Optional[float] = None
    viewport_zoom: Optional[float] = None


class CanvasResponse(BaseModel):
    id: str
    name: str
    description: str
    user_id: str
    project_id: Optional[str] = None
    viewport_x: float
    viewport_y: float
    viewport_zoom: float
    node_count: int = 0
    edge_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CanvasDetailResponse(BaseModel):
    id: str
    name: str
    description: str
    user_id: str
    project_id: Optional[str] = None
    viewport_x: float
    viewport_y: float
    viewport_zoom: float
    nodes: List[CanvasNodeResponse] = []
    edges: List[CanvasEdgeResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CanvasImportRequest(BaseModel):
    scan_id: str
    layout: str = "auto"
    asset_types: Optional[List[str]] = None
    asset_ids: Optional[List[str]] = None


class CanvasBulkNodeCreate(BaseModel):
    nodes: List[CanvasNodeCreate]
    edges: List[CanvasEdgeCreate] = []


class CanvasExportRequest(BaseModel):
    format: str = "json"


class ScanAssetPreview(BaseModel):
    asset_type: str
    asset_id: str
    label: str
    detail: Dict[str, Any] = {}
    is_alive: Optional[bool] = None
    risk_level: str = "informational"


class ScanPreviewResponse(BaseModel):
    scan_id: str
    domain: str
    status: str
    assets: Dict[str, List[ScanAssetPreview]]
    counts: Dict[str, int]
