"""Pydantic schemas for executive reporting."""
from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel


class ExecAsset(BaseModel):
    asset_id: str
    value: Optional[str] = None
    asset_type: Optional[str] = None
    exposure_score: float = 0.0


class ExecutiveReport(BaseModel):
    total_assets: int = 0
    total_scans: int = 0
    active_scans: int = 0
    critical_vulns: int = 0
    high_vulns: int = 0
    medium_vulns: int = 0
    low_vulns: int = 0
    top_exposed_assets: List[ExecAsset] = []
    summary_text: str = ""
    generated_at: Optional[datetime] = None


class ExecutiveReportRequest(BaseModel):
    format: Literal["json", "pdf", "csv"] = "json"


class ExecutiveReportGenerated(ExecutiveReport):
    format: str = "json"
    note: Optional[str] = None
